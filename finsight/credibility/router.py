from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.credibility.schemas import CredibilityScoreResponse
from finsight.credibility.service import (
    get_credibility_history,
    compute_credibility_for_symbol_period,
    extract_claims_for_document,
)

router = APIRouter()


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
    claims = extract_claims_for_document(session, document_id)
    return {"count": len(claims)}
