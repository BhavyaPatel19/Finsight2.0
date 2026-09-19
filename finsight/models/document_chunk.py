from sqlmodel import Field, SQLModel


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    chunk_index: int = Field(default=0)
    # Plain text chunk; default TEXT type is fine for SQLite
    text: str
    chroma_id: str | None = None  # id in ChromaDB for retrieval
