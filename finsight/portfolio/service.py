from sqlmodel import Session, select

from finsight.models import Holding, Portfolio, FinancialMetric
from finsight.zerodha.service import get_or_create_default_portfolio, get_holdings


def get_holdings_with_metrics(session: Session, user_id: int) -> list[dict]:
    """Holdings joined with financial metrics (P/E, ROCE, revenue_growth) where available."""
    holdings_list = get_holdings(session, user_id)
    out = []
    for h in holdings_list:
        stmt = (
            select(FinancialMetric)
            .where(FinancialMetric.symbol == h.symbol)
            .order_by(FinancialMetric.created_at.desc())
            .limit(1)
        )
        metric = session.exec(stmt).first()
        out.append({
            "symbol": h.symbol,
            "quantity": h.quantity,
            "avg_price": h.avg_price,
            "current_price": h.current_price,
            "pe": metric.pe if metric else None,
            "roce": metric.roce if metric else None,
            "revenue_growth": metric.revenue_growth if metric else None,
        })
    return out


def get_portfolio_insights(session: Session, user_id: int) -> dict:
    """Placeholder: portfolio-weighted credibility, low-credibility exposure, summary."""
    from finsight.models import CredibilityScore

    holdings_list = get_holdings(session, user_id)
    if not holdings_list:
        return {
            "portfolio_credibility_score": None,
            "low_credibility_exposure_pct": None,
            "sentiment_weighted_exposure": None,
            "summary": "No holdings.",
        }
    total_value = sum((h.current_price or h.avg_price) * h.quantity for h in holdings_list)
    if total_value == 0:
        total_value = 1
    weighted_cred = 0.0
    low_cred_value = 0.0
    for h in holdings_list:
        w = (h.current_price or h.avg_price) * h.quantity / total_value
        stmt = (
            select(CredibilityScore)
            .where(CredibilityScore.symbol == h.symbol)
            .order_by(CredibilityScore.computed_at.desc())
            .limit(1)
        )
        cred = session.exec(stmt).first()
        if cred:
            weighted_cred += w * cred.score_0_100
            if cred.score_0_100 < 50:
                low_cred_value += (h.current_price or h.avg_price) * h.quantity
    return {
        "portfolio_credibility_score": weighted_cred if weighted_cred else None,
        "low_credibility_exposure_pct": (low_cred_value / total_value) * 100 if total_value else None,
        "sentiment_weighted_exposure": None,
        "summary": None,
    }
