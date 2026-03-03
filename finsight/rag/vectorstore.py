from typing import Any

from finsight.config import CHROMA_PERSIST_DIR

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = client.get_or_create_collection(
            name="finsight_docs",
            metadata={"hnsw:space": "cosine"},
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
    n_results: int = 8,
    where: dict[str, Any] | None = None,
) -> list[dict]:
    coll = get_collection()
    res = coll.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    if res["documents"] and res["documents"][0]:
        for i, doc in enumerate(res["documents"][0]):
            out.append({
                "text": doc,
                "metadata": (res["metadatas"][0][i] if (res["metadatas"] and res["metadatas"][0]) else {}),
                "distance": (res["distances"][0][i] if (res.get("distances") and res["distances"][0]) else None),
            })
    return out


def delete_by_document_id(document_id: int) -> int:
    """Delete all embeddings for a given document_id from ChromaDB.
    Returns the number of items deleted."""
    coll = get_collection()
    # Get all IDs matching this document_id
    results = coll.get(
        where={"document_id": document_id},
        include=[],
    )
    ids = results.get("ids", [])
    if ids:
        coll.delete(ids=ids)
    return len(ids)
