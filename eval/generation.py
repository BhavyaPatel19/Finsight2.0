"""
End-to-end answer evaluation: run the production RAG pipeline on the gold
questions and score the answers.

    python -m eval.generation                 # deterministic + judge
    python -m eval.generation --no-judge      # deterministic only (no extra LLM calls)
    python -m eval.generation --model llama-3.3-70b-versatile --tag groq

Deterministic (no judge):
    number_recall     share of the reference answer's numbers present in the answer
    abstain           unanswerable questions answered "Not found in the selected documents."
    false_abstain     answerable questions wrongly answered "Not found…"
    cited             answer contains at least one [… Page N] citation
    citation_valid    every cited page belongs to a retrieved chunk
Judge (eval/judge.py, same provider unless --judge-model):
    faithfulness      claims in the answer supported by retrieved context
    correctness       correct / partial / incorrect vs the human reference
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold" / "retrieval.jsonl"
RESULTS = ROOT / "eval" / "results"

ABSTAIN_RE = re.compile(r"not found in the selected documents", re.I)
CITATION_RE = re.compile(r"\[[^\]]*?Page\s+(\d+)[^\]]*\]", re.I)
NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?(?:%|bn|mn|billion|million|crore)?", re.I)


def numbers(text: str) -> set[str]:
    """Distinctive numeric tokens, normalised: '$4,730 million' -> '4730', '21.1%' -> '21.1%'."""
    out = set()
    for tok in NUM_RE.findall(text):
        t = tok.lower().replace("$", "").replace(",", "").strip()
        t = re.sub(r"\s?(billion|bn)$", "bn", t)
        t = re.sub(r"\s?(million|mn)$", "mn", t)
        core = re.sub(r"(%|bn|mn|crore)$", "", t)
        if core.replace(".", "").isdigit() and len(core.replace(".", "")) >= 2:
            out.add(t)
    return out


def number_recall(reference: str, answer: str) -> float | None:
    ref = numbers(reference)
    if not ref:
        return None
    ans_text = answer.lower().replace(",", "")
    ans = numbers(answer)
    hit = 0
    for r in ref:
        core = re.sub(r"(%|bn|mn|crore)$", "", r)
        if r in ans or core in ans or re.search(rf"(?<![\d.]){re.escape(core)}(?![\d])", ans_text):
            hit += 1
    return hit / len(ref)


def deterministic(item: dict, answer: str, sources: list[dict]) -> dict:
    abstained = bool(ABSTAIN_RE.search(answer))
    cited_pages = {int(p) for p in CITATION_RE.findall(answer)}
    retrieved_pages = {s.get("page_number") for s in sources}
    out = {
        "abstained": abstained,
        "cited": bool(cited_pages),
        "citation_valid": (cited_pages <= retrieved_pages) if cited_pages else None,
    }
    if item["answerable"]:
        out["number_recall"] = number_recall(item["answer"], answer)
        out["false_abstain"] = abstained
    else:
        out["abstain_ok"] = abstained
    return out


def run(session, gold: list[dict], *, model: str | None, judge: bool, judge_model: str | None, top_k: int) -> list[dict]:
    from finsight.rag.service import answer_question

    rows = []
    for item in gold:
        t0 = time.perf_counter()
        try:
            res = answer_question(session, item["question"], top_k=top_k, model=model)
        except Exception as e:  # provider down: record and continue
            rows.append({"id": item["id"], "type": item["type"], "error": str(e)[:200]})
            print(f"  {item['id']} ERROR {e}")
            continue
        answer = res["answer"]
        row = {
            "id": item["id"], "type": item["type"], "answerable": item["answerable"],
            "question": item["question"], "reference": item["answer"], "answer": answer,
            "model": res.get("model_used"), "latency_ms": round((time.perf_counter() - t0) * 1000),
            "usage": res.get("usage"),
            **deterministic(item, answer, res.get("sources", [])),
        }
        if judge:
            contexts = [s["snippet"] for s in res.get("sources", [])]
            if item["answerable"] and not row["abstained"]:
                row["faithfulness"] = judge_faithfulness_cached(answer, res, contexts, judge_model)
            if item["answerable"]:
                row["correctness"] = judge_correctness_cached(item, answer, judge_model)
        rows.append(row)
        flag = "abstain" if row["abstained"] else f"nums {row.get('number_recall')}"
        grade = row.get("correctness", {}).get("grade", "")
        print(f"  {item['id']} [{item['type'][:8]:8s}] {row['latency_ms']:5d} ms  {flag}  {grade}")
    return rows


def judge_faithfulness_cached(answer, res, contexts, judge_model):
    from eval.judge import judge_faithfulness
    # Full chunk text gives the judge more to verify against than the 300-char snippet.
    full = [c for c in (res.get("context") or contexts) if c]
    return judge_faithfulness(answer, full, model=judge_model)


def judge_correctness_cached(item, answer, judge_model):
    from eval.judge import judge_correctness
    return judge_correctness(item["question"], item["answer"], answer, model=judge_model)


def summarise(rows: list[dict]) -> dict:
    from eval.metrics import mean

    ok = [r for r in rows if "error" not in r]
    ans = [r for r in ok if r["answerable"]]
    unans = [r for r in ok if not r["answerable"]]
    nr = [r["number_recall"] for r in ans if r.get("number_recall") is not None]
    faith = [r["faithfulness"]["score"] for r in ans if r.get("faithfulness", {}).get("score") is not None]
    grades = [r["correctness"]["grade"] for r in ans if r.get("correctness")]
    cited = [r for r in ans if not r["abstained"]]
    return {
        "n": len(rows), "errors": len(rows) - len(ok),
        "answerable": len(ans), "unanswerable": len(unans),
        "number_recall": round(mean(nr), 4) if nr else None,
        "false_abstain_rate": round(mean([float(r["false_abstain"]) for r in ans]), 4) if ans else None,
        "abstain_rate_on_unanswerable": round(mean([float(r["abstain_ok"]) for r in unans]), 4) if unans else None,
        "cited_rate": round(mean([float(r["cited"]) for r in cited]), 4) if cited else None,
        "citation_valid_rate": round(mean([float(r["citation_valid"]) for r in cited if r["citation_valid"] is not None]), 4)
        if any(r["citation_valid"] is not None for r in cited) else None,
        "faithfulness": round(mean(faith), 4) if faith else None,
        "faithfulness_n": len(faith),
        "correctness": {g: grades.count(g) / len(grades) for g in ("correct", "partial", "incorrect", "unknown")} if grades else None,
        "correctness_n": len(grades),
        "latency_ms_mean": round(mean([r["latency_ms"] for r in ok])) if ok else None,
        "by_type": {
            t: {"n": sum(1 for r in ans if r["type"] == t),
                "number_recall": round(mean([r["number_recall"] for r in ans if r["type"] == t and r.get("number_recall") is not None]), 3),
                "correct": round(mean([float(r["correctness"]["grade"] == "correct") for r in ans if r["type"] == t and r.get("correctness")]), 3)
                if any(r.get("correctness") for r in ans if r["type"] == t) else None}
            for t in sorted({r["type"] for r in ans})
        },
    }


def write_markdown(report: dict, path: Path) -> None:
    s = report["summary"]
    c = s["correctness"] or {}
    lines = [
        f"# Generation evaluation — {report['timestamp'][:10]} (`{report['git_sha']}`{', ' + report['tag'] if report.get('tag') else ''})",
        "",
        f"Generator `{report['model']}` via `{report['provider']}` · judge `{report['judge_model'] or report['model']}` · top-{report['top_k']} hybrid+rerank",
        f"· {s['answerable']} answerable + {s['unanswerable']} unanswerable questions · {s['errors']} errors",
        "",
        "| metric | value |",
        "|---|---|",
        f"| correctness vs reference (judge) | correct {c.get('correct', 0):.1%} · partial {c.get('partial', 0):.1%} · incorrect {c.get('incorrect', 0):.1%} (n={s['correctness_n']}) |" if c else "| correctness | – (no judge) |",
        f"| faithfulness (judge, claims supported by context) | {s['faithfulness']:.3f} (n={s['faithfulness_n']}) |" if s["faithfulness"] is not None else "| faithfulness | – (no judge) |",
        f"| number recall (reference numbers present) | {s['number_recall']:.3f} |" if s["number_recall"] is not None else "| number recall | – |",
        f"| abstains on unanswerable | {s['abstain_rate_on_unanswerable']:.1%} |" if s["abstain_rate_on_unanswerable"] is not None else "| abstains on unanswerable | – |",
        f"| false abstain on answerable | {s['false_abstain_rate']:.1%} |" if s["false_abstain_rate"] is not None else "| false abstain | – |",
        f"| answers with a page citation | {s['cited_rate']:.1%} |" if s["cited_rate"] is not None else "| cited | – |",
        f"| cited pages ⊆ retrieved pages | {s['citation_valid_rate']:.1%} |" if s["citation_valid_rate"] is not None else "| citation validity | – |",
        f"| mean latency | {s['latency_ms_mean']} ms |",
        "",
        "## By question type", "", "| type | n | number recall | correct |", "|---|---|---|---|",
    ]
    for t, v in s["by_type"].items():
        lines.append(f"| {t} | {v['n']} | {v['number_recall']:.2f} | {v['correct']:.0%} |" if v["correct"] is not None else f"| {t} | {v['n']} | {v['number_recall']:.2f} | – |")
    lines += ["", "Number recall and abstention are deterministic; correctness and faithfulness are LLM-judged (prompts in eval/judge.py).", ""]
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=None, help="generator model (provider default if omitted)")
    ap.add_argument("--judge-model", default=None, help="judge model (defaults to --model)")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="only the first N questions (smoke test)")
    ap.add_argument("--ids", default="", help="comma-separated question ids to (re)run")
    ap.add_argument("--merge-into", type=Path, default=None, help="update these rows in an existing results JSON instead of writing a new file")
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    os.environ.setdefault("SECRET_KEY", "eval")
    from sqlmodel import Session

    from eval.retrieval import git_sha, load_gold
    from finsight.database.session import engine
    from finsight.llm import get_provider

    gold = load_gold(args.gold)
    if args.ids:
        wanted = set(args.ids.split(","))
        gold = [g for g in gold if g["id"] in wanted]
    if args.limit:
        gold = gold[: args.limit]
    provider = get_provider()
    model = args.model or provider.default_model
    print(f"generator {model} via {provider.name}; judge {'off' if args.no_judge else (args.judge_model or model)}; {len(gold)} questions")

    with Session(engine) as session:
        rows = run(session, gold, model=args.model, judge=not args.no_judge, judge_model=args.judge_model or args.model, top_k=args.top_k)

    if args.merge_into:
        # Re-run of specific questions: replace those rows, recompute the summary, keep provenance.
        report = json.loads(args.merge_into.read_text())
        by_id = {r["id"]: r for r in report["rows"]}
        by_id.update({r["id"]: r for r in rows})
        report["rows"] = [by_id[g["id"]] for g in load_gold(args.gold) if g["id"] in by_id]
        report["summary"] = summarise(report["rows"])
        report.setdefault("reruns", []).append({"ids": sorted(r["id"] for r in rows), "git_sha": git_sha(),
                                                 "timestamp": datetime.now(UTC).isoformat(timespec="seconds")})
        out = args.merge_into
    else:
        report = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"), "git_sha": git_sha(), "tag": args.tag,
            "provider": provider.name, "model": model, "judge_model": args.judge_model, "top_k": args.top_k,
            "summary": summarise(rows), "rows": rows,
        }
        name = args.tag or f"{provider.name}-{datetime.now().strftime('%Y-%m-%d')}"
        out = RESULTS / f"generation_{name}.json"
    RESULTS.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_markdown(report, RESULTS / "generation_latest.md")
    s = report["summary"]
    print(json.dumps({k: v for k, v in s.items() if k not in ("by_type",)}, indent=1))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
