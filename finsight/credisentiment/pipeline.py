"""
CrediSentiment processing pipeline.

Section-aware chunking (3500-char / 500-overlap) and process orchestrator
that writes ComparisonChunk rows + credisentiment_docs embeddings.

Independent from RAG pipeline -- never imports or touches RAG status.
"""

from pathlib import Path

from sqlmodel import Session, select

from finsight.config import CREDISENTIMENT_CHUNK_OVERLAP, CREDISENTIMENT_CHUNK_SIZE
from finsight.credisentiment.vectorstore import add_chunks, delete_by_document_id
from finsight.ingestion.parsers import extract_structured_document
from finsight.models import ComparisonChunk, Document
from finsight.rag.service import embed_documents

# ---------------------------------------------------------------------------
# Section-aware chunking
# ---------------------------------------------------------------------------

def _find_paragraph_break(text: str, target: int) -> int:
    """
    Search backward from *target* for a paragraph break (``\\n\\n``).
    Returns the position right after the break, or *target* if none found
    within a reasonable window (25 % of target).
    """
    window = max(target // 4, 200)
    search_start = max(0, target - window)
    idx = text.rfind("\n\n", search_start, target)
    if idx != -1:
        return idx + 2  # skip past the two newlines
    return target


def chunk_for_credisentiment(
    pages: list[dict],
    chunk_size: int = CREDISENTIMENT_CHUNK_SIZE,
    overlap: int = CREDISENTIMENT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Section-aware chunking for CrediSentiment.

    * Flushes the buffer at section boundaries when buffer > 30 % of chunk_size.
    * Size-based flush when buffer >= chunk_size (finds paragraph break).
    * Keeps *overlap* chars carried over between consecutive chunks.

    Returns list of chunk dicts with keys:
        text, page_number, section, sub_section, chunk_index
    """
    chunks: list[dict] = []
    chunk_idx = 0

    buffer = ""
    buffer_page: int = 1
    buffer_section: str | None = None
    buffer_sub: str | None = None

    def _flush(text: str):
        nonlocal chunk_idx
        text = text.strip()
        if not text:
            return
        chunks.append({
            "text": text,
            "page_number": buffer_page,
            "section": buffer_section,
            "sub_section": buffer_sub,
            "chunk_index": chunk_idx,
        })
        chunk_idx += 1

    for page in pages:
        page_text = page.get("text", "")
        if not page_text:
            continue

        current_section = page.get("section")
        current_sub = page.get("sub_section")
        page_num = page.get("page", 1)

        # Section boundary detection
        if (
            buffer
            and current_section != buffer_section
            and len(buffer) > chunk_size * 0.3
        ):
            _flush(buffer)
            buffer = ""

        # If buffer is empty, adopt the new page's metadata
        if not buffer:
            buffer_page = page_num
            buffer_section = current_section
            buffer_sub = current_sub

        buffer += page_text

        # Size-based flush
        while len(buffer) >= chunk_size:
            break_pos = _find_paragraph_break(buffer, chunk_size)
            _flush(buffer[:break_pos])
            # Keep overlap
            keep_from = max(0, break_pos - overlap)
            buffer = buffer[keep_from:]
            buffer_page = page_num
            buffer_section = current_section
            buffer_sub = current_sub

    # Flush remaining
    if buffer.strip():
        _flush(buffer)

    return chunks


# ---------------------------------------------------------------------------
# Process orchestrator
# ---------------------------------------------------------------------------

def process_for_credisentiment(session: Session, document_id: int) -> dict:
    """
    On-demand CrediSentiment processing:
      extract structured text -> section-aware chunks -> embed -> ChromaDB.

    Writes ComparisonChunk rows and credisentiment_docs embeddings.
    Does NOT touch RAG status, RAG chunks, or finsight_docs collection.
    """
    doc = session.get(Document, document_id)

    # Guard: missing document or PDF
    if not doc or not doc.pdf_path:
        return {"status": "error", "document_id": document_id, "message": "Document or PDF not found"}

    # Guard: already processed
    if doc.cs_status == "indexed":
        return {"status": "already_indexed", "document_id": document_id}

    doc.cs_status = "processing"
    session.add(doc)
    session.commit()

    try:
        structured = extract_structured_document(doc.pdf_path)
        pages = structured["pages"]

        if not pages:
            doc.cs_status = "error"
            doc.cs_error_message = "No text extracted from PDF"
            session.add(doc)
            session.commit()
            return {"status": "error", "document_id": document_id, "message": "No text extracted from PDF"}

        # Save full text if not already set
        if doc.pdf_path and not doc.text_path:
            try:
                full_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
                text_path = Path(doc.pdf_path).with_suffix(".txt")
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(full_text, encoding="utf-8")
                doc.text_path = str(text_path)
            except OSError:
                pass  # Non-critical: text file is convenience, not required

        # Section-aware chunking
        cs_chunks = chunk_for_credisentiment(pages)

        # Delete old ComparisonChunk rows
        old_chunks = session.exec(
            select(ComparisonChunk).where(ComparisonChunk.document_id == document_id)
        ).all()
        for oc in old_chunks:
            session.delete(oc)

        # Delete old ChromaDB entries
        delete_by_document_id(document_id)

        # Save new ComparisonChunk rows
        chroma_ids: list[str] = []
        for c in cs_chunks:
            cid = f"cs_{document_id}_chunk_{c['chunk_index']}"
            chroma_ids.append(cid)
            cc = ComparisonChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                text=c["text"],
                page_number=c.get("page_number"),
                section=c.get("section"),
                sub_section=c.get("sub_section"),
                chroma_id=cid,
            )
            session.add(cc)
        session.commit()

        # Embed chunks
        texts = [c["text"] for c in cs_chunks]
        embeddings = embed_documents(texts)

        # Store in ChromaDB
        metadatas = [
            {
                "document_id": document_id,  # int, not str
                "chunk_index": c["chunk_index"],
                "page_number": c.get("page_number") or 0,
                "section": c.get("section") or "",
                "sub_section": c.get("sub_section") or "",
                "symbol": doc.symbol or "",
                "doc_type": doc.doc_type or "",
                "fiscal_quarter": doc.fiscal_quarter or "",
                "fiscal_year": doc.fiscal_year or "",
            }
            for c in cs_chunks
        ]
        add_chunks(ids=chroma_ids, texts=texts, metadatas=metadatas, embeddings=embeddings)

        # Update document status
        doc.cs_status = "indexed"
        doc.cs_chunk_count = len(cs_chunks)
        doc.cs_error_message = None
        session.add(doc)
        session.commit()

        return {
            "status": "indexed",
            "document_id": document_id,
            "chunks": len(cs_chunks),
        }

    except Exception as e:
        doc.cs_status = "error"
        doc.cs_error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return {"status": "error", "document_id": document_id, "message": str(e)[:500]}
