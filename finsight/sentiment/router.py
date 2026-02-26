from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.sentiment.schemas import SentimentScoreResponse
from finsight.sentiment.service import get_sentiment_history, compute_sentiment_for_document

router = APIRouter()


@router.get("/{symbol}", response_model=list[SentimentScoreResponse])
def sentiment_history(
    symbol: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return get_sentiment_history(session, symbol)


@router.post("/recompute/{document_id}", response_model=SentimentScoreResponse)
def recompute(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = compute_sentiment_for_document(session, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found or no text")
    return result
