from pathlib import Path
from datetime import datetime

from sqlmodel import Session, select

from finsight.config import DOCUMENTS_DIR, CHROMA_PERSIST_DIR
from finsight.models import Document, DocumentChunk
from finsight.models.enums import DocType
from finsight.ingestion.parsers import extract_text_from_pdf, chunk_text


def ensure_dirs() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)


def register_document(
    session: Session,
    symbol: str,
    doc_type: str,
    fiscal_quarter: str | None = None,
    fiscal_year: str | None = None,
    source_url: str | None = None,
    pdf_path: str | None = None,
) -> Document:
    doc = Document(
        symbol=symbol,
        doc_type=doc_type,
        fiscal_quarter=fiscal_quarter,
        fiscal_year=fiscal_year,
        source_url=source_url,
        pdf_path=pdf_path,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def extract_and_chunk_document(session: Session, document_id: int) -> list[DocumentChunk]:
    """Extract text from PDF, chunk, and save DocumentChunk rows. Caller adds to Chroma."""
    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        return []
    text = extract_text_from_pdf(doc.pdf_path)
    if not text:
        return []
    text_path = Path(doc.pdf_path).with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    doc.text_path = str(text_path)
    session.add(doc)
    session.commit()

    chunks = chunk_text(text)
    created = []
    for i, c in enumerate(chunks):
        chunk = DocumentChunk(document_id=document_id, chunk_index=i, text=c)
        session.add(chunk)
        created.append(chunk)
    session.commit()
    for ch in created:
        session.refresh(ch)
    return created


def list_documents(
    session: Session,
    symbol: str | None = None,
    doc_type: str | None = None,
) -> list[Document]:
    stmt = select(Document)
    if symbol:
        stmt = stmt.where(Document.symbol == symbol)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    stmt = stmt.order_by(Document.ingested_at.desc())
    return list(session.exec(stmt).all())
