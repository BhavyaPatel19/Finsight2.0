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
from finsight.verification.claims import candidate_sentences, extract_claims
from finsight.verification.evidence import actuals_documents, find_evidence
from finsight.verification.verdict import judge_claim

logger = logging.getLogger(__name__)

SCORE = {"MET": 1.0, "PARTIAL": 0.5, "MISSED": 0.0}


def _parallel() -> int:
    return 1 if get_provider().name == "ollama" else 4


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
    claims = await extract_claims(cands, model=model, parallel=parallel)
    logger.info("WTT v2: %d claims extracted", len(claims))
    if not claims:
        return None

    # Stage 2 — evidence from all documents of the actuals period, then a verdict per claim
    doc_ids = actuals_documents(session, actuals_doc)
    sem = asyncio.Semaphore(parallel)

    async def one(claim):
        evidence = find_evidence(session, claim, doc_ids)
        async with sem:
            v = await judge_claim(claim, evidence, model=model)
        return claim, v, evidence

    results = await asyncio.gather(*(one(c) for c in claims))

    rows = []
    for claim, v, _ in results:
        rows.append(
            {
                **claim.to_dict(),
                "verdict": v.verdict,
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
