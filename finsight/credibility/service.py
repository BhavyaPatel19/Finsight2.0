from sqlmodel import Session, select

from finsight.llm import generate
from finsight.models import CredibilityScore, Document, ExtractedClaim, FinancialMetric


def extract_claims_for_document(session: Session, document_id: int) -> list[ExtractedClaim]:
    """Use LLM to extract forward-looking claims from document; save ExtractedClaim rows."""
    doc = session.get(Document, document_id)
    if not doc or not doc.text_path:
        return []
    from pathlib import Path

    text = Path(doc.text_path).read_text(encoding="utf-8")[:8000]
    if not text.strip():
        return []

    prompt = f"""From the following financial document excerpt, extract forward-looking numeric claims. For each claim, categorize as one of: revenue_growth, margin_expansion, debt_reduction, market_expansion. Return a JSON array of objects with keys: category, claim_period (e.g. FY25 or Q3FY26), claim_value (number), context_snippet (short quote). If none found, return [].

Document excerpt:
{text}

JSON array:"""
    try:
        raw = generate(prompt, max_tokens=512, temperature=0.0).text
        import json

        # Try to parse JSON from response (might be wrapped in markdown)
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            arr = json.loads(raw[start:end])
        else:
            arr = []
    except Exception:
        arr = []

    created = []
    for item in arr if isinstance(arr, list) else []:
        cat = (item.get("category") or "").strip().lower()
        if cat not in ("revenue_growth", "margin_expansion", "debt_reduction", "market_expansion"):
            continue
        claim = ExtractedClaim(
            document_id=document_id,
            symbol=doc.symbol,
            category=cat,
            claim_period=item.get("claim_period"),
            claim_value=item.get("claim_value"),
            context_snippet=item.get("context_snippet"),
        )
        session.add(claim)
        created.append(claim)
    session.commit()
    for c in created:
        session.refresh(c)
    return created


def compute_credibility_for_symbol_period(session: Session, symbol: str, period: str) -> CredibilityScore | None:
    """Compare extracted claims to actual FinancialMetric; compute deviation and score 0-100."""
    stmt = select(ExtractedClaim).where(
        ExtractedClaim.symbol == symbol,
        ExtractedClaim.claim_period == period,
    )
    claims = list(session.exec(stmt).all())
    if not claims:
        return None

    stmt = (
        select(FinancialMetric)
        .where(
            FinancialMetric.symbol == symbol,
            (FinancialMetric.fiscal_year == period) | (FinancialMetric.fiscal_quarter == period),
        )
        .limit(1)
    )
    metric = session.exec(stmt).first()
    if not metric:
        # No actuals: cannot compute
        return None

    deviations = []
    for c in claims:
        actual = None
        if c.category == "revenue_growth":
            actual = metric.revenue_growth
        elif c.category == "margin_expansion":
            actual = metric.margin
        elif c.category == "debt_reduction":
            actual = metric.debt
        elif c.category == "market_expansion":
            actual = metric.revenue_growth
        if actual is not None and c.claim_value is not None and c.claim_value != 0:
            dev = abs(c.claim_value - actual) / abs(c.claim_value)
            deviations.append(min(1.0, dev))

    if not deviations:
        return None
    avg_dev = sum(deviations) / len(deviations)
    score = max(0, 100 * (1 - avg_dev))

    row = CredibilityScore(
        symbol=symbol,
        period=period,
        score_0_100=round(score, 2),
        avg_deviation=round(avg_dev, 4),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_credibility_history(session: Session, symbol: str) -> list[CredibilityScore]:
    stmt = (
        select(CredibilityScore).where(CredibilityScore.symbol == symbol).order_by(CredibilityScore.computed_at.desc())
    )
    return list(session.exec(stmt).all())
