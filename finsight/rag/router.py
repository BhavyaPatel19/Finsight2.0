from fastapi import APIRouter, Depends

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.rag.schemas import RAGQueryRequest, RAGQueryResponse, RAGSource
from finsight.rag.service import answer_question

router = APIRouter()


@router.post("/query", response_model=RAGQueryResponse)
def rag_query(
    payload: RAGQueryRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    answer, sources = answer_question(
        session=session,
        question=payload.question,
        symbol=payload.symbol,
        period=payload.period,
        top_k=payload.top_k,
    )
    return RAGQueryResponse(
        answer=answer,
        sources=[RAGSource(**s) for s in sources],
    )
