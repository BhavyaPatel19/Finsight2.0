"""
RAG service — hybrid BM25 + dense retrieval, cross-encoder reranking,
page-aware context, strict grounding prompt.
"""
import re

from sqlmodel import Session, select

from finsight.config import (
    EMBEDDING_MODEL,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
)
from finsight.llm import generate
from finsight.models import DocumentChunk, Document, PageMetadata, DocumentSection
from finsight.rag.vectorstore import (
    query as chroma_query,
    query_by_document_ids,
    add_chunks,
    delete_by_document_id,
)

_embedding_model = None

# ---------------------------------------------------------------------------
# Embeddings (BGE-base-en-v1.5)
# ---------------------------------------------------------------------------

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def embed_query(text: str) -> list[float]:
    """Embed a search query. BGE requires a query prefix for questions."""
    model = get_embedding_model()
    prefixed = f"Represent this sentence for searching relevant passages: {text}"
    return model.encode(prefixed, convert_to_numpy=True, normalize_embeddings=True).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks. BGE does NOT use a prefix for documents."""
    model = get_embedding_model()
    return model.encode(
        texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
    ).tolist()


# Keep old name for backward compat with legacy indexing
def embed(text: str) -> list[float]:
    return embed_query(text)

def embed_batch(texts: list[str]) -> list[list[float]]:
    return embed_documents(texts)


# ---------------------------------------------------------------------------
# Legacy index (kept for backward compat with old ingestion flow)
# ---------------------------------------------------------------------------

def index_chunks_for_document(session: Session, document_id: int) -> int:
    doc = session.get(Document, document_id)
    if not doc:
        return 0
    stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    chunks = list(session.exec(stmt).all())
    if not chunks:
        return 0
    texts = [c.text for c in chunks]
    embeddings = embed_documents(texts)
    ids = [f"doc_{document_id}_chunk_{c.chunk_index}" for c in chunks]
    metadatas = [{
        "symbol": doc.symbol or "",
        "doc_type": doc.doc_type or "",
        "fiscal_quarter": doc.fiscal_quarter or "",
        "fiscal_year": doc.fiscal_year or "",
        "document_id": document_id,
        "chunk_index": c.chunk_index,
        "page_number": 0,
        "section": "",
        "sub_section": "",
    } for c in chunks]
    add_chunks(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)
    return len(chunks)


# ---------------------------------------------------------------------------
# On-demand RAG processing
# ---------------------------------------------------------------------------

_DOC_TYPE_LABELS = {
    "concall": "earnings call transcript",
    "press_release": "results press release",
    "fact_sheet": "results fact sheet",
    "annual_report": "annual report",
    "quarterly": "quarterly results",
    "annual": "annual report",
}


def context_header(doc: Document) -> str:
    """Document-level context prepended to each chunk *for indexing only*.

    Corpora hold many near-identical filings from different periods; without
    this, an embedding cannot tell a Q4 FY25 call from a Q4 FY26 call.
    """
    parts = [doc.company_name or doc.symbol]
    if doc.company_name and doc.symbol:
        parts[0] = f"{doc.company_name} ({doc.symbol})"
    parts.append(_DOC_TYPE_LABELS.get(doc.doc_type or "", doc.doc_type or "document"))
    period = " ".join(x for x in (doc.fiscal_quarter, doc.fiscal_year) if x)
    if period:
        parts.append(period)
    return " · ".join(parts)


def text_for_index(header: str, chunk: dict) -> str:
    """What gets embedded / BM25-tokenised: header, section path, then the chunk."""
    lines = [header]
    section = chunk.get("section") or ""
    if section:
        sub = chunk.get("sub_section") or ""
        lines.append(f"{section} > {sub}" if sub else section)
    lines.append(chunk["text"])
    return "\n".join(lines)

def process_for_rag(session: Session, document_id: int) -> dict:
    """
    On-demand: extract structured text → page-aware chunks → embed → ChromaDB.
    Uses smart chunking (concall-aware).
    """
    from finsight.ingestion.parsers import extract_structured_document, chunk_smart

    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        return {"status": "error", "message": "Document or PDF not found"}

    if doc.status == "indexed":
        return {"status": "already_indexed", "document_id": document_id}

    doc.status = "processing"
    session.add(doc)
    session.commit()

    try:
        structured = extract_structured_document(doc.pdf_path)
        pages = structured["pages"]
        sections = structured["sections"]
        total_pages = structured["total_pages"]

        if not pages:
            doc.status = "error"
            doc.error_message = "No text extracted from PDF"
            session.add(doc)
            session.commit()
            return {"status": "error", "message": "No text extracted"}

        # Save PageMetadata rows
        for page_data in pages:
            if not page_data["text"]:
                continue
            pm = PageMetadata(
                document_id=document_id,
                page_number=page_data["page"],
                section_title=page_data.get("section"),
                sub_section_title=page_data.get("sub_section"),
                text=page_data["text"],
            )
            session.add(pm)

        # Save DocumentSection rows
        _save_sections(session, document_id, sections, parent_id=None)

        # Save full text
        full_text = "\n\n".join(p["text"] for p in pages if p["text"])
        from pathlib import Path
        if doc.pdf_path:
            text_path = Path(doc.pdf_path).with_suffix(".txt")
            text_path.write_text(full_text, encoding="utf-8")
            doc.text_path = str(text_path)

        # Smart chunking (concall-aware)
        chunks = chunk_smart(pages, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP)

        # Delete old chunks + ChromaDB entries
        old_chunks = session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        ).all()
        for oc in old_chunks:
            session.delete(oc)
        delete_by_document_id(document_id)

        # Save new DocumentChunk rows
        for chunk in chunks:
            dc = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
            )
            session.add(dc)
        session.commit()

        # Embed (with contextual header) and index to ChromaDB; stored text stays clean.
        header = context_header(doc)
        texts = [c["text"] for c in chunks]
        embeddings = embed_documents([text_for_index(header, c) for c in chunks])
        ids = [f"doc_{document_id}_chunk_{c['chunk_index']}" for c in chunks]
        metadatas = [{
            "symbol": doc.symbol or "",
            "doc_type": doc.doc_type or "",
            "fiscal_quarter": doc.fiscal_quarter or "",
            "fiscal_year": doc.fiscal_year or "",
            "document_id": document_id,
            "chunk_index": c["chunk_index"],
            "page_number": c.get("page_number", 0),
            "section": c.get("section") or "",
            "sub_section": c.get("sub_section") or "",
            "context_header": header,
        } for c in chunks]
        add_chunks(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)

        # Invalidate BM25 index (will rebuild on next query)
        from finsight.rag.bm25_store import invalidate_bm25
        invalidate_bm25()

        doc.status = "indexed"
        doc.chunk_count = len(chunks)
        doc.error_message = None
        session.add(doc)
        session.commit()

        return {
            "status": "indexed",
            "document_id": document_id,
            "total_pages": total_pages,
            "chunks": len(chunks),
            "sections": _count_sections(sections),
        }

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return {"status": "error", "message": str(e)[:500]}


def _save_sections(session, document_id, sections, parent_id):
    for sec in sections:
        ds = DocumentSection(
            document_id=document_id,
            title=sec["title"],
            level=sec["level"],
            parent_id=parent_id,
            start_page=sec["start_page"],
            end_page=sec.get("end_page"),
        )
        session.add(ds)
        session.flush()
        if sec.get("children"):
            _save_sections(session, document_id, sec["children"], parent_id=ds.id)


def _count_sections(sections):
    count = len(sections)
    for s in sections:
        if s.get("children"):
            count += _count_sections(s["children"])
    return count


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_deepseek_thinking(response: str) -> tuple[str, str | None]:
    """Extract <think>...</think> reasoning trace from DeepSeek-R1 output."""
    think_match = re.search(r"<think>(.*?)</think>", response, re.DOTALL)
    if think_match:
        thinking = think_match.group(1).strip()
        answer = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
        return answer, thinking
    return response, None


# ---------------------------------------------------------------------------
# Strict grounding prompt
# ---------------------------------------------------------------------------

FINANCIAL_RAG_PROMPT = """You are a financial analyst assistant. Your ONLY job is to answer questions using the document excerpts provided below.

