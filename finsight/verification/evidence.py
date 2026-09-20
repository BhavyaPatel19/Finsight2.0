"""
Stage 2a: evidence for each claim, retrieved with the measured v2 engine
over every document of the actuals period (call + press release + fact
sheet), not just the one the user picked.
"""

from __future__ import annotations

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


def evidence_query(claim: Claim) -> str:
    parts = [claim.metric or "", claim.claim]
    if claim.period:
        parts.append(claim.period)
    return " ".join(p for p in parts if p)


def find_evidence(session: Session, claim: Claim, document_ids: list[int], top_k: int = 5) -> list[dict]:
    res = retrieve(
        session, evidence_query(claim), top_k=top_k, document_ids=document_ids, candidates=16, use_period=False
    )
    out = []
    for h in res["chunks"]:
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
