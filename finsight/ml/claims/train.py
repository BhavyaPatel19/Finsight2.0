"""
Fine-tune a small encoder to detect forward-looking commitments in transcript sentences.

    python -m finsight.ml.claims.train [--model answerdotai/ModernBERT-base] [--epochs 3] [--out models/claim-detector]

Trains on eval/gold/claims_silver.jsonl (LLM-labelled), holds out 15% of it for
validation, and reports precision/recall/F1 on (a) the silver validation split and
(b) the human gold set (never trained on). Also scores two baselines on the same
gold: the cue regex (finsight.verification.claims.is_candidate) and zero-shot
yiyanghkust/finbert-fls (Specific/Non-specific FLS → positive).

Plain PyTorch loop; Apple silicon (MPS) or CUDA if available, else CPU.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def prf(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == 1 and p == 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "n": len(y_true),
        "positives": sum(y_true),
    }


def device():
    import torch

    return "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def baseline_regex(sentences: list[str]) -> list[int]:
    from finsight.verification.claims import is_candidate

    return [int(is_candidate(s)) for s in sentences]


def baseline_finbert_fls(sentences: list[str]) -> list[int]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    name = "yiyanghkust/finbert-fls"
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSequenceClassification.from_pretrained(name).to(device()).eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(sentences), 32):
            batch = tok(sentences[i : i + 32], padding=True, truncation=True, max_length=128, return_tensors="pt").to(
                device()
            )
            labels = model(**batch).logits.argmax(-1).tolist()
            preds.extend(int(lab != 0) for lab in labels)  # 0 = Not FLS
    return preds


def train(model_name: str, train_rows: list[dict], val_rows: list[dict], epochs: int, lr: float, out: Path) -> tuple:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dev = device()
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    pos = sum(r["label"] for r in train_rows)
    weight = torch.tensor([1.0, max(1.0, (len(train_rows) - pos) / max(1, pos))], device=dev)  # class imbalance
    loss_fn = torch.nn.CrossEntropyLoss(weight=weight)
    bs = 16
    steps = epochs * ((len(train_rows) + bs - 1) // bs)
    sched = torch.optim.lr_scheduler.LinearLR(opt, start_factor=1.0, end_factor=0.05, total_iters=steps)
    t0 = time.time()
    for ep in range(epochs):
        random.shuffle(train_rows)
        model.train()
        total = 0.0
        for i in range(0, len(train_rows), bs):
            batch = train_rows[i : i + bs]
            enc = tok(
                [r["sentence"] for r in batch], padding=True, truncation=True, max_length=128, return_tensors="pt"
            ).to(dev)
            y = torch.tensor([r["label"] for r in batch], device=dev)
            loss = loss_fn(model(**enc).logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += loss.item() * len(batch)
        val = evaluate(model, tok, val_rows)
        print(
            f"epoch {ep + 1}/{epochs}: loss {total / len(train_rows):.4f} · val P {val['precision']:.3f} R {val['recall']:.3f} F1 {val['f1']:.3f} · {time.time() - t0:.0f}s"
        )
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    return model, tok


def evaluate(model, tok, rows: list[dict]) -> dict:
    import torch

    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(rows), 32):
            enc = tok(
                [r["sentence"] for r in rows[i : i + 32]],
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            ).to(model.device)
            preds.extend(model(**enc).logits.argmax(-1).tolist())
    return prf([r["label"] for r in rows], preds)


def main() -> None:
    os.environ.setdefault("SECRET_KEY", "train")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="answerdotai/ModernBERT-base")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "claim-detector")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    random.seed(args.seed)

    from finsight.ml.claims.dataset import SILVER, gold_labels, transcript_sentences

    silver = load_jsonl(SILVER)
    random.shuffle(silver)
    n_val = max(1, int(len(silver) * 0.15))
    val, tr = silver[:n_val], silver[n_val:]
    gold = gold_labels(transcript_sentences())
    print(
        f"train {len(tr)} · val {len(val)} · gold {len(gold)} ({sum(r['label'] for r in gold)} positive) · device {device()}"
    )

    results = {"model": args.model, "train": len(tr), "val": len(val), "gold": len(gold)}
    gold_s = [r["sentence"] for r in gold]
    gold_y = [r["label"] for r in gold]
    results["regex_on_gold"] = prf(gold_y, baseline_regex(gold_s))
    print("regex baseline on gold:", results["regex_on_gold"])
    try:
        results["finbert_fls_on_gold"] = prf(gold_y, baseline_finbert_fls(gold_s))
        print("FinBERT-FLS zero-shot on gold:", results["finbert_fls_on_gold"])
    except Exception as e:  # model download may be unavailable offline
        results["finbert_fls_on_gold"] = f"unavailable: {e}"

    model, tok = train(args.model, tr, val, args.epochs, args.lr, args.out)
    results["finetuned_on_val"] = evaluate(model, tok, val)
    results["finetuned_on_gold"] = evaluate(model, tok, gold)
    print("fine-tuned on silver val:", results["finetuned_on_val"])
    print("fine-tuned on gold:", results["finetuned_on_gold"])
    out = ROOT / "eval" / "results" / "claim_detector.json"
    out.write_text(json.dumps(results, indent=1) + "\n")
    print(f"wrote {out.relative_to(ROOT)} · weights in {args.out}")


if __name__ == "__main__":
    main()
