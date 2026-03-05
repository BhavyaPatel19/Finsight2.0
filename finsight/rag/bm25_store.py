"""
In-memory BM25 index built from DocumentChunk rows.
Rebuilt lazily on first query after invalidation.
"""
import re

_bm25_index = None
_bm25_corpus: list[dict] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


def build_bm25_index(session) -> None:
    """Load all DocumentChunk rows from DB and build BM25Okapi index."""
    global _bm25_index, _bm25_corpus
    from rank_bm25 import BM25Okapi
    from sqlmodel import select
    from finsight.models import DocumentChunk, Document

    chunks = list(session.exec(select(DocumentChunk)).all())
    if not chunks:
        _bm25_index = None
        _bm25_corpus = []
        return

    doc_cache: dict[int, Document] = {}
    corpus = []
    for chunk in chunks:
        if chunk.document_id not in doc_cache:
            doc = session.get(Document, chunk.document_id)
            doc_cache[chunk.document_id] = doc
        doc = doc_cache[chunk.document_id]
        corpus.append({
            "id": f"doc_{chunk.document_id}_chunk_{chunk.chunk_index}",
            "text": chunk.text,
            "metadata": {
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "symbol": doc.symbol if doc else "",
                "doc_type": doc.doc_type if doc else "",
                "fiscal_year": doc.fiscal_year if doc else "",
                "fiscal_quarter": doc.fiscal_quarter if doc else "",
                "page_number": 0,
                "section": "",
                "sub_section": "",
            },
        })

    tokenized = [_tokenize(item["text"]) for item in corpus]
    _bm25_index = BM25Okapi(tokenized)
    _bm25_corpus = corpus


def bm25_search(
    query: str,
    n_results: int = 30,
    document_ids: list[int] | None = None,
) -> list[dict]:
    """
    Search the BM25 index. Returns [{text, metadata, bm25_score}, ...] sorted by score.
    Optionally filtered to specific document_ids.
    """
    global _bm25_index, _bm25_corpus
    if _bm25_index is None or not _bm25_corpus:
        return []

    tokens = _tokenize(query)
    scores = _bm25_index.get_scores(tokens)

    results = []
    for item, score in zip(_bm25_corpus, scores):
        if document_ids and item["metadata"]["document_id"] not in document_ids:
            continue
        if score <= 0:
            continue
        results.append({
            "text": item["text"],
            "metadata": item["metadata"],
            "bm25_score": float(score),
            "distance": None,
        })

    results.sort(key=lambda x: x["bm25_score"], reverse=True)
    return results[:n_results]


def invalidate_bm25() -> None:
    """Invalidate the BM25 index so it rebuilds on the next query."""
    global _bm25_index
    _bm25_index = None


def is_built() -> bool:
    return _bm25_index is not None
