"""CrediSentiment ChromaDB vectorstore — STUB (to be implemented)."""

_collection = None


def get_collection():
    raise NotImplementedError("vectorstore not yet implemented")


def add_chunks(ids, texts, metadatas, embeddings):
    raise NotImplementedError


def get_chunks_by_document_id(document_id: int):
    raise NotImplementedError


def delete_by_document_id(document_id: int) -> int:
    raise NotImplementedError
