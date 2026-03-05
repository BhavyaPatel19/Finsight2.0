"""
Cross-encoder reranker using BAAI/bge-reranker-base.
~275MB on VRAM. Loaded lazily on first use.
"""

_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
    return _reranker


def rerank(query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
    """
    Rerank candidate chunks using cross-encoder.
    candidates: list of {"text": str, "metadata": dict, ...}
    Returns top_k candidates sorted by reranker score (highest = most relevant).
    """
    if not candidates:
        return []

    model = get_reranker()
    pairs = [(query, c["text"][:512]) for c in candidates]  # truncate to 512 chars for speed

    try:
        scores = model.predict(pairs, show_progress_bar=False)
    except Exception:
        # Fallback: return candidates unchanged if reranker fails
        return candidates[:top_k]

    for candidate, score in zip(candidates, scores):
        candidate["reranker_score"] = float(score)

    reranked = sorted(candidates, key=lambda x: x.get("reranker_score", 0.0), reverse=True)
    return reranked[:top_k]
