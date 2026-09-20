"""
Latency and cost.

    python -m eval.bench retrieval [--n 64] [--mode v2]    per-stage p50/p95 over the gold questions, models warm
    python -m eval.bench generation eval/results/generation_<tag>.json   tokens and cost per answer

Groq list prices (USD per 1M tokens) are a table here; local models cost 0.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# USD per 1M tokens (input, output). Update when Groq changes list prices.
GROQ_PRICES = {
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
}


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def bench_retrieval(mode: str, n: int) -> dict:
    os.environ.setdefault("SECRET_KEY", "bench")
    from sqlmodel import Session

    from eval.retrieval import load_gold
    from finsight.database.session import engine
    from finsight.rag.retrieval import retrieve

    gold = [g for g in load_gold() if g["answerable"]][:n]
    stages: dict[str, list[float]] = {}
    with Session(engine) as s:
        retrieve(s, "warm up", mode=mode, top_k=1, candidates=5)
        wall = []
        for g in gold:
            t0 = time.perf_counter()
            res = retrieve(s, g["question"], mode=mode, top_k=8)
            wall.append((time.perf_counter() - t0) * 1000)
            for k, v in res["timings_ms"].items():
                stages.setdefault(k, []).append(v)
    out = {
        "mode": mode,
        "n": len(gold),
        "wall_ms": {"p50": round(pct(wall, 50)), "p95": round(pct(wall, 95)), "mean": round(statistics.mean(wall))},
    }
    out["stages_ms"] = {k: {"p50": round(pct(v, 50)), "p95": round(pct(v, 95))} for k, v in stages.items()}
    return out


def bench_generation(path: Path) -> dict:
    r = json.loads(path.read_text())
    rows = [x for x in r["rows"] if "error" not in x and x.get("usage")]
    prompt = [x["usage"].get("prompt_tokens") or 0 for x in rows]
    comp = [x["usage"].get("completion_tokens") or 0 for x in rows]
    lat = [x["latency_ms"] for x in rows]
    model = r.get("model", "")
    price = GROQ_PRICES.get(model)
    cost = None
    if price:
        cost = [(p * price[0] + c * price[1]) / 1e6 for p, c in zip(prompt, comp, strict=True)]
    return {
        "model": model,
        "provider": r.get("provider"),
        "n": len(rows),
        "prompt_tokens": {"mean": round(statistics.mean(prompt)) if prompt else 0, "p95": round(pct(prompt, 95))},
        "completion_tokens": {"mean": round(statistics.mean(comp)) if comp else 0, "p95": round(pct(comp, 95))},
        "latency_ms": {"p50": round(pct(lat, 50)), "p95": round(pct(lat, 95))},
        "usd_per_answer": {"mean": round(statistics.mean(cost), 5), "per_1000": round(sum(cost) / len(cost) * 1000, 2)}
        if cost
        else "n/a (local model)",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("retrieval")
    p.add_argument("--mode", default="v2")
    p.add_argument("--n", type=int, default=64)
    p = sub.add_parser("generation")
    p.add_argument("path", type=Path)
    args = ap.parse_args()
    out = bench_retrieval(args.mode, args.n) if args.what == "retrieval" else bench_generation(args.path)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
