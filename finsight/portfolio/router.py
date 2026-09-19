from fastapi import APIRouter, Depends
from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.portfolio.schemas import HoldingMetric, InsightSummary, PortfolioMetrics
from finsight.portfolio.service import get_holdings_with_metrics, get_portfolio_insights

router = APIRouter()


@router.get("/holdings", response_model=PortfolioMetrics)
def holdings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rows = get_holdings_with_metrics(session, current_user.id)
    total = sum((r.get("current_price") or r.get("avg_price", 0)) * r.get("quantity", 0) for r in rows)
    return PortfolioMetrics(
        holdings=[HoldingMetric(**r) for r in rows],
        total_value=total,
    )


@router.get("/insights", response_model=InsightSummary)
def insights(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return get_portfolio_insights(session, current_user.id)
