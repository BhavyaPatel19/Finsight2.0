"""
Retrieval v2.

    retrieve(session, question, top_k=8, document_ids=None, ...)

1. dense over chunks (top-c) and over sentences (top-2c → parent chunks)
2. BM25 over chunks and over sentences (same)
3. Reciprocal Rank Fusion of the four lists, × period prior from the question
4. cross-encoder over (question, chunk.index_text) → top-k

Returns hits shaped like the v1 engine: {"text", "metadata", "rrf_score", "reranker_score"}.
"""

from __future__ import annotations

import time

from finsight.retrieval import index as ix
from finsight.retrieval.periods import period_boost
from finsight.retrieval.text import tokenize

RRF_K = 60
PERIOD_FACTOR = 1.25  # ablation: 1.5 helped hit@5 but cost hit@1; 1.25 keeps both
TABLE_KINDS = ["row", "table"]


def _dense(
    name: str, q_emb: list[float], n: int, document_ids: list[int] | None, kinds: list[str] | None = None
) -> list[dict]:
    coll = ix.collection(name)
    clauses = []
    if document_ids:
        clauses.append(
            {"document_id": document_ids[0]} if len(document_ids) == 1 else {"document_id": {"$in": list(document_ids)}}
        )
    if kinds:
        clauses.append({"kind": {"$in": kinds}})
    where = None if not clauses else (clauses[0] if len(clauses) == 1 else {"$and": clauses})
    try:
        res = coll.query(
            query_embeddings=[q_emb], n_results=max(1, n), where=where, include=["documents", "metadatas", "distances"]
        )
    except Exception:
        return []
    out = []
    for i, cid in enumerate(res["ids"][0]):
        out.append(
            {
                "id": cid,
                "text": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i],
            }
        )
    return out


def _bm25(
    name: str, question: str, n: int, document_ids: list[int] | None, kinds: list[str] | None = None
) -> list[dict]:
    idx = ix.bm25_indexes().get(name)
    if not idx:
        return []
    model, records = idx
    scores = model.get_scores(tokenize(question))
    order = sorted(range(len(records)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in order:
        if scores[i] <= 0:
            break
        r = records[i]
        if document_ids and r["metadata"].get("document_id") not in document_ids:
            continue
        if kinds and r["metadata"].get("kind") not in kinds:
            continue
        out.append({**r, "bm25_score": float(scores[i])})
        if len(out) >= n:
            break
    return out


def _parents(hits: list[dict]) -> list[dict]:
    """Sentence hits → parent chunk records, first occurrence wins, order kept."""
    seen: set[str] = set()
    out = []
    for h in hits:
        cid = h["metadata"].get("chunk_id") or h["id"]
        if cid in seen:
            continue
        seen.add(cid)
        parent = ix.chunk_by_id(cid)
        if parent:
            out.append(parent)
    return out


def _fuse(lists: list[list[dict]], question: str, use_period: bool) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for hits in lists:
        for rank, h in enumerate(hits):
            cid = h["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            items.setdefault(cid, h)
    if use_period:
        for cid in scores:
            m = items[cid]["metadata"]
            scores[cid] *= period_boost(question, m.get("fiscal_year"), m.get("fiscal_quarter"), factor=PERIOD_FACTOR)
    ranked = sorted(scores, key=scores.get, reverse=True)
    return [{**items[c], "rrf_score": scores[c]} for c in ranked]


def retrieve(
    session,
    question: str,
    *,
    top_k: int = 8,
    document_ids: list[int] | None = None,
    candidates: int = 20,
    use_sentences: bool = True,
    use_period: bool = True,
    use_rerank: bool = True,
    use_tables: bool = True,
) -> dict:
    from finsight.rag.service import embed_query

    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    q_emb = embed_query(question)
    timings["embed"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    lists = [_dense(ix.CHUNKS, q_emb, candidates, document_ids)]
    if use_sentences:
        lists.append(_parents(_dense(ix.SENTENCES, q_emb, candidates * 2, document_ids)))
    if use_tables:  # numeric questions need table candidates in the fusion regardless of prose competition
        lists.append(_dense(ix.CHUNKS, q_emb, candidates // 2, document_ids, kinds=TABLE_KINDS))
    timings["dense"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    lists.append(_bm25("chunks", question, candidates, document_ids))
    if use_sentences:
        lists.append(_parents(_bm25("sentences", question, candidates * 2, document_ids)))
    if use_tables:
        lists.append(_bm25("chunks", question, candidates // 2, document_ids, kinds=TABLE_KINDS))
    timings["bm25"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    fused = _fuse(lists, question, use_period)[:candidates]
    timings["fuse"] = (time.perf_counter() - t0) * 1000

    if use_rerank and fused:
        from finsight.rag.reranker import get_reranker

        t0 = time.perf_counter()
        model = get_reranker()
        pairs = [(question, h["metadata"].get("index_text") or h["text"]) for h in fused]
        try:
            rs = model.predict(pairs, show_progress_bar=False)
            for h, s in zip(fused, rs, strict=True):
                h["reranker_score"] = float(s)
            fused.sort(key=lambda h: h["reranker_score"], reverse=True)
        except Exception:
            pass
        timings["rerank"] = (time.perf_counter() - t0) * 1000

    chunks = fused[:top_k]
    for h in chunks:  # strip the bulky index text from what goes to the LLM / API
        h["metadata"] = {k: v for k, v in h["metadata"].items() if k != "index_text"}
    timings["total"] = sum(timings.values())
    return {"chunks": chunks, "timings_ms": timings, "mode": "v2"}
