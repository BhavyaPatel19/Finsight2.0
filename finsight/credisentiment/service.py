"""
CrediSentiment service — combines:
  Feature 1: Division-level FinBERT sentiment analysis
  Feature 2: 'Walking the Talk' LLM credibility comparison
"""
import json
import re
from datetime import datetime

from sqlmodel import Session, select

from finsight.models import (
    Document,
    DivisionSentiment,
    WalkTheTalkResult,
    PageMetadata,
    DocumentSection,
)
from finsight.models import ComparisonChunk
from finsight.rag.service import process_for_rag, call_ollama_async
from finsight.credisentiment.prompts import (
    STAGE1_EXTRACT_CLAIMS_PROMPT,
    STAGE2_VERIFY_CLAIMS_PROMPT,
    strip_think_tags,
    parse_json_array,
    parse_json_object,
    deduplicate_claims,
)
from finsight.ml.finbert import analyze_batch, split_financial_sentences


# ---------------------------------------------------------------------------
# Feature 1 — Division-level FinBERT Sentiment
# ---------------------------------------------------------------------------

def _get_division_texts(session: Session, document_id: int) -> dict[str, str]:
    """
    Group document text by top-level section headings (divisions).
    Uses DocumentSection + PageMetadata tables populated during RAG indexing.
    Falls back to splitting the raw text by common heading patterns.
    """
    # Try structured sections first
    stmt = (
        select(DocumentSection)
        .where(
            DocumentSection.document_id == document_id,
            DocumentSection.level == 1,  # top-level sections only
        )
        .order_by(DocumentSection.start_page)
    )
    sections = list(session.exec(stmt).all())

    if sections:
        division_texts: dict[str, str] = {}
        for sec in sections:
            end_page = sec.end_page or sec.start_page + 5  # default span
            page_stmt = (
                select(PageMetadata)
                .where(
                    PageMetadata.document_id == document_id,
                    PageMetadata.page_number >= sec.start_page,
                    PageMetadata.page_number <= end_page,
                )
                .order_by(PageMetadata.page_number)
            )
            pages = list(session.exec(page_stmt).all())
            text = "\n".join(p.text for p in pages if p.text)
            if text.strip():
                division_texts[sec.title] = text
        if division_texts:
            return division_texts

    # Fallback: use PageMetadata section_title grouping
    page_stmt = (
        select(PageMetadata)
        .where(PageMetadata.document_id == document_id)
        .order_by(PageMetadata.page_number)
    )
    pages = list(session.exec(page_stmt).all())

    if pages:
        division_texts = {}
        for p in pages:
            key = p.section_title or "General"
            if key not in division_texts:
                division_texts[key] = ""
            division_texts[key] += "\n" + (p.text or "")
        # Filter out empty
        return {k: v.strip() for k, v in division_texts.items() if v.strip()}

    # Last resort: read raw text and split by headings
    doc = session.get(Document, document_id)
    if doc and doc.text_path:
        try:
            text = open(doc.text_path, encoding="utf-8").read()
        except Exception:
            return {"Full Document": text if 'text' in dir() else ""}
        # Split on lines that look like headings (ALL CAPS, short)
        parts = re.split(r"\n([A-Z][A-Z &/\-]{4,})\n", text)
        if len(parts) > 2:
            divisions = {}
            for i in range(1, len(parts), 2):
                heading = parts[i].strip()
                body = parts[i + 1] if i + 1 < len(parts) else ""
                if body.strip():
                    divisions[heading] = body.strip()
            if divisions:
                return divisions
        return {"Full Document": text[:15000]}

    return {}


def _run_finbert_on_text(text: str) -> dict:
    """Run FinBERT in batches of 32 with dynamic padding; return aggregated scores."""
    sentences = split_financial_sentences(text, min_length=15)
    sentences = sentences[:500]  # cap for performance
    if not sentences:
        sentences = [text[:512]]

    try:
        batch_results = analyze_batch(sentences, batch_size=32)
    except Exception:
        return {
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 0.0,
            "overall": 0.0,
            "count": 0,
        }

    n = len(batch_results)
    if n == 0:
        return {"positive": 0.0, "negative": 0.0, "neutral": 0.0, "overall": 0.0, "count": 0}

    pos_sum = sum(r["positive"] for r in batch_results)
    neg_sum = sum(r["negative"] for r in batch_results)
    neu_sum = sum(r["neutral"] for r in batch_results)

    return {
        "positive": round(pos_sum / n, 4),
        "negative": round(neg_sum / n, 4),
        "neutral": round(neu_sum / n, 4),
        "overall": round((pos_sum - neg_sum) / n, 4),
        "count": n,
    }


