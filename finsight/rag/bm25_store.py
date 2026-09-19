"""
In-memory BM25 index over the chunks in ChromaDB (same ids + metadata as
dense retrieval). Rebuilt lazily on first query after invalidation.
"""
import re

_bm25_index = None
_bm25_corpus: list[dict] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\b\w+\b', text.lower())


def build_bm25_index(session=None) -> None:
    """Build BM25Okapi over the chunks stored in ChromaDB.

    Reading the same collection dense retrieval uses guarantees identical
    chunk ids and metadata (page_number, section, ...) for both retrievers;
    the earlier DocumentChunk-based build stored page_number=0 for every
    BM25 hit, so citations lost their page whenever BM25 found the chunk.
    """
    global _bm25_index, _bm25_corpus
    from rank_bm25 import BM25Okapi

    from finsight.rag.vectorstore import get_collection

    coll = get_collection()
    got = coll.get(include=["documents", "metadatas"])
    ids = got.get("ids") or []
    if not ids:
        _bm25_index = None
        _bm25_corpus = []
        return

    corpus = [
        {"id": cid, "text": text or "", "metadata": dict(meta or {})}
        for cid, text, meta in zip(ids, got["documents"], got["metadatas"], strict=True)
    ]
    # Index the same contextual header the embeddings saw (company, doc type, period).
    tokenized = [
        _tokenize(f"{item['metadata'].get('context_header', '')} {item['text']}") for item in corpus
    ]
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
    for item, score in zip(_bm25_corpus, scores, strict=True):
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
