from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Document
from finsight.rag.schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
    NavigationStep,
    PrepareRequest,
    PrepareResponse,
    AvailableDocument,
)
from finsight.llm import LLMError
from finsight.rag.service import answer_question, process_for_rag

router = APIRouter()


@router.get("/available-documents", response_model=list[AvailableDocument])
def get_available_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return all documents for the document picker in RAG tab."""
    stmt = select(Document).order_by(Document.ingested_at.desc())
    docs = list(session.exec(stmt).all())
    return [
        AvailableDocument(
            id=d.id,
            symbol=d.symbol,
            doc_type=d.doc_type,
            company_name=d.company_name,
            fiscal_quarter=d.fiscal_quarter,
            fiscal_year=d.fiscal_year,
            status=d.status,
            chunk_count=d.chunk_count or 0,
            file_size=d.file_size,
        )
        for d in docs
    ]


@router.post("/prepare", response_model=PrepareResponse)
def prepare_documents(
    payload: PrepareRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Process selected documents for RAG on-demand.
    Extracts text, builds page-aware chunks, embeds, and indexes to ChromaDB.
    Only processes documents not already indexed.
    """
    results = []
    for doc_id in payload.document_ids:
        result = process_for_rag(session, doc_id)
        results.append(result)
    return PrepareResponse(results=results)


@router.post("/query", response_model=RAGQueryResponse)
def rag_query(
    payload: RAGQueryRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Query against selected documents with navigation and thinking trace."""
    try:
        result = answer_question(
            session=session,
            question=payload.question,
            document_ids=payload.document_ids,
            symbol=payload.symbol,
            period=payload.period,
            top_k=payload.top_k,
            model=payload.model,
        )
    except LLMError as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {e}") from e
    return RAGQueryResponse(
        answer=result["answer"],
        thinking=result.get("thinking"),
        navigations=[NavigationStep(**n) for n in result.get("navigations", [])],
        sources=[RAGSource(**s) for s in result.get("sources", [])],
        model_used=result.get("model_used", ""),
    )