def analyze_division_sentiment(
    session: Session, document_id: int
) -> list[DivisionSentiment]:
    """
    Run FinBERT division-level sentiment on a document.
    Auto-indexes for RAG if not already done to get section structure.
    """
    doc = session.get(Document, document_id)
    if not doc:
        return []

    # Ensure document is RAG-indexed (populates PageMetadata / DocumentSection)
    if doc.status != "indexed":
        result = process_for_rag(session, document_id)
        if result.get("status") == "error":
            return []
        # Refresh doc
        session.refresh(doc)

    # Get text grouped by division
    division_texts = _get_division_texts(session, document_id)
    if not division_texts:
        # Fallback: whole document as single division
        if doc.text_path:
            try:
                full = open(doc.text_path, encoding="utf-8").read()
                division_texts = {"Full Document": full[:15000]}
            except Exception:
                return []

    # Delete old results for this document
    old = session.exec(
        select(DivisionSentiment).where(DivisionSentiment.document_id == document_id)
    ).all()
    for o in old:
        session.delete(o)
    session.commit()

    # Run FinBERT on each division
    results = []
    for div_name, text in division_texts.items():
        scores = _run_finbert_on_text(text)
        row = DivisionSentiment(
            document_id=document_id,
            symbol=doc.symbol,
            division_name=div_name,
            positive_score=scores["positive"],
            negative_score=scores["negative"],
            neutral_score=scores["neutral"],
            overall_score=scores["overall"],
            sentence_count=scores["count"],
        )
        session.add(row)
        results.append(row)

    session.commit()
    for r in results:
        session.refresh(r)

    return results


# ---------------------------------------------------------------------------
# Feature 2 — "Walking the Talk" LLM Comparison (Two-Stage Pipeline)
# ---------------------------------------------------------------------------


def get_document_chunks(session: Session, document_id: int) -> list[str]:
    """Load all CrediSentiment chunks for a document, ordered by chunk_index."""
    stmt = (
        select(ComparisonChunk)
        .where(ComparisonChunk.document_id == document_id)
        .order_by(ComparisonChunk.chunk_index)
    )
    chunks = list(session.exec(stmt).all())
    return [c.text for c in chunks]


async def walk_the_talk(
    session: Session,
    claims_document_id: int,
    actuals_document_id: int,
) -> WalkTheTalkResult | None:
    """
    Two-stage async pipeline using DeepSeek R1 LLM:
      Stage 1: Extract forward-looking claims from each ComparisonChunk
      Stage 2: Verify deduplicated claims against all actuals chunks
    """
    claims_doc = session.get(Document, claims_document_id)
    actuals_doc = session.get(Document, actuals_document_id)
    if not claims_doc or not actuals_doc:
        return None

    # Guard: both docs must be CrediSentiment-indexed
    if claims_doc.cs_status != "indexed" or actuals_doc.cs_status != "indexed":
        return None

    # Load ComparisonChunk texts (no truncation)
    claims_chunks = get_document_chunks(session, claims_document_id)
    actuals_chunks = get_document_chunks(session, actuals_document_id)
    if not claims_chunks or not actuals_chunks:
        return None

    # ------------------------------------------------------------------
    # Stage 1: Extract claims from each claims chunk (sequential)
    # ------------------------------------------------------------------
    all_claims: list[dict] = []
    for chunk_text in claims_chunks:
        prompt = STAGE1_EXTRACT_CLAIMS_PROMPT.format(chunk_text=chunk_text)
        raw = await call_ollama_async(prompt, max_tokens=2048)
        clean = strip_think_tags(raw)
        extracted = parse_json_array(clean)
        all_claims.extend(extracted)

    # Deduplicate overlapping claims across chunks
    unique_claims = deduplicate_claims(all_claims)

    if not unique_claims:
        return None

    # ------------------------------------------------------------------
    # Stage 2: Verify claims against actuals
    # ------------------------------------------------------------------
    actuals_text = "\n\n---\n\n".join(actuals_chunks)
    prompt = STAGE2_VERIFY_CLAIMS_PROMPT.format(
        claims_json=json.dumps(unique_claims, indent=2),
        actuals_text=actuals_text,
    )
    raw = await call_ollama_async(prompt, max_tokens=4096)
    clean = strip_think_tags(raw)
    result = parse_json_object(clean)

    # Extract results
    overall_score = float(result.get("overall_score", 50))
    claims_list = result.get("verified_claims", result.get("claims", []))
    narrative = result.get("narrative_summary", "No summary provided.")

    # ------------------------------------------------------------------
    # Persist: delete old results, save new
    # ------------------------------------------------------------------
    old = session.exec(
        select(WalkTheTalkResult).where(
            WalkTheTalkResult.claims_document_id == claims_document_id,
            WalkTheTalkResult.actuals_document_id == actuals_document_id,
        )
    ).all()
    for o in old:
        session.delete(o)
    session.commit()

    symbol = claims_doc.symbol or actuals_doc.symbol or "UNKNOWN"
    row = WalkTheTalkResult(
        claims_document_id=claims_document_id,
        actuals_document_id=actuals_document_id,
        symbol=symbol,
        overall_score=round(overall_score, 2),
        claims_json=json.dumps(claims_list),
        narrative_summary=narrative,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
