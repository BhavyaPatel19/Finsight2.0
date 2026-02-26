from sqlmodel import Session, select

from finsight.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from finsight.models import DocumentChunk, Document
from finsight.rag.vectorstore import query as chroma_query, add_chunks, get_collection

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def embed(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text, convert_to_numpy=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts, convert_to_numpy=True).tolist()


def index_chunks_for_document(session: Session, document_id: int) -> int:
    """Load DocumentChunks for document_id, embed, add to Chroma. Returns count indexed."""
    doc = session.get(Document, document_id)
    if not doc:
        return 0
    stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    chunks = list(session.exec(stmt).all())
    if not chunks:
        return 0
    texts = [c.text for c in chunks]
    embeddings = embed_batch(texts)
    ids = []
    metadatas = []
    for c in chunks:
        ids.append(f"doc_{document_id}_chunk_{c.chunk_index}")
        metadatas.append({
            "symbol": doc.symbol or "",
            "doc_type": doc.doc_type or "",
            "fiscal_quarter": doc.fiscal_quarter or "",
            "fiscal_year": doc.fiscal_year or "",
            "document_id": document_id,
            "chunk_index": c.chunk_index,
        })
    add_chunks(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)
    return len(chunks)


def call_ollama(prompt: str, max_tokens: int = 1024) -> str:
    import httpx
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()
    except Exception as e:
        return f"[LLM error: {e}]"


def answer_question(
    session: Session,
    question: str,
    symbol: str | None = None,
    period: str | None = None,
    top_k: int = 8,
) -> tuple[str, list[dict]]:
    """Retrieve chunks, build prompt, call Ollama, return answer and sources."""
    q_emb = embed(question)
    where = None
    if symbol:
        where = {"symbol": symbol}
    if period:
        if where is None:
            where = {}
        where["fiscal_year"] = period  # or fiscal_quarter depending on format
    hits = chroma_query(q_emb, n_results=top_k, where=where)

    context_parts = []
    sources = []
    for i, h in enumerate(hits):
        meta = h.get("metadata") or {}
        context_parts.append(
            f"[{i+1}] (symbol={meta.get('symbol')}, doc_type={meta.get('doc_type')}, "
            f"quarter={meta.get('fiscal_quarter')}, year={meta.get('fiscal_year')})\n{h.get('text', '')}"
        )
        sources.append({
            "symbol": meta.get("symbol"),
            "doc_type": meta.get("doc_type"),
            "fiscal_quarter": meta.get("fiscal_quarter"),
            "fiscal_year": meta.get("fiscal_year"),
            "document_id": meta.get("document_id"),
            "chunk_index": meta.get("chunk_index"),
            "snippet": (h.get("text", ""))[:300],
        })

    context = "\n\n".join(context_parts) if context_parts else "No relevant context found."
    prompt = f"""Answer the question using ONLY the following context. If the context does not contain the answer, say so. Cite which source number [1], [2], etc. you use.

Context:
{context}

Question: {question}

Answer:"""

    answer = call_ollama(prompt)
    return answer, sources
