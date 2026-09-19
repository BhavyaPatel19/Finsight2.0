from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.ingestion.access import get_accessible_document, visible_documents
from finsight.llm import LLMError
from finsight.models import User
from finsight.rag.schemas import (
    AvailableDocument,
    NavigationStep,
    PrepareRequest,
    PrepareResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
)
from finsight.rag.service import answer_question, process_for_rag

router = APIRouter()


@router.get("/available-documents", response_model=list[AvailableDocument])
def get_available_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Documents this user may query (own uploads + shared corpus)."""
    docs = visible_documents(session, current_user)
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
        get_accessible_document(session, current_user, doc_id)
        results.append(process_for_rag(session, doc_id))
    return PrepareResponse(results=results)


@router.post("/query", response_model=RAGQueryResponse)
def rag_query(
    payload: RAGQueryRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Query against selected documents with navigation and thinking trace."""
    # Restrict retrieval to documents this user may see; an explicit selection
    # is validated, no selection means "everything visible to me".
    visible_ids = [d.id for d in visible_documents(session, current_user)]
    if payload.document_ids:
        document_ids = [i for i in payload.document_ids if i in visible_ids]
        if not document_ids:
            raise HTTPException(status_code=404, detail="Document not found")
    else:
        document_ids = visible_ids
    try:
        result = answer_question(
            session=session,
            question=payload.question,
            document_ids=document_ids,
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
