"""
Stage 2a: evidence for each claim, retrieved with the measured v2 engine
over every document of the actuals period (call + press release + fact
sheet), not just the one the user picked.
"""

from __future__ import annotations

import re

from sqlmodel import Session, select

from finsight.models import Document
from finsight.retrieval.search import retrieve
from finsight.verification.claims import Claim


def actuals_documents(session: Session, actuals_doc: Document) -> list[int]:
    """All indexed documents for the same symbol and period as the chosen actuals document."""
    stmt = select(Document).where(
        Document.symbol == actuals_doc.symbol,
        Document.fiscal_year == actuals_doc.fiscal_year,
        Document.fiscal_quarter == actuals_doc.fiscal_quarter,
        Document.status == "indexed",
    )
    ids = [d.id for d in session.exec(stmt).all()]
    return ids or [actuals_doc.id]


_GUIDANCE_WORDS = re.compile(
    r"\b(guidance|guide[sd]?|expect(s|ed|ing)?|anticipate[sd]?|target(s|ed|ing)?|aim(s|ed)?|outlook|forecast|plan(s|ned|ning)?|"
    r"intend(s|ed)?|endeavou?r|commit(s|ted)?|will|shall|should|the company|we|our)\b",
    re.I,
)
_NUMBERS = re.compile(r"[-–]?\$?\d[\d,]*(\.\d+)?\s*(%|bps|bn|mn|crore|x)?", re.I)


def evidence_query(claim: Claim) -> str:
    """Ask for the outcome, not the promise: metric + period + outcome words, with the
    guidance vocabulary and the target numbers removed so the next period's restated
    guidance does not outrank the actual."""
    core = _NUMBERS.sub(" ", _GUIDANCE_WORDS.sub(" ", claim.claim))
    core = re.sub(r"\s+", " ", core).strip(" .,:;")
    parts = [claim.metric or "", claim.period or "", core, "actual reported was stood at"]
    return " ".join(p for p in parts if p)


_OUTCOME = re.compile(
    r"\b(was|were|stood at|came in|reported|delivered|grew|declined|increased|decreased|reduced|closed|signed|onboarded|hired|"
    r"achieved|improved|expanded|contracted|generated|returned|paid|crossed|remained|ended)\b",
    re.I,
)
_FORWARD = re.compile(
    r"\b(expect(s|ed)?|guidance|guide|will|shall|target(s)?|aim|outlook|plan(s|ned)?|anticipate|forecast)\b", re.I
)


def outcome_weight(text: str, kind: str | None) -> float:
    """Prefer evidence that reports what happened over evidence that promises again.
    Table rows are results by nature; prose is weighed by outcome vs forward-looking verbs."""
    if kind in ("row", "table"):
        return 1.0
    fwd = len(_FORWARD.findall(text))
    out = len(_OUTCOME.findall(text))
    if out == 0 and fwd > 0:
        return 0.5
    if fwd > out:
        return 0.75
    return 1.0


def find_evidence(session: Session, claim: Claim, document_ids: list[int], top_k: int = 8) -> list[dict]:
    res = retrieve(
        session, evidence_query(claim), top_k=top_k + 4, document_ids=document_ids, candidates=24, use_period=False
    )
    ranked = sorted(
        res["chunks"],
        key=lambda h: (h.get("reranker_score") or 0.0) * outcome_weight(h["text"], h["metadata"].get("kind")),
        reverse=True,
    )[:top_k]
    out = []
    for h in ranked:
        m = h["metadata"]
        out.append(
            {
                "id": h["id"],
                "text": h["text"],
                "document_id": m.get("document_id"),
                "doc_type": m.get("doc_type"),
                "page": m.get("page_number"),
                "speaker": m.get("speaker") or None,
                "kind": m.get("kind"),
                "score": h.get("reranker_score"),
            }
        )
    return out
