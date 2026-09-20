"""
RAG service — hybrid BM25 + dense retrieval, cross-encoder reranking,
page-aware context, strict grounding prompt.
"""

import re

from sqlmodel import Session, select

from finsight.config import (
    EMBEDDING_MODEL,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
)
from finsight.llm import generate
from finsight.models import Document, DocumentChunk, DocumentSection, PageMetadata
from finsight.rag.vectorstore import (
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
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False).tolist()


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
    metadatas = [
        {
            "symbol": doc.symbol or "",
            "doc_type": doc.doc_type or "",
            "fiscal_quarter": doc.fiscal_quarter or "",
            "fiscal_year": doc.fiscal_year or "",
            "document_id": document_id,
            "chunk_index": c.chunk_index,
            "page_number": 0,
            "section": "",
            "sub_section": "",
        }
        for c in chunks
    ]
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
    """Index a document for retrieval. Delegates to the v2 engine (finsight.retrieval)."""
    from finsight.retrieval import index_document

    return index_document(session, document_id)


def _process_for_rag_v1(session: Session, document_id: int) -> dict:
    """
    Legacy: extract structured text → page-aware chunks → embed → ChromaDB.
    Kept for the eval's like-for-like comparison (scripts/seed_demo.py --engine v1).
    """
    from finsight.ingestion.parsers import chunk_smart, extract_structured_document

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
        old_chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all()
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
        metadatas = [
            {
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
            }
            for c in chunks
        ]
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


def _normalize_output(text: str) -> str:
    """Undo typography some models add: CJK citation brackets (gpt-oss writes 【…】), narrow
    no-break spaces inside numbers, non-breaking hyphens and markdown bold around figures."""
    text = text.replace("【", "[").replace("】", "]")
    text = text.replace("\u202f", " ").replace("\u2011", "-")
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


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

FINANCIAL_RAG_PROMPT = """You are a financial analyst assistant. Answer the question using ONLY the excerpts below.

RULES
1. Use only the excerpts. No outside knowledge, no inference beyond what they state.
2. Copy numbers and units exactly as written (crores, millions, %, basis points).
3. Every fact carries a citation in this exact form: [<document type> <period>, Page <n>] — e.g. [earnings call transcript Q4 FY25, Page 3].
4. If no excerpt states the fact, the ANSWER line is exactly: Not found in the selected documents.
   The question may name a source (the call, the press release, the fact sheet). A missing source is NOT a reason to abstain: if another excerpt from the same period states the fact, answer from it and cite it — the citation shows where it came from.
5. Excerpts from different periods can look alike; check the period in each excerpt header before using it.

FORMAT — two sections, nothing else:
EVIDENCE:
- "<verbatim sentence or table row copied from an excerpt>" [citation]
- (1–4 lines; leave empty if nothing relevant)
ANSWER:
<1–3 sentences answering the question, each fact cited>

EXCERPTS ({n} from {doc_count} document(s)):

{context}

QUESTION (a source named here is a hint, not a filter — any excerpt from that period may answer it): {question}"""


_EVIDENCE_LINE = re.compile(r'^\s*[-•]\s*["“]?(.+?)["”]?\s*(\[[^\]]*\])?\s*$')


def parse_answer(raw: str) -> tuple[str, list[str]]:
    """Split the model output into (answer, [evidence quotes]). Tolerates missing sections."""
    text = raw.strip()
    m = re.search(r"EVIDENCE:\s*(.*?)\n\s*ANSWER:\s*(.*)$", text, re.S | re.I)
    if not m:
        m2 = re.search(r"ANSWER:\s*(.*)$", text, re.S | re.I)
        return (m2.group(1).strip() if m2 else text), []
    quotes = []
    for line in m.group(1).splitlines():
        lm = _EVIDENCE_LINE.match(line)
        if lm and lm.group(1).strip() and not lm.group(1).strip().startswith("("):
            quotes.append(lm.group(1).strip().strip('"“”'))
    return m.group(2).strip(), quotes


def verify_quotes(quotes: list[str], context_texts: list[str]) -> list[dict]:
    """Each quote is checked as a normalised substring of some retrieved chunk."""

    def norm(t: str) -> str:
        t = (
            t.replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("|", " ")
            .replace("\xa0", " ")
            .replace("\u202f", " ")  # narrow no-break space, e.g. "$14.9\u202fbillion" from gpt-oss
            .replace("\u2011", "-")  # non-breaking hyphen, e.g. "1.5%\u20113%"
            .replace("\u2013", "-")
        )
        t = re.sub(r"\s+", " ", t).strip().lower()
        return re.sub(r"\s+%", "%", t)  # "55 %" == "55%"

    ctx = [norm(c) for c in context_texts]
    out = []
    for q in quotes:
        nq = norm(q)
        found = bool(nq) and any(nq in c for c in ctx)
        out.append({"quote": q, "verified": found})
    return out


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

        header = f"[{i + 1}]"
        speaker = meta.get("speaker", "")
        label = _DOC_TYPE_LABELS.get(doc_type or "", doc_type or "document")
        period = " ".join(x for x in (meta.get("fiscal_quarter", ""), fy) if x)
        header += f" {label} {period}".rstrip()
        if symbol:
            header += f" ({symbol})"
        if section:
            header += f" | {section}"
            if sub_section:
                header += f" > {sub_section}"
        header += f" | Page {page}"
        if speaker:
            header += f" | Speaker: {speaker}"

        # Table rows are shown as "label: column = value; …" — the bare "1,428 | 1,345 | 5,872"
        # form left the model guessing which figure was the quarter and which the year.
        parts.append(f"{header}\n{meta.get('display_text') or chunk.get('text', '')}")
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
    retrieval_mode: str = "v2",
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
        session,
        question,
        mode=retrieval_mode,
        top_k=top_k,
        document_ids=document_ids,
        symbol=symbol,
        period=period,
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

    # 9. Parse thinking trace (reasoning models wrap it in <think> tags), then EVIDENCE / ANSWER
    raw, thinking = _parse_deepseek_thinking(_normalize_output(response.text))
    answer, quotes = parse_answer(raw)
    context_texts = [c.get("text", "") for c in top_chunks] + [
        c["metadata"]["display_text"] for c in top_chunks if c.get("metadata", {}).get("display_text")
    ]
    evidence = verify_quotes(quotes, context_texts)

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
            navigations.append(
                {
                    "section": section or None,
                    "sub_section": sub_section or None,
                    "page_number": page_num if isinstance(page_num, int) else 0,
                    "snippet": chunk.get("text", "")[:200],
                }
            )

    # 11. Build sources
    sources = []
    for chunk in top_chunks:
        meta = chunk.get("metadata", {})
        sources.append(
            {
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
            }
        )

    return {
        "answer": answer,
        "thinking": thinking,
        "navigations": navigations,
        "sources": sources,
        "context": context_texts,  # full chunk texts (eval/judge; not in the API response)
        "evidence": evidence,  # [{quote, verified}] — quotes the model copied, checked against the excerpts
        "model_used": model_name,
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "latency_ms": round(response.latency_ms, 1),
            "retrieval_ms": round(retrieved["timings_ms"]["total"], 1),
        },
    }
