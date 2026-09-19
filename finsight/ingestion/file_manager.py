"""
File Manager Service — single source of truth for document lifecycle.
Handles: registration, deduplication, download, processing, deletion.
Used by scraper, ingestion router, and any module needing document context.
"""
import os
from pathlib import Path

from sqlmodel import Session, select

from finsight.config import CHROMA_PERSIST_DIR, DOCUMENTS_DIR
from finsight.ingestion.parsers import chunk_text, extract_text_from_pdf
from finsight.models import Document, DocumentChunk
from finsight.rag.service import index_chunks_for_document
from finsight.rag.vectorstore import delete_by_document_id


def ensure_dirs() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)


def register_or_skip(
    session: Session,
    symbol: str,
    doc_type: str,
    source_url: str | None = None,
    company_name: str | None = None,
    **kwargs,
) -> tuple[Document, bool]:
    """Returns (document, is_new). If source_url already exists, returns existing doc with is_new=False."""
    if source_url:
        existing = session.exec(
            select(Document).where(Document.source_url == source_url)
        ).first()
        if existing:
            return existing, False

    doc = Document(
        symbol=symbol.upper(),
        doc_type=doc_type,
        source_url=source_url,
        company_name=company_name,
        status="pending",
        **kwargs,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc, True


def download_and_register(
    session: Session,
    url: str,
    symbol: str,
    doc_type: str,
    download_func,
    save_dir: str | None = None,
    company_name: str | None = None,
    fiscal_quarter: str | None = None,
    fiscal_year: str | None = None,
) -> Document | None:
    """Download a filing and register it. Returns Document or None on failure.
    download_func should be bse_scraper.download_filing or nse_scraper.download_nse_filing."""
    ensure_dirs()
    target_dir = save_dir or str(DOCUMENTS_DIR)

    # Check for existing document with same source_url
    doc, is_new = register_or_skip(
        session,
        symbol=symbol,
        doc_type=doc_type,
        source_url=url,
        company_name=company_name,
        fiscal_quarter=fiscal_quarter,
        fiscal_year=fiscal_year,
    )
    if not is_new:
        return doc

    # Update status to downloading
    doc.status = "downloading"
    session.add(doc)
    session.commit()

    try:
        filepath = download_func(url, target_dir)
        if not filepath:
            doc.status = "error"
            doc.error_message = "Download failed"
            session.add(doc)
            session.commit()
            return None

        doc.pdf_path = filepath
        doc.file_size = os.path.getsize(filepath) if os.path.exists(filepath) else None
        doc.status = "pending"  # Ready for processing
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc
    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return None


def process_document(session: Session, document_id: int) -> Document | None:
    """Extract text, chunk, and index to ChromaDB. Updates document status throughout."""
    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        return None

    doc.status = "processing"
    session.add(doc)
    session.commit()

    try:
        # Extract text
        text = extract_text_from_pdf(doc.pdf_path)
        if not text:
            doc.status = "error"
            doc.error_message = "No text extracted from PDF"
            session.add(doc)
            session.commit()
            return doc

        text_path = Path(doc.pdf_path).with_suffix(".txt")
        text_path.write_text(text, encoding="utf-8")
        doc.text_path = str(text_path)

        # Chunk
        chunks = chunk_text(text)
        created = []
        for i, c in enumerate(chunks):
            chunk = DocumentChunk(document_id=document_id, chunk_index=i, text=c)
            session.add(chunk)
            created.append(chunk)
        session.commit()

        # Index to ChromaDB
        index_chunks_for_document(session, document_id)

        doc.chunk_count = len(created)
        doc.status = "indexed"
        doc.error_message = None
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc
    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return doc


def delete_document(session: Session, document_id: int) -> dict:
    """Full cleanup: remove file from disk, chunks from DB, embeddings from ChromaDB, document row."""
    doc = session.get(Document, document_id)
    if not doc:
        return {"status": "not_found"}

    # 1. Remove embeddings from ChromaDB
    embeddings_deleted = 0
    try:
        embeddings_deleted = delete_by_document_id(document_id)
    except Exception:
        pass

    # 2. Delete DocumentChunk rows
    chunks = session.exec(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    ).all()
    for chunk in chunks:
        session.delete(chunk)

    # 3. Delete files from disk
    files_deleted = []
    if doc.pdf_path and os.path.exists(doc.pdf_path):
        try:
            os.remove(doc.pdf_path)
            files_deleted.append(doc.pdf_path)
        except Exception:
            pass
    if doc.text_path and os.path.exists(doc.text_path):
        try:
            os.remove(doc.text_path)
            files_deleted.append(doc.text_path)
        except Exception:
            pass

    # 4. Delete document row
    session.delete(doc)
    session.commit()

    return {
        "status": "deleted",
        "document_id": document_id,
        "chunks_deleted": len(chunks),
        "embeddings_deleted": embeddings_deleted,
        "files_deleted": files_deleted,
    }


def get_document_context(session: Session, document_id: int) -> dict | None:
    """Get document metadata with chunk/index status for cross-app use."""
    doc = session.get(Document, document_id)
    if not doc:
        return None

    chunk_count = len(
        session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).all()
    )

    return {
        "id": doc.id,
        "symbol": doc.symbol,
        "company_name": doc.company_name,
        "doc_type": doc.doc_type,
        "fiscal_quarter": doc.fiscal_quarter,
        "fiscal_year": doc.fiscal_year,
        "status": doc.status,
        "chunk_count": chunk_count,
        "file_size": doc.file_size,
        "ingested_at": doc.ingested_at.isoformat() if doc.ingested_at else None,
        "has_pdf": bool(doc.pdf_path and os.path.exists(doc.pdf_path)),
        "has_text": bool(doc.text_path),
    }
