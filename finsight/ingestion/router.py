from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Document
from finsight.config import DOCUMENTS_DIR
from finsight.ingestion.service import (
    list_documents,
    register_document,
    ensure_dirs,
)
from finsight.ingestion.scheduler import scheduled_fetch_documents
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
    """Serve the document PDF for viewing."""
    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        raise HTTPException(status_code=404, detail="Document or PDF not found")
    pdf_path = Path(doc.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
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
    """Upload a PDF; save to documents dir, register, extract text, chunk, and index to Chroma."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF file required")
    if not symbol.strip():
        raise HTTPException(status_code=400, detail="symbol required")
    ensure_dirs()
    import uuid
    path = DOCUMENTS_DIR / f"{symbol}_{fiscal_year or 'na'}_{fiscal_quarter or 'na'}_{uuid.uuid4().hex[:8]}_{file.filename}"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    path.write_bytes(content)
    doc = register_document(
        session,
        symbol=symbol.strip(),
        doc_type=doc_type.strip() or "quarterly",
        fiscal_quarter=fiscal_quarter.strip() or None,
        fiscal_year=fiscal_year.strip() or None,
        pdf_path=str(path),
    )
    return {"document_id": doc.id, "status": "pending"}


@router.post("/run")
def run_ingestion(
    current_user: User = Depends(get_current_user),
):
    """Trigger scheduled fetch manually (admin/convenience)."""
    scheduled_fetch_documents()
    return {"status": "triggered"}
