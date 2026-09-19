from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Document
from finsight.ingestion.service import (
    list_documents,
    register_document,
)
from finsight.ingestion.uploads import MEDIA_TYPES, save_upload
from finsight.ingestion.file_manager import (
    delete_document,
    get_document_context,
    process_document,
)

router = APIRouter()


@router.get("/documents")
def documents_list(
    symbol: str | None = None,
    doc_type: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return list_documents(session, symbol=symbol, doc_type=doc_type)


@router.get("/documents/{document_id}")
def document_detail(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get full document details including chunk count and status."""
    ctx = get_document_context(session, document_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Document not found")
    return ctx


@router.get("/documents/{document_id}/pdf")
def document_pdf(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Serve the source document (PDF or HTML) for viewing."""
    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        raise HTTPException(status_code=404, detail="Document or file not found")
    pdf_path = Path(doc.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(pdf_path),
        media_type=MEDIA_TYPES.get(pdf_path.suffix.lower(), "application/octet-stream"),
        filename=pdf_path.name,
    )


@router.delete("/documents/{document_id}")
def document_delete(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a document: removes file from disk, chunks from DB, embeddings from ChromaDB."""
    result = delete_document(session, document_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.post("/documents/{document_id}/process")
def document_process(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Extract text, chunk, and index a document to ChromaDB."""
    doc = process_document(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or no PDF")
    return {
        "document_id": doc.id,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error": doc.error_message,
    }


@router.post("/documents/upload")
async def upload_and_index(
    file: UploadFile = File(...),
    symbol: str = "",
    doc_type: str = "quarterly",
    fiscal_quarter: str = "",
    fiscal_year: str = "",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF/HTML/text filing; save to documents dir and register it (pending)."""
    path = await save_upload(file, symbol=symbol, fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter)
    doc = register_document(
        session,
        symbol=symbol.strip().upper(),
        doc_type=doc_type.strip() or "quarterly",
        fiscal_quarter=fiscal_quarter.strip() or None,
        fiscal_year=fiscal_year.strip() or None,
        pdf_path=str(path),
    )
    return {"document_id": doc.id, "status": "pending"}
