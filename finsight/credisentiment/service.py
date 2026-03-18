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
from finsight.rag.service import process_for_rag, call_ollama
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
# Feature 2 — "Walking the Talk" LLM Comparison
# ---------------------------------------------------------------------------

WALK_THE_TALK_PROMPT = """You are a financial analyst auditing management credibility. You have two documents:

**CLAIMS DOCUMENT** (older — contains forward-looking statements, guidance, and promises):
{claims_text}

---

**ACTUALS DOCUMENT** (newer — contains actual financial results and outcomes):
{actuals_text}

---

{sentiment_context}

**TASK**: Compare the claims/promises from the Claims Document against the actual results in the Actuals Document. For each forward-looking claim you find:
1. What was claimed/promised (with the approximate value if numeric)
2. What actually happened (from the actuals document)
3. Whether the claim was MET, MISSED, or UNCLEAR
4. A brief explanation

Also provide an overall credibility score from 0-100 where:
- 90-100: Excellent — almost all promises met or exceeded
- 70-89: Good — majority of promises met
- 50-69: Mixed — some met, some missed
- 30-49: Poor — majority of promises missed
- 0-29: Very Poor — severe disconnect between claims and reality

**RESPOND ONLY WITH THIS EXACT JSON FORMAT (no other text)**:
{{
  "overall_score": <number 0-100>,
  "claims": [
    {{
      "claim": "<what was promised>",
      "category": "<revenue_growth|margin|debt|expansion|guidance|other>",
      "claimed_value": "<claimed figure or target>",
      "actual_value": "<actual result>",
      "met": <true|false|null>,
      "explanation": "<brief comparison>"
    }}
  ],
  "narrative_summary": "<2-3 sentence overall assessment of management credibility>"
}}"""


def walk_the_talk(
    session: Session,
    claims_document_id: int,
    actuals_document_id: int,
) -> WalkTheTalkResult | None:
    """
    Use DeepSeek R1 LLM to compare claims in one document against
    actuals in another document. Optionally uses FinBERT sentiment
    scores as additional context.
    """
    claims_doc = session.get(Document, claims_document_id)
    actuals_doc = session.get(Document, actuals_document_id)
    if not claims_doc or not actuals_doc:
        return None

    # Ensure both are indexed
    for doc in [claims_doc, actuals_doc]:
        if doc.status != "indexed":
            result = process_for_rag(session, doc.id)
            if result.get("status") == "error":
                return None
            session.refresh(doc)

    # Read texts
    claims_text = ""
    actuals_text = ""
    try:
        if claims_doc.text_path:
            claims_text = open(claims_doc.text_path, encoding="utf-8").read()[:8000]
        if actuals_doc.text_path:
            actuals_text = open(actuals_doc.text_path, encoding="utf-8").read()[:8000]
    except Exception:
        return None

    if not claims_text.strip() or not actuals_text.strip():
        return None

    # Check for existing FinBERT sentiment scores as context
    sentiment_context = ""
    from finsight.models import SentimentScore
    claims_sentiment = session.exec(
        select(SentimentScore).where(SentimentScore.document_id == claims_document_id)
    ).first()
    actuals_sentiment = session.exec(
        select(SentimentScore).where(SentimentScore.document_id == actuals_document_id)
    ).first()
    if claims_sentiment or actuals_sentiment:
        sentiment_context = "**FinBERT Sentiment Context**:\n"
        if claims_sentiment:
            sentiment_context += (
                f"- Claims document sentiment: overall={claims_sentiment.overall_score:.4f}, "
                f"optimism={claims_sentiment.optimism_index or 0:.4f}, "
                f"risk_tone={claims_sentiment.risk_tone_index or 0:.4f}\n"
            )
        if actuals_sentiment:
            sentiment_context += (
                f"- Actuals document sentiment: overall={actuals_sentiment.overall_score:.4f}, "
                f"optimism={actuals_sentiment.optimism_index or 0:.4f}, "
                f"risk_tone={actuals_sentiment.risk_tone_index or 0:.4f}\n"
            )
        sentiment_context += "\nUse these sentiment scores as additional context when evaluating credibility.\n"

    # Build prompt
    prompt = WALK_THE_TALK_PROMPT.format(
        claims_text=claims_text,
        actuals_text=actuals_text,
        sentiment_context=sentiment_context,
    )

    # Call LLM
    raw = call_ollama(prompt, max_tokens=2048)

    # Strip <think>...</think> tags from DeepSeek R1
    clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Parse JSON response
    overall_score = 50.0
    claims_list = []
    narrative = "Analysis could not be completed."

    try:
        # Find JSON in response
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(clean[start:end])
            overall_score = float(parsed.get("overall_score", 50))
            claims_list = parsed.get("claims", [])
            narrative = parsed.get("narrative_summary", "No summary provided.")
    except (json.JSONDecodeError, ValueError):
        narrative = f"LLM response could not be parsed. Raw output: {clean[:500]}"

    # Delete old results for this combination
    old = session.exec(
        select(WalkTheTalkResult).where(
            WalkTheTalkResult.claims_document_id == claims_document_id,
            WalkTheTalkResult.actuals_document_id == actuals_document_id,
        )
    ).all()
    for o in old:
        session.delete(o)
    session.commit()

    # Save result
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
