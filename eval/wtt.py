"""
Walk-the-Talk evaluation: does the pipeline find management's forward-looking
claims, and does it grade them the way a human did?

    python -m eval.wtt                # all labelled pairs
    python -m eval.wtt --tag groq     # label the run

For every (claims document → actuals document) pair in eval/gold/wtt_claims.jsonl
the production walk_the_talk() pipeline runs once; each human-labelled claim is
then matched to the closest system claim (similarity ≥ 0.45) and compared.

Reported:
    claim_recall       labelled claims the system extracted at all
    verdict_accuracy   MET / MISSED / PARTIAL agreement on matched claims
    kappa              Cohen's κ vs the human labels (chance-corrected)
    system_claims      how many claims the system produced per pair (precision is
                       not measured: only labelled claims have ground truth)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold" / "wtt_claims.jsonl"
RESULTS = ROOT / "eval" / "results"
MATCH_THRESHOLD = 0.45

_STOP = set(
    "the a an of to in for and or is are was were be been our we it its this that on at by with as from will".split()
)


def tokens(text: str) -> tuple[set[str], set[str]]:
    """(content stems, numeric tokens). 'FY26'/'FY2026'/"'26" normalise to a year token."""
    text = re.sub(r"\[.*?\]", " ", text.lower())
    text = re.sub(r"\bfy\s?'?(\d{2,4})", r"\1", text)  # fy26, fy 2026 -> 26 / 2026
    text = re.sub(r"'(\d{2})\b", r"\1", text)  # '26 -> 26
    words, nums = set(), set()
    for tok in re.findall(r"[a-z0-9%.,]+", text):
        tok = tok.strip(".,")
        if not tok or tok in _STOP:
            continue
        if re.fullmatch(r"[\d.,]+%?", tok):
            nums.add(tok.replace(",", ""))
        elif len(tok) > 2:
            words.add(tok[:5])  # light stemming: guidance/guides, margins/margin, expects/expected
    return words, nums


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def similarity(a: str, b: str) -> float:
    """Overlap coefficient on content stems, blended 50/50 with overlap on numbers when both sides have any."""
    wa, na = tokens(a)
    wb, nb = tokens(b)
    words = _overlap(wa, wb)
    if words < 0.2:
        return (
            0.0  # a shared year or figure is not a match ("EBITDA neutral by June 2025" vs "groundwork by July 2025")
        )
    if na and nb:
        return 0.5 * words + 0.5 * _overlap(na, nb)
    if na or nb:  # one side has numbers the other lacks: penalise
        return 0.7 * words
    return words


def match_claims(gold: list[dict], system: list[dict]) -> list[dict]:
    """Greedy best-match of each gold claim to an unused system claim."""
    used: set[int] = set()
    out = []
    for g in gold:
        best, best_i = 0.0, None
        for i, s in enumerate(system):
            if i in used:
                continue
            sim = similarity(g["claim"], s.get("claim", ""))
            if sim > best:
                best, best_i = sim, i
        if best_i is not None and best >= MATCH_THRESHOLD:
            used.add(best_i)
            sys_claim = system[best_i]
            out.append(
                {
                    "id": g["id"],
                    "matched": True,
                    "similarity": round(best, 3),
                    "human": g["human_verdict"],
                    "system": str(sys_claim.get("verdict", "")).upper(),
                    "system_claim": sys_claim.get("claim"),
                    "system_explanation": sys_claim.get("explanation"),
                    "category": g["category"],
                }
            )
        else:
            out.append(
                {
                    "id": g["id"],
                    "matched": False,
                    "similarity": round(best, 3),
                    "human": g["human_verdict"],
                    "system": None,
                    "category": g["category"],
                }
            )
    return out


def summarise(rows: list[dict], system_counts: dict[str, int]) -> dict:
    from eval.metrics import cohen_kappa, mean

    matched = [r for r in rows if r["matched"]]
    abstained = [r for r in matched if r["system"] == "UNVERIFIABLE"]
    should_abstain = [r for r in matched if r["human"] == "UNVERIFIABLE"]
    agree = [r for r in matched if r["system"] == r["human"]]
    answered = [r for r in matched if r["system"] != "UNVERIFIABLE" and r["human"] != "UNVERIFIABLE"]
    agree_answered = [r for r in answered if r["system"] == r["human"]]
    kappa = None
    if len(matched) >= 2:
        try:
            kappa = round(cohen_kappa([r["human"] for r in matched], [r["system"] for r in matched]), 4)
        except ValueError:
            kappa = None
    confusion: dict[str, dict[str, int]] = {}
    for r in matched:
        confusion.setdefault(r["human"], {}).setdefault(r["system"], 0)
        confusion[r["human"]][r["system"]] += 1
    llm_errors = [r for r in matched if str(r.get("system_explanation") or "").startswith("LLM error")]
    return {
        "labelled": len(rows),
        "matched": len(matched),
        "llm_errors": len(
            llm_errors
        ),  # verdicts lost to provider errors (rate limits, quota) — a run with these is contaminated
        "claim_recall": round(len(matched) / len(rows), 4) if rows else None,
        "verdict_accuracy": round(len(agree) / len(matched), 4) if matched else None,
        "abstained": len(abstained),
        "verdict_accuracy_on_answered": round(len(agree_answered) / len(answered), 4) if answered else None,
        "abstain_recall": round(
            sum(1 for r in should_abstain if r["system"] == "UNVERIFIABLE") / len(should_abstain), 4
        )
        if should_abstain
        else None,
        "abstain_precision": round(sum(1 for r in abstained if r["human"] == "UNVERIFIABLE") / len(abstained), 4)
        if abstained
        else None,
        "kappa": kappa,
        "confusion": confusion,
        "system_claims": system_counts,
        "mean_match_similarity": round(mean([r["similarity"] for r in matched]), 3) if matched else None,
        "unmatched_ids": [r["id"] for r in rows if not r["matched"]],
    }


async def run_pair(session, claims_id: int, actuals_id: int, engine: str = "v1") -> tuple[list[dict], dict]:
    from finsight.models import Document

    if engine == "v2":
        from finsight.verification import verify

        result = await verify(session, claims_id, actuals_id)
    else:
        from finsight.credisentiment.pipeline import process_for_credisentiment
        from finsight.credisentiment.service import walk_the_talk

        for doc_id in (claims_id, actuals_id):
            doc = session.get(Document, doc_id)
            if doc.cs_status != "indexed":
                process_for_credisentiment(session, doc_id)
        result = await walk_the_talk(session, claims_id, actuals_id)
    if result is None:
        return [], {}
    claims = json.loads(result.claims_json or "[]")
    return claims, {"overall_score": result.overall_score, "narrative": result.narrative_summary}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="")
    ap.add_argument(
        "--engine", choices=["v1", "v2"], default="v2", help="v1 = credisentiment pipeline, v2 = finsight.verification"
    )
    ap.add_argument("--gold", type=Path, default=GOLD, help="labelled claims (default: the Infosys set)")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="document manifest the gold's document keys refer to (default: eval/gold/documents.json)",
    )
    args = ap.parse_args()

    os.environ.setdefault("SECRET_KEY", "eval")
    from sqlmodel import Session

    from eval.retrieval import doc_key_by_id, git_sha
    from finsight.database.session import engine
    from finsight.llm import get_provider

    gold = [json.loads(line) for line in args.gold.read_text().splitlines() if line.strip()]
    pairs = sorted({(g["claims_doc"], g["actuals_doc"]) for g in gold})
    provider = get_provider()
    print(f"{len(gold)} labelled claims across {len(pairs)} pairs; model {provider.default_model} via {provider.name}")

    rows, system_counts, pair_meta = [], {}, {}
    with Session(engine) as session:
        id_by_key = {
            v: k
            for k, v in (doc_key_by_id(session, args.manifest) if args.manifest else doc_key_by_id(session)).items()
        }
        for claims_key, actuals_key in pairs:
            label = f"{claims_key} → {actuals_key}"
            print(f"  running {label} …", flush=True)
            system, meta = asyncio.run(
                run_pair(session, id_by_key[claims_key], id_by_key[actuals_key], engine=args.engine)
            )
            system_counts[label] = len(system)
            pair_meta[label] = meta
            subset = [g for g in gold if (g["claims_doc"], g["actuals_doc"]) == (claims_key, actuals_key)]
            matched = match_claims(subset, system)
            rows.extend(matched)
            for r in matched:
                flag = "✓" if r["matched"] and r["system"] == r["human"] else ("✗" if r["matched"] else "–")
                print(
                    f"    {flag} {r['id']} human={r['human']:8s} system={r['system'] or 'not found':10s} sim={r['similarity']}"
                )

    report = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "tag": args.tag,
        "gold": str(args.gold.relative_to(ROOT)) if args.gold.is_relative_to(ROOT) else str(args.gold),
        "provider": provider.name,
        "model": provider.default_model,
        "engine": args.engine,
        "summary": summarise(rows, system_counts),
        "pairs": pair_meta,
        "rows": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    name = args.tag or f"{provider.name}-{datetime.now().strftime('%Y-%m-%d')}"
    (RESULTS / f"wtt_{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    s = report["summary"]
    print(json.dumps({k: v for k, v in s.items() if k != "confusion"}, indent=1))
    print("confusion (human → system):", json.dumps(s["confusion"]))
    print(f"wrote eval/results/wtt_{name}.json")


if __name__ == "__main__":
    main()
