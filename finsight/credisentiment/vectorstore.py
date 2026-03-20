"""
CrediSentiment ChromaDB vectorstore.

Manages the `credisentiment_docs` collection, separate from the RAG
`finsight_docs` collection.  Mirrors the pattern in finsight/rag/vectorstore.py.
"""

from typing import Any

from finsight.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

_collection = None


def get_collection():
    """
    Lazy-init singleton for the credisentiment_docs ChromaDB collection.
    Auto-clears if the stored embedding model differs from the current one.
    """
    global _collection
    if _collection is not None:
        return _collection

    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # Check for embedding-model mismatch (e.g. after switching models)
    existing = client.list_collections()
    if any(c.name == "credisentiment_docs" for c in existing):
        coll = client.get_collection("credisentiment_docs")
        stored_model = (coll.metadata or {}).get("embedding_model", "")
        if not stored_model or stored_model != EMBEDDING_MODEL:
            client.delete_collection("credisentiment_docs")

    _collection = client.get_or_create_collection(
        name="credisentiment_docs",
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": EMBEDDING_MODEL,
        },
    )
    return _collection


def add_chunks(
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    """Add chunks with pre-computed embeddings to credisentiment_docs."""
    coll = get_collection()
    coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)


def query_by_document_id(
    query_embedding: list[float],
    document_id: int,
    n_results: int = 5,
) -> list[dict]:
    """Semantic search within a single document's credisentiment chunks."""
    coll = get_collection()
    try:
        res = coll.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"document_id": document_id},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    items = []
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i, cid in enumerate(ids):
        items.append({
            "id": cid,
            "text": docs[i] if docs else "",
            "metadata": metas[i] if metas else {},
            "distance": dists[i] if dists else 1.0,
        })
    return items


def get_chunks_by_document_id(document_id: int) -> list[dict]:
    """Retrieve all chunks for a document, sorted by chunk_index."""
    coll = get_collection()
    results = coll.get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    items = []
    ids = results.get("ids", [])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    for i, cid in enumerate(ids):
        items.append({
            "id": cid,
            "text": docs[i] if docs else "",
            "metadata": metas[i] if metas else {},
        })
    # Sort by chunk_index
    items.sort(key=lambda x: x.get("metadata", {}).get("chunk_index", 0))
    return items


def delete_by_document_id(document_id: int) -> int:
    """Delete all embeddings for a given document_id.  Returns count deleted."""
    coll = get_collection()
    results = coll.get(where={"document_id": document_id}, include=[])
    ids = results.get("ids", [])
    if ids:
        coll.delete(ids=ids)
    return len(ids)
