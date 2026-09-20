"""
CI gate: fail if a retrieval run is below the thresholds in eval/thresholds.json.

    python -m eval.gate eval/results/retrieval_ci.json --corpus html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(report: dict, thresholds: dict) -> list[str]:
    mode = thresholds["mode"]
    if mode not in report.get("modes", {}):
        return [f"mode {mode!r} not in report (have {list(report.get('modes', {}))})"]
    m = report["modes"][mode]
    failures = []
    for key in ("hit@1", "hit@5", "mrr"):
        if key in thresholds and m.get(key, 0) < thresholds[key]:
            failures.append(f"{mode} {key} = {m.get(key, 0):.3f} < {thresholds[key]:.3f}")
    if "coverage" in thresholds and report.get("coverage", {}).get("coverage", 0) < thresholds["coverage"]:
        failures.append(f"chunk coverage = {report['coverage']['coverage']:.3f} < {thresholds['coverage']:.3f}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("--corpus", choices=["html", "pdf"], default="html")
    args = ap.parse_args()
    thresholds = json.loads((ROOT / "eval" / "thresholds.json").read_text())[args.corpus]
    report = json.loads(args.report.read_text())
    m = report["modes"].get(thresholds["mode"], {})
    print(
        f"{args.corpus} corpus, mode {thresholds['mode']}: hit@1 {m.get('hit@1')}, hit@5 {m.get('hit@5')}, MRR {m.get('mrr')}, "
        f"coverage {report.get('coverage', {}).get('coverage')}"
    )
    failures = check(report, thresholds)
    if failures:
        print("GATE FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
