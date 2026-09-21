"""
Walk the Talk v2 orchestration.

    result = await verify(session, claims_document_id, actuals_document_id)

Both documents must be indexed by the v2 engine. Persists a WalkTheTalkResult
whose claims_json carries, per claim: claim, quote, category, metric, period,
target, verdict, actual_value, evidence quote/page/doc, explanation, method.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from sqlmodel import Session, select

from finsight.config import WTT_MODEL
from finsight.llm import LLMError, agenerate, get_provider
from finsight.models import Document, WalkTheTalkResult
from finsight.retrieval import index as ix
from finsight.verification.claims import EXTRACT_PROMPT, Claim, candidate_sentences, extract_claims, last_extraction
from finsight.verification.evidence import (
    actuals_documents,
    find_baseline,
    find_components,
    find_evidence,
    is_directional,
    period_documents,
)
from finsight.verification.verdict import confidence, judge_claim

logger = logging.getLogger(__name__)

SCORE = {"MET": 1.0, "PARTIAL": 0.5, "MISSED": 0.0}


def latest_reported_period(session: Session, doc_ids: list[int]) -> tuple[int, int] | None:
    """(fy, quarter) of the most recent actuals document, from Document.fiscal_year/fiscal_quarter."""
    import re

    best = None
    for d in session.exec(select(Document).where(Document.id.in_(doc_ids))).all():  # type: ignore[attr-defined]
        m = re.search(r"(\d{2,4})", d.fiscal_year or "")
        if not m:
            continue
        fy = int(m.group(1)) % 100
        q = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get((d.fiscal_quarter or "Q4").upper(), 4)
        if best is None or (fy, q) > best:
            best = (fy, q)
    return best


def _parallel() -> int:
    name = get_provider().name
    if name == "ollama":
        return 1  # one model slot
    if name == "cerebras":
        return 1  # ~4k-token verdict prompts against 150k tokens/min: two in flight trade 429s for minute-long waits
    return 4


# Claims extracted from a document do not depend on the actuals document, so the eval's three
# pairs that start from the same call and a user comparing one call with several later periods
# pay for extraction once. Keyed on the prompt too, so a prompt change is never served stale.
_claims_cache: dict[tuple, list[Claim]] = {}
# What the last verify() cost and lost — read by the eval so a contaminated run is visible.
last_run = {"extraction_batches": 0, "extraction_failed": 0, "verdict_errors": 0, "claims_from_cache": False}


def clear_cache() -> None:
    _claims_cache.clear()


def overall_score(verdicts: list[str]) -> float | None:
    graded = [SCORE[v] for v in verdicts if v in SCORE]
    return round(sum(graded) / len(graded) * 100, 1) if graded else None


async def verify(
    session: Session, claims_document_id: int, actuals_document_id: int, *, model: str | None = None
) -> WalkTheTalkResult | None:
    claims_doc = session.get(Document, claims_document_id)
    actuals_doc = session.get(Document, actuals_document_id)
    if not claims_doc or not actuals_doc:
        return None
    model = model or WTT_MODEL or None
    parallel = _parallel()

    # Stage 1 — claims from every prose chunk of the claims document
    chunks = [c for c in ix.all_chunks() if c["metadata"].get("document_id") == claims_document_id]
    if not chunks:
        return None
    cands = candidate_sentences(chunks)
    logger.info("WTT v2: %d candidate sentences from %d chunks", len(cands), len(chunks))
    key = (claims_document_id, model, hash(EXTRACT_PROMPT), claims_doc.chunk_count, str(claims_doc.ingested_at))
    claims = _claims_cache.get(key)
    last_run.update(extraction_batches=0, extraction_failed=0, verdict_errors=0, claims_from_cache=claims is not None)
    if claims is None:
        claims = await extract_claims(cands, model=model, parallel=parallel)
        last_run.update(extraction_batches=last_extraction["batches"], extraction_failed=last_extraction["failed"])
        if claims and not last_extraction["failed"]:
            _claims_cache[key] = claims
    else:
        logger.info("WTT v2: claims for document %d served from cache", claims_document_id)
    logger.info("WTT v2: %d claims extracted", len(claims))
    if not claims:
        return None

    # Stage 2 — evidence from all documents of the actuals period, then a verdict per claim
    doc_ids = actuals_documents(session, actuals_doc)
    latest = latest_reported_period(session, doc_ids)
    sem = asyncio.Semaphore(parallel)

    baseline_ids = period_documents(session, claims_doc)

    async def one(claim):
        evidence = find_evidence(session, claim, doc_ids)
        seen = {e["id"] for e in evidence}
        evidence += [e for e in find_components(session, claim, doc_ids) if e["id"] not in seen]
        baseline = find_baseline(session, claim, baseline_ids) if is_directional(claim) else None
        async with sem:
            v = await judge_claim(claim, evidence, model=model, latest_reported=latest, baseline=baseline)
        return claim, v, evidence

    results = await asyncio.gather(*(one(c) for c in claims))

    rows = []
    for claim, v, evidence in results:
        level, reasons = confidence(v, claim, evidence)
        rows.append(
            {
                **claim.to_dict(),
                "verdict": v.verdict,
                "confidence": level,
                "confidence_reasons": reasons,
                "actual_value": v.actual_value,
                "actual_number": v.actual_number,
                "evidence_quote": v.evidence_quote,
                "evidence_page": v.evidence_page,
                "evidence_doc_type": v.evidence_doc_type,
                "evidence_id": v.evidence_id,
                "explanation": v.explanation,
                "method": v.method,
                # legacy fields the UI reads
                "claimed_value": _target_str(claim.target),
                "met": {"MET": True, "MISSED": False}.get(v.verdict),
            }
        )
    last_run["verdict_errors"] = sum(1 for r in rows if str(r.get("explanation") or "").startswith("LLM error"))
    verdicts = [r["verdict"] for r in rows]
    score = overall_score(verdicts)
    counts = {k: verdicts.count(k) for k in ("MET", "PARTIAL", "MISSED", "UNVERIFIABLE")}

    narrative = await _narrative(rows, score, counts, model)

    for old in session.exec(
        select(WalkTheTalkResult).where(
            WalkTheTalkResult.claims_document_id == claims_document_id,
            WalkTheTalkResult.actuals_document_id == actuals_document_id,
        )
    ).all():
        session.delete(old)
    result = WalkTheTalkResult(
        claims_document_id=claims_document_id,
        actuals_document_id=actuals_document_id,
        symbol=claims_doc.symbol,
        overall_score=score if score is not None else 0.0,
        claims_json=json.dumps(rows, ensure_ascii=False),
        narrative_summary=narrative,
        computed_at=datetime.utcnow(),
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def _target_str(t: dict | None) -> str | None:
    if not t:
        return None
    u = t.get("unit") or ""
    if t["kind"] == "range":
        return f"{t['low']}–{t['high']} {u}".strip()
    return f"{ {'min': '≥', 'max': '≤', 'point': '≈'}[t['kind']] }{t['value']} {u}".strip()


async def _narrative(rows: list[dict], score: float | None, counts: dict, model: str | None) -> str:
    lines = [
        f"- [{r['verdict']}] {r['claim']} → {r['actual_value'] or 'not verifiable from the filings'}" for r in rows[:25]
    ]
    prompt = (
        "Write a 2–3 sentence assessment of management credibility from these verified commitments. "
        "Mention the score and what was and was not delivered; say plainly how many could not be verified. No JSON.\n\n"
        f"Score: {score if score is not None else 'n/a'}/100 over {sum(counts[k] for k in ('MET', 'PARTIAL', 'MISSED'))} verifiable claims; "
        f"MET {counts['MET']}, PARTIAL {counts['PARTIAL']}, MISSED {counts['MISSED']}, UNVERIFIABLE {counts['UNVERIFIABLE']}.\n"
        + "\n".join(lines)
    )
    try:
        resp = await agenerate(prompt, model=model, max_tokens=300, temperature=0.2, think=False)
        text = resp.text.strip().strip('"')
        if text:
            return text
    except LLMError as e:
        logger.warning("narrative failed: %s", e)
    return (
        f"Credibility score {score if score is not None else 'n/a'}/100: {counts['MET']} met, {counts['PARTIAL']} partial, "
        f"{counts['MISSED']} missed, {counts['UNVERIFIABLE']} not verifiable from the filings."
    )
