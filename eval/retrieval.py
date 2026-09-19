"""
Retrieval evaluation: does the pipeline surface the chunk that answers the
question? Runs every retrieval mode over the same indexed corpus and gold set.

    python -m eval.retrieval                       # all modes, k=8
    python -m eval.retrieval --modes dense bm25    # subset
    python -m eval.retrieval --k 5 --tag pre-fix   # label the run

A retrieved chunk is relevant iff it comes from a gold document AND contains
one of the gold evidence quotes (whitespace/quote-normalised). Page overlap
is reported separately as a diagnostic; it is not used for scoring.

Writes eval/results/retrieval_<tag-or-date>.json and refreshes
eval/results/retrieval_latest.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold" / "retrieval.jsonl"
MANIFEST = ROOT / "eval" / "gold" / "documents.json"
RESULTS = ROOT / "eval" / "results"


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def load_gold(path: Path = GOLD) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def doc_key_by_id(session) -> dict[int, str]:
    """Map Document.id -> manifest key via source_url."""
    from sqlmodel import select

    from finsight.models import Document

    by_url = {d["url"]: d["key"] for d in json.loads(MANIFEST.read_text())["documents"]}
    out = {}
    for doc in session.exec(select(Document)).all():
        if doc.source_url in by_url:
            out[doc.id] = by_url[doc.source_url]
    return out


def is_relevant(hit: dict, item: dict, key_by_id: dict[int, str]) -> tuple[bool, bool]:
    """(evidence_match, page_match) for one retrieved chunk against one gold item."""
    meta = hit.get("metadata", {})
    key = key_by_id.get(meta.get("document_id"))
    gold = item["docs"].get(key)
    if not gold:
        return False, False
    text = _norm(hit.get("text", ""))
    evidence = any(_norm(q) in text for q in gold["evidence"])
    page = meta.get("page_number") in gold["pages"]
    return evidence, page


def corpus_coverage(session, gold: list[dict], key_by_id: dict[int, str]) -> dict:
    """Upper bound: for how many items does *some* chunk contain the evidence?"""
    from sqlmodel import select

    from finsight.models import DocumentChunk

    chunks_by_key: dict[str, list[str]] = {}
    for c in session.exec(select(DocumentChunk)).all():
        key = key_by_id.get(c.document_id)
        if key:
            chunks_by_key.setdefault(key, []).append(_norm(c.text))
    covered, missing = 0, []
    for item in gold:
        if not item["answerable"]:
            continue
        ok = any(
            any(_norm(q) in t for t in chunks_by_key.get(key, []))
            for key, g in item["docs"].items()
            for q in g["evidence"]
        )
        covered += ok
        if not ok:
            missing.append(item["id"])
    n = sum(1 for i in gold if i["answerable"])
    return {"answerable": n, "covered": covered, "coverage": covered / n if n else 0.0, "uncovered_ids": missing}


def evaluate_mode(session, gold: list[dict], mode: str, k: int, candidates: int, key_by_id: dict[int, str]) -> dict:
    from eval.metrics import hit_at_k, mean, ndcg_at_k, precision_at_k, reciprocal_rank
    from finsight.rag.retrieval import retrieve

    per_q = []
    stage_ms: dict[str, list[float]] = {}
    for item in gold:
        if not item["answerable"]:
            continue
        res = retrieve(session, item["question"], mode=mode, top_k=k, candidates=candidates)
        rels, pages, docs_hit = [], [], set()
        for hit in res["chunks"]:
            ev, pg = is_relevant(hit, item, key_by_id)
            rels.append(int(ev))
            pages.append(int(pg))
            if ev:
                docs_hit.add(key_by_id.get(hit["metadata"].get("document_id")))
        n_gold_docs = len(item["docs"])
        per_q.append(
            {
                "id": item["id"],
                "type": item["type"],
                "hit@1": hit_at_k(rels, 1),
                "hit@3": hit_at_k(rels, 3),
                "hit@5": hit_at_k(rels, 5),
                f"hit@{k}": hit_at_k(rels, k),
                "rr": reciprocal_rank(rels, k),
                "ndcg": ndcg_at_k(rels, k, n_relevant=max(1, sum(rels))),
                "p@5": precision_at_k(rels, 5),
                "page_hit@5": hit_at_k(pages, 5),
                "docs_covered": len(docs_hit) / n_gold_docs if n_gold_docs else 0.0,
                "first_rank": (rels.index(1) + 1) if 1 in rels else None,
            }
        )
        for stage, ms in res["timings_ms"].items():
            stage_ms.setdefault(stage, []).append(ms)

    def agg(field: str, subset=None) -> float:
        rows = [q for q in per_q if subset is None or q["type"] == subset]
        return round(mean([q[field] for q in rows]), 4)

    types = sorted({q["type"] for q in per_q})
    return {
        "mode": mode,
        "k": k,
        "candidates": candidates,
        "n": len(per_q),
        "hit@1": agg("hit@1"),
        "hit@3": agg("hit@3"),
        "hit@5": agg("hit@5"),
        f"hit@{k}": agg(f"hit@{k}"),
        "mrr": agg("rr"),
        "ndcg": agg("ndcg"),
        "p@5": agg("p@5"),
        "page_hit@5": agg("page_hit@5"),
        "cross_doc_docs_covered": agg("docs_covered", "cross_doc") if "cross_doc" in types else None,
        "by_type": {
            t: {"n": sum(1 for q in per_q if q["type"] == t), "hit@5": agg("hit@5", t), "mrr": agg("rr", t)}
            for t in types
        },
        "latency_ms": {s: round(mean(v), 1) for s, v in stage_ms.items()},
        "per_question": per_q,
    }


def write_markdown(report: dict, path: Path) -> None:
    k = report["k"]
    modes = report["modes"]
    lines = [
        f"# Retrieval evaluation — {report['timestamp'][:10]} (`{report['git_sha']}`{', ' + report['tag'] if report.get('tag') else ''})",
        "",
        f"Corpus: {report['corpus']['documents']} documents, {report['corpus']['chunks']} chunks · "
        f"gold: {report['coverage']['answerable']} answerable questions · "
        f"chunk coverage {report['coverage']['coverage']:.1%} "
        f"(evidence for {report['coverage']['covered']}/{report['coverage']['answerable']} questions exists in some chunk)",
        "",
        f"Embeddings `{report['embedding_model']}` · reranker `{report['reranker']}` · first stage top-{report['candidates']} → top-{k}",
        "",
        f"| mode | hit@1 | hit@3 | hit@5 | hit@{k} | MRR@{k} | nDCG@{k} | P@5 | latency (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, r in modes.items():
        lines.append(
            f"| {m} | {r['hit@1']:.3f} | {r['hit@3']:.3f} | {r['hit@5']:.3f} | {r[f'hit@{k}']:.3f} | "
            f"{r['mrr']:.3f} | {r['ndcg']:.3f} | {r['p@5']:.3f} | {r['latency_ms'].get('total', 0):.0f} |"
        )
    lines += [
        "",
        "## By question type (hit@5 / MRR)",
        "",
        "| type | n | " + " | ".join(modes) + " |",
        "|---|---|" + "---|" * len(modes),
    ]
    types = sorted({t for r in modes.values() for t in r["by_type"]})
    for t in types:
        n = next(r["by_type"][t]["n"] for r in modes.values() if t in r["by_type"])
        cells = [
            f"{r['by_type'][t]['hit@5']:.2f} / {r['by_type'][t]['mrr']:.2f}" if t in r["by_type"] else "–"
            for r in modes.values()
        ]
        lines.append(f"| {t} | {n} | " + " | ".join(cells) + " |")
    if report["coverage"]["uncovered_ids"]:
        lines += [
            "",
            f"Uncovered by chunking (no chunk contains the evidence): {', '.join(report['coverage']['uncovered_ids'])}",
        ]
    lines += [
        "",
        "Relevance = retrieved chunk contains a gold evidence quote. Latency is mean per query on this machine, models warm.",
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    from finsight.rag.retrieval import MODES

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=list(MODES))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--candidates", type=int, default=20)
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    os.environ.setdefault("SECRET_KEY", "eval")
    from sqlmodel import Session, select

    from finsight import config
    from finsight.database.session import engine
    from finsight.models import DocumentChunk

    gold = load_gold(args.gold)
    with Session(engine) as session:
        key_by_id = doc_key_by_id(session)
        if not key_by_id:
            raise SystemExit("no seeded documents found — run `python -m scripts.seed_demo` first")
        n_chunks = len(session.exec(select(DocumentChunk)).all())
        coverage = corpus_coverage(session, gold, key_by_id)
        print(f"corpus: {len(key_by_id)} docs, {n_chunks} chunks · coverage {coverage['coverage']:.1%}")

        modes: dict[str, dict] = {}
        for mode in args.modes:
            # warm-up so model load time is not charged to the first query
            from finsight.rag.retrieval import retrieve

            retrieve(session, "warm up", mode=mode, top_k=1, candidates=5)
            t0 = time.time()
            modes[mode] = evaluate_mode(session, gold, mode, args.k, args.candidates, key_by_id)
            r = modes[mode]
            print(
                f"{mode:14s} hit@1 {r['hit@1']:.3f}  hit@5 {r['hit@5']:.3f}  MRR {r['mrr']:.3f}  nDCG {r['ndcg']:.3f}  "
                f"{r['latency_ms'].get('total', 0):.0f} ms/q  ({time.time() - t0:.0f}s)"
            )

    report = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "tag": args.tag,
        "k": args.k,
        "candidates": args.candidates,
        "embedding_model": config.EMBEDDING_MODEL,
        "reranker": "BAAI/bge-reranker-base",
        "corpus": {"documents": len(key_by_id), "chunks": n_chunks},
        "coverage": coverage,
        "modes": modes,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = args.tag or datetime.now().strftime("%Y-%m-%d")
    out = RESULTS / f"retrieval_{name}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    write_markdown(report, RESULTS / "retrieval_latest.md")
    print(f"wrote {out.relative_to(ROOT)} and eval/results/retrieval_latest.md")


if __name__ == "__main__":
    main()
