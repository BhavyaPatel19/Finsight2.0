from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from finsight.credibility.fundamentals import fetch_and_score
from finsight.credibility.schemas import CredibilityScoreResponse, FundamentalsScoreResponse
from finsight.credibility.service import (
    compute_credibility_for_symbol_period,
    extract_claims_for_document,
    get_credibility_history,
)
from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.ingestion.access import get_accessible_document
from finsight.models import User

router = APIRouter()


@router.get("/score/{symbol}", response_model=FundamentalsScoreResponse)
def fundamentals_score(
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """Get credibility score for a symbol based on live financial fundamentals."""
    result = fetch_and_score(symbol.upper())
    fundamentals = result.get("fundamentals") or {}
    return FundamentalsScoreResponse(
        symbol=result["symbol"],
        score=result["score"],
        pe=fundamentals.get("pe"),
        roce=fundamentals.get("roce"),
        debt_to_equity=fundamentals.get("debt_to_equity"),
        revenue_growth=fundamentals.get("revenue_growth"),
        promoter_holding=fundamentals.get("promoter_holding"),
        market_cap=fundamentals.get("market_cap"),
        book_value=fundamentals.get("book_value"),
        dividend_yield=fundamentals.get("dividend_yield"),
        source=fundamentals.get("source", "screener.in"),
    )


@router.get("/{symbol}", response_model=list[CredibilityScoreResponse])
def credibility_history(
    symbol: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return get_credibility_history(session, symbol)


@router.post("/recompute/{symbol}/{period}", response_model=CredibilityScoreResponse)
def recompute(
    symbol: str,
    period: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = compute_credibility_for_symbol_period(session, symbol, period)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No claims or actuals found for this symbol/period",
        )
    return result


@router.post("/extract-claims/{document_id}")
def extract_claims(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    get_accessible_document(session, current_user, document_id)
    claims = extract_claims_for_document(session, document_id)
    return {"count": len(claims)}

