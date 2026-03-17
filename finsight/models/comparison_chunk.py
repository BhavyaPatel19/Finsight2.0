from sqlmodel import SQLModel, Field


class ComparisonChunk(SQLModel, table=True):
    __tablename__ = "comparison_chunks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    chunk_index: int = Field(default=0)
    text: str
    page_number: int | None = None
    section: str | None = None
    sub_section: str | None = None
    chroma_id: str | None = None  # ID in credisentiment_docs collection
