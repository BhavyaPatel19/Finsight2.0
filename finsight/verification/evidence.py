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

# Evidence for the same claim against the same period is retrieved once per process: the eval
# runs several pairs that share an actuals period, and the app re-runs a document pair when a
# user reopens it. Cleared by finsight.retrieval.index.invalidate() when the index changes.
_retrieval_cache: dict[tuple, dict] = {}
_CACHE_MAX = 2048


def clear_cache() -> None:
    _retrieval_cache.clear()


def _retrieve(session: Session, query: str, document_ids: list[int], **kw) -> dict:
    key = (query, tuple(sorted(document_ids)), tuple(sorted(kw.items())))
    hit = _retrieval_cache.get(key)
    if hit is None:
        if len(_retrieval_cache) >= _CACHE_MAX:
            _retrieval_cache.clear()
        hit = _retrieval_cache[key] = retrieve(session, query, document_ids=document_ids, **kw)
    return hit


def period_documents(session: Session, doc: Document) -> list[int]:
    """All indexed documents for the same symbol and period as `doc`."""
    stmt = select(Document).where(
        Document.symbol == doc.symbol,
        Document.fiscal_year == doc.fiscal_year,
        Document.fiscal_quarter == doc.fiscal_quarter,
        Document.status == "indexed",
    )
    ids = [d.id for d in session.exec(stmt).all()]
    return ids or [doc.id]


def actuals_documents(session: Session, actuals_doc: Document) -> list[int]:
    """All indexed documents for the same symbol and period as the chosen actuals document."""
    return period_documents(session, actuals_doc)


def is_directional(claim: Claim) -> bool:
    """A claim judged against where the metric stood when it was made ("improve margins from
    current levels", "third-party costs lower than FY25", "similar range") rather than against
    an absolute number: no target, a zero-change target, or a target expressed as a change."""
    t = claim.target
    if not t:
        return True
    unit = (t.get("unit") or "").lower()
    if any(w in unit for w in ("change", "reduction", "increase", "improvement", "lower", "higher", "vs")):
        return True
    return t.get("kind") in ("min", "max") and (t.get("value") or 0) == 0


def find_components(session: Session, claim: Claim, document_ids: list[int], top_k: int = 2) -> list[dict]:
    """For a ratio claim (effective tax rate, FCF conversion) the evidence must contain both
    figures a person would divide; ask the index for each component by name, rows first."""
    from finsight.verification.derived import ratio_for

    ratio = ratio_for(claim.metric)
    if not ratio:
        return []
    out: list[dict] = []
    for q in ratio.queries:
        res = _retrieve(
            session, f"{q} {claim.period or ''}", document_ids, top_k=top_k + 2, candidates=16, use_period=False
        )
        hits = sorted(
            res["chunks"],
            key=lambda h: (h["metadata"].get("kind") not in ("row", "table"), -(h.get("reranker_score") or 0.0)),
        )
        out.extend(_as_evidence(h) for h in hits[:top_k])
    return out


def find_baseline(session: Session, claim: Claim, document_ids: list[int], top_k: int = 3) -> list[dict]:
    """The metric as reported in the period the claim was made — the "current level" a
    directional claim is measured from. Same retrieval as the evidence, over the
    claims-period filings, keeping only blocks that report a figure."""
    hits = find_evidence(session, claim, document_ids, top_k=top_k + 3)
    return [h for h in hits if _NUMBERS.search(h["text"]) and outcome_weight(h["text"], h.get("kind")) >= 0.75][:top_k]


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
    r"\b(was|were|stood at|came in|reported|delivered|grew|declined|increased|decreased|reduced|closed|signed|onboarded|hired|achieved|improved|expanded|contracted|generated|returned|paid|crossed|remained|ended|recruited|dropped|fell|rose|halved|doubled|widened|narrowed|commissioned|decommissioned|started|completed|launched|produced|shut|received|placed|spent|invested|reached|recorded|posted|ramped|operated|commenced|secured|awarded)\b",
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
    res = _retrieve(session, evidence_query(claim), document_ids, top_k=top_k + 4, candidates=24, use_period=False)
    ranked = sorted(
        res["chunks"],
        key=lambda h: (h.get("reranker_score") or 0.0) * outcome_weight(h["text"], h["metadata"].get("kind")),
        reverse=True,
    )[:top_k]
    return [_as_evidence(h) for h in ranked]


def _as_evidence(h: dict) -> dict:
    m = h["metadata"]
    return {
        "id": h["id"],
        "text": m.get("display_text") or h["text"],  # rows as "label: column = value; …"
        "document_id": m.get("document_id"),
        "doc_type": m.get("doc_type"),
        "page": m.get("page_number"),
        "speaker": m.get("speaker") or None,
        "kind": m.get("kind"),
        "score": h.get("reranker_score"),
    }