STRICT RULES:
1. Answer ONLY using information present in the context below. Do not use any external knowledge.
2. Quote numbers EXACTLY as they appear in the source. Do not round or paraphrase figures.
3. For every fact you state, cite the source using this format: [Section: <section> > Page <page>]
4. If the information is not found in the context, respond with exactly: "Not found in the selected documents."
5. State units exactly as written in the source (crores, millions, %, basis points, etc.).

Context ({n} sections from {doc_count} document(s)):

{context}

Question: {question}

Answer with citations:"""


def _build_section_context(chunks: list[dict]) -> str:
    """Build structured context string grouped by section."""
    parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        page = meta.get("page_number", "?")
        section = meta.get("section", "")
        sub_section = meta.get("sub_section", "")
        symbol = meta.get("symbol", "")
        doc_type = meta.get("doc_type", "")
        fy = meta.get("fiscal_year", "")

        header = f"[{i+1}]"
        if symbol:
            header += f" {symbol}"
        if doc_type:
            header += f" · {doc_type}"
        if fy:
            header += f" · {fy}"
        if section:
            header += f" | {section}"
            if sub_section:
                header += f" > {sub_section}"
        header += f" | Page {page}"

        parts.append(f"{header}\n{chunk.get('text', '')}")
    return "\n\n---\n\n".join(parts) if parts else "No relevant context found."


# ---------------------------------------------------------------------------
# Main RAG query pipeline
# ---------------------------------------------------------------------------

def answer_question(
    session: Session,
    question: str,
    document_ids: list[int] | None = None,
    symbol: str | None = None,
    period: str | None = None,
    top_k: int = 8,
    model: str | None = None,
    retrieval_mode: str = "hybrid_rerank",
) -> dict:
    """
    Hybrid RAG pipeline:
    1-5. retrieve() — BGE dense + BM25 → RRF → cross-encoder rerank → top-k
    6.   Strict grounded prompt with section/page headers
    7.   LLM inference via the configured provider (Groq or Ollama)
    8.   Parse thinking trace + navigation breadcrumbs
    """
    from finsight.rag.retrieval import retrieve

    retrieved = retrieve(
        session, question,
        mode=retrieval_mode, top_k=top_k,
        document_ids=document_ids, symbol=symbol, period=period,
    )
    top_chunks = retrieved["chunks"]

    # 6. Build structured context
    context = _build_section_context(top_chunks)

    # 7. Format strict prompt
    unique_doc_ids = len({c.get("metadata", {}).get("document_id") for c in top_chunks})
    prompt = FINANCIAL_RAG_PROMPT.format(
        n=len(top_chunks),
        doc_count=unique_doc_ids,
        context=context,
        question=question,
    )

    # 8. Call LLM (raises LLMError if the provider is unavailable)
    response = generate(prompt, model=model, max_tokens=2048, temperature=0.0)
    model_name = response.model

    # 9. Parse thinking trace (reasoning models wrap it in <think> tags)
    answer, thinking = _parse_deepseek_thinking(response.text)

    # 10. Build navigation breadcrumbs (deduplicated)
    navigations = []
    seen = set()
    for chunk in top_chunks:
        meta = chunk.get("metadata", {})
        page_num = meta.get("page_number", 0)
        section = meta.get("section", "")
        sub_section = meta.get("sub_section", "")
        nav_key = f"{section}|{sub_section}|{page_num}"
        if nav_key not in seen:
            seen.add(nav_key)
            navigations.append({
                "section": section or None,
                "sub_section": sub_section or None,
                "page_number": page_num if isinstance(page_num, int) else 0,
                "snippet": chunk.get("text", "")[:200],
            })

    # 11. Build sources
    sources = []
    for chunk in top_chunks:
        meta = chunk.get("metadata", {})
        sources.append({
            "symbol": meta.get("symbol"),
            "doc_type": meta.get("doc_type"),
            "fiscal_quarter": meta.get("fiscal_quarter"),
            "fiscal_year": meta.get("fiscal_year"),
            "document_id": meta.get("document_id"),
            "chunk_index": meta.get("chunk_index"),
            "page_number": meta.get("page_number"),
            "section": meta.get("section"),
            "sub_section": meta.get("sub_section"),
            "snippet": chunk.get("text", "")[:300],
        })

    return {
        "answer": answer,
        "thinking": thinking,
        "navigations": navigations,
        "sources": sources,
        "context": [c.get("text", "") for c in top_chunks],  # full chunk texts (eval/judge; not in the API response)
        "model_used": model_name,
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "latency_ms": round(response.latency_ms, 1),
            "retrieval_ms": round(retrieved["timings_ms"]["total"], 1),
        },
    }
