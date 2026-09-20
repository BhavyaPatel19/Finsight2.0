"""
Training data for the forward-looking-claim detector.

Sentences come from the v2 sentence index of the transcript documents.
Labels:
  gold    the human-labelled claims in eval/gold/wtt_claims.jsonl (positive) plus a
          hand-checked negative list in eval/gold/claim_negatives.txt
  silver  what the LLM extraction kept (positive) vs. candidate sentences it rejected
          and sentences with no forward-looking cue (negative), from persisted
          WalkTheTalkResult rows — the LLM as teacher

    python -m finsight.ml.claims.dataset            # writes eval/gold/claims_silver.jsonl and prints counts
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GOLD_CLAIMS = ROOT / "eval" / "gold" / "wtt_claims.jsonl"
GOLD_NEG = ROOT / "eval" / "gold" / "claim_negatives.txt"
GOLD_POS = ROOT / "eval" / "gold" / "claim_positives.txt"
SILVER = ROOT / "eval" / "gold" / "claims_silver.jsonl"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("[", "").replace("]", "")).strip().lower()


def transcript_sentences() -> list[dict]:
    """[{sentence, document_id, chunk_id, speaker}] for every prose sentence of every transcript in the index."""
    from sqlmodel import Session, select

    from finsight.corpus.chunker import split_sentences
    from finsight.database.session import engine
    from finsight.models import Document
    from finsight.retrieval import index as ix

    with Session(engine) as s:
        transcript_ids = {d.id for d in s.exec(select(Document).where(Document.doc_type == "concall")).all()}
    out, seen = [], set()
    for c in ix.all_chunks():
        m = c["metadata"]
        if m.get("document_id") not in transcript_ids or m.get("kind") != "prose":
            continue
        for sent in split_sentences(c["text"]):
            key = _norm(sent)
            if len(sent) < 25 or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "sentence": sent,
                    "document_id": m["document_id"],
                    "chunk_id": c["id"],
                    "speaker": m.get("speaker") or None,
                }
            )
    return out


def silver_labels(sentences: list[dict]) -> list[dict]:
    """Label each sentence with the LLM's decision where one exists."""
    from sqlmodel import Session, select

    from finsight.database.session import engine
    from finsight.models import WalkTheTalkResult
    from finsight.verification.claims import is_candidate

    with Session(engine) as s:
        rows = s.exec(select(WalkTheTalkResult)).all()
        positives = {_norm(c["quote"]) for r in rows for c in json.loads(r.claims_json or "[]") if c.get("quote")}
        judged_docs = {r.claims_document_id for r in rows}
    out = []
    for x in sentences:
        k = _norm(x["sentence"])
        if k in positives:
            label, source = 1, "llm"
        elif x["document_id"] in judged_docs and is_candidate(x["sentence"]):
            label, source = 0, "llm-rejected"
        elif not is_candidate(x["sentence"]):
            label, source = 0, "no-cue"
        else:
            continue  # candidate in a document the LLM never judged
        out.append({**x, "label": label, "source": source})
    return out


def _lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {_norm(line)[:60] for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")}


def gold_labels(sentences: list[dict]) -> list[dict]:
    """Human labels: WTT claim quotes + claim_positives.txt are positive; claim_negatives.txt negative."""
    pos = {
        _norm(re.sub(r"\[.*?\]\s*", "", json.loads(line)["claim"]))[:60]
        for line in GOLD_CLAIMS.read_text().splitlines()
        if line.strip()
    } | _lines(GOLD_POS)
    neg = _lines(GOLD_NEG)
    out = []
    for x in sentences:
        k = _norm(x["sentence"])[:60]
        if k in pos:
            out.append({**x, "label": 1, "source": "gold"})
        elif k in neg:
            out.append({**x, "label": 0, "source": "gold"})
    return out


def main() -> None:
    os.environ.setdefault("SECRET_KEY", "dataset")
    sents = transcript_sentences()
    silver = silver_labels(sents)
    gold = gold_labels(sents)
    gold_keys = {_norm(x["sentence"]) for x in gold}
    silver = [x for x in silver if _norm(x["sentence"]) not in gold_keys]  # gold is held out from training
    with SILVER.open("w") as f:
        for x in silver:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    from collections import Counter

    print(f"transcript sentences: {len(sents)}")
    print(f"silver (train): {len(silver)} — {dict(Counter((x['label'], x['source']) for x in silver))}")
    print(f"gold (held-out eval): {len(gold)} — {dict(Counter(x['label'] for x in gold))}")
    print(f"wrote {SILVER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
