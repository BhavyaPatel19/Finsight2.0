from typing import Any

from finsight.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

_collection = None


def get_collection():
    """
    Get or create ChromaDB collection.
    Auto-clears if the stored embedding model differs from the current one
    (e.g. after switching from all-MiniLM to bge-base).
    """
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # Check if existing collection was built with a different embedding model
    existing = client.list_collections()
    if any(c.name == "finsight_docs" for c in existing):
        coll = client.get_collection("finsight_docs")
        stored_model = (coll.metadata or {}).get("embedding_model", "")
        if not stored_model or stored_model != EMBEDDING_MODEL:
            # Model changed — delete and recreate to avoid dimension mismatch
            client.delete_collection("finsight_docs")

    _collection = client.get_or_create_collection(
        name="finsight_docs",
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
    embeddings: list[list[float]] | None = None,
) -> None:
    coll = get_collection()
    if embeddings is not None:
        coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    else:
        coll.add(ids=ids, documents=texts, metadatas=metadatas)


def query(
    query_embedding: list[float],
    n_results: int = 30,
    where: dict[str, Any] | None = None,
) -> list[dict]:
    coll = get_collection()
    try:
        res = coll.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    out = []
    if res["documents"] and res["documents"][0]:
        for i, doc in enumerate(res["documents"][0]):
            out.append({
                "text": doc,
                "metadata": (res["metadatas"][0][i] if (res["metadatas"] and res["metadatas"][0]) else {}),
                "distance": (res["distances"][0][i] if (res.get("distances") and res["distances"][0]) else None),
            })
    return out


def query_by_document_ids(
    query_embedding: list[float],
    document_ids: list[int],
    n_results: int = 30,
) -> list[dict]:
    """Query ChromaDB filtered to specific document IDs only."""
    if not document_ids:
        return []

    if len(document_ids) == 1:
        where: dict[str, Any] = {"document_id": document_ids[0]}
    else:
        where = {"document_id": {"$in": document_ids}}

    return query(query_embedding, n_results=n_results, where=where)


def delete_by_document_id(document_id: int) -> int:
    """Delete all embeddings for a given document_id. Returns count deleted."""
    coll = get_collection()
    results = coll.get(where={"document_id": document_id}, include=[])
    ids = results.get("ids", [])
    if ids:
        coll.delete(ids=ids)
    return len(ids)
