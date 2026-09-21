from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.ingestion.access import get_accessible_document, visible_documents
from finsight.ingestion.file_manager import (
    delete_document,
    get_document_context,
)
from finsight.ingestion.service import (
    register_document,
)
from finsight.ingestion.uploads import MEDIA_TYPES, save_upload
from finsight.models import User

router = APIRouter()


@router.get("/documents")
def documents_list(
    symbol: str | None = None,
    doc_type: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return visible_documents(session, current_user, symbol=symbol, doc_type=doc_type)


@router.get("/documents/{document_id}")
def document_detail(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get full document details including chunk count and status."""
    get_accessible_document(session, current_user, document_id)
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
    doc = get_accessible_document(session, current_user, document_id)
    if not doc.pdf_path:
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
    get_accessible_document(session, current_user, document_id)
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
    """Parse, chunk and index a document (same route the Chat page's 'prepare' uses)."""
    from finsight.retrieval import index_document

    doc = get_accessible_document(session, current_user, document_id)
    if not doc.pdf_path:
        raise HTTPException(status_code=404, detail="Document has no file")
    result = index_document(session, document_id, force=True)
    session.refresh(doc)
    return {
        "document_id": doc.id,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error": doc.error_message,
        **{k: v for k, v in result.items() if k in ("chunks", "sentences", "total_pages", "seconds", "health")},
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
    """Upload a PDF/HTML/text filing; save to documents dir and register it (pending).

    Whatever the caller leaves blank — document type, quarter, year — is read from the file's
    first pages (finsight.corpus.detect); the response says what was detected and from what."""
    path = await save_upload(file, symbol=symbol, fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter)
    detected: dict = {}
    if str(path).lower().endswith(".pdf") and (
        not doc_type.strip() or doc_type == "quarterly" or not fiscal_quarter.strip() or not fiscal_year.strip()
    ):
        from finsight.corpus.detect import detect_metadata

        try:
            detected = detect_metadata(path)
        except Exception:  # noqa: BLE001 — detection is a convenience, never a reason to fail an upload
            detected = {}
    doc = register_document(
        session,
        user_id=current_user.id,
        symbol=symbol.strip().upper(),
        doc_type=(doc_type.strip() if doc_type.strip() and doc_type != "quarterly" else None)
        or detected.get("doc_type")
        or "quarterly",
        fiscal_quarter=fiscal_quarter.strip() or detected.get("fiscal_quarter"),
        fiscal_year=fiscal_year.strip() or detected.get("fiscal_year"),
        pdf_path=str(path),
    )
    return {
        "document_id": doc.id,
        "status": "pending",
        "doc_type": doc.doc_type,
        "fiscal_quarter": doc.fiscal_quarter,
        "fiscal_year": doc.fiscal_year,
        "detected": {
            k: detected.get(k) for k in ("doc_type", "fiscal_quarter", "fiscal_year", "company_name", "evidence")
        }
        if detected
        else None,
    }
