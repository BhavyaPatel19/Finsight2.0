"""
Retrieval, factored out of answer_question() so the evaluation harness
measures exactly the code path the app uses.

Modes:
    dense          BGE-base embeddings → ChromaDB (cosine)
    bm25           rank-bm25 over the same chunks
    hybrid         dense ∪ bm25 fused with Reciprocal Rank Fusion (k=60)
    hybrid_rerank  hybrid, then BAAI/bge-reranker-base cross-encoder   (production)
"""

from __future__ import annotations

import time

from sqlmodel import Session

MODES = ("dense", "bm25", "hybrid", "hybrid_rerank")
DEFAULT_MODE = "hybrid_rerank"
CANDIDATES = 20  # first-stage depth per retriever before fusion / reranking (ablation: 20 ≈ 30 in quality, 35% faster)


def reciprocal_rank_fusion(*ranked_lists: list[dict], k: int = 60) -> list[dict]:
    """Fuse ranked lists of hits; RRF score = Σ 1/(k + rank). Dedupes by chunk id."""
    scores: dict[str, dict] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits):
            cid = chunk_id(hit)
            entry = scores.setdefault(cid, {"rrf_score": 0.0, "item": hit})
            entry["rrf_score"] += 1.0 / (k + rank + 1)
            # Prefer the richer metadata (dense hits carry page/section; BM25 may not)
            if not entry["item"].get("metadata", {}).get("page_number") and hit.get("metadata", {}).get("page_number"):
                entry["item"] = {**hit}
    merged = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    out = []
    for m in merged:
        item = dict(m["item"])
        item["rrf_score"] = m["rrf_score"]
        out.append(item)
    return out


def chunk_id(hit: dict) -> str:
    meta = hit.get("metadata", {})
    return f"doc_{meta.get('document_id')}_chunk_{meta.get('chunk_index')}"


def retrieve(
    session: Session,
    question: str,
    *,
    mode: str = DEFAULT_MODE,
    top_k: int = 8,
    document_ids: list[int] | None = None,
    symbol: str | None = None,
    period: str | None = None,
    candidates: int = CANDIDATES,
) -> dict:
    """Return {"chunks": [top_k hits], "timings_ms": {...}, "mode": mode}."""
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode!r}; expected one of {MODES}")

    from finsight.rag.bm25_store import bm25_search, build_bm25_index, is_built
    from finsight.rag.service import embed_query
    from finsight.rag.vectorstore import query as chroma_query
    from finsight.rag.vectorstore import query_by_document_ids

    timings: dict[str, float] = {}
    dense_hits: list[dict] = []
    bm25_hits: list[dict] = []

    if mode in ("dense", "hybrid", "hybrid_rerank"):
        t0 = time.perf_counter()
        q_emb = embed_query(question)
        timings["embed"] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        if document_ids:
            dense_hits = query_by_document_ids(q_emb, document_ids, n_results=candidates)
        else:
            where = None
            if symbol:
                where = {"symbol": symbol}
            if period:
                where = where or {}
                where["fiscal_year"] = period
            dense_hits = chroma_query(q_emb, n_results=candidates, where=where)
        timings["dense"] = (time.perf_counter() - t0) * 1000

    if mode in ("bm25", "hybrid", "hybrid_rerank"):
        t0 = time.perf_counter()
        if not is_built():
            build_bm25_index(session)
        bm25_hits = bm25_search(question, n_results=candidates, document_ids=document_ids)
        if symbol:
            bm25_hits = [h for h in bm25_hits if h["metadata"].get("symbol") == symbol]
        if period:
            bm25_hits = [h for h in bm25_hits if h["metadata"].get("fiscal_year") == period]
        timings["bm25"] = (time.perf_counter() - t0) * 1000

    if mode == "dense":
        chunks = dense_hits[:top_k]
    elif mode == "bm25":
        chunks = bm25_hits[:top_k]
    else:
        t0 = time.perf_counter()
        fused = reciprocal_rank_fusion(dense_hits, bm25_hits)[:candidates]
        timings["fuse"] = (time.perf_counter() - t0) * 1000
        if mode == "hybrid":
            chunks = fused[:top_k]
        else:
            from finsight.rag.reranker import rerank

            t0 = time.perf_counter()
            chunks = rerank(question, fused, top_k=top_k) if fused else []
            timings["rerank"] = (time.perf_counter() - t0) * 1000

    timings["total"] = sum(timings.values())
    return {"chunks": chunks, "timings_ms": timings, "mode": mode}
