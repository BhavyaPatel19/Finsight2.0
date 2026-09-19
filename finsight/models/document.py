from datetime import datetime

from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    # NULL = shared corpus (seeded filings); otherwise private to the uploader.
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    symbol: str = Field(index=True)
    doc_type: str = Field(index=True)  # DocType value
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    source_url: str | None = None
    pdf_path: str | None = None
    text_path: str | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    # New fields for scraper workflow
    status: str = Field(default="pending", index=True)  # pending|downloading|processing|indexed|error
    error_message: str | None = None
    chunk_count: int = Field(default=0)
    file_size: int | None = None  # bytes
    company_name: str | None = None

    # CrediSentiment pipeline status (independent of RAG status)
    cs_status: str = Field(default="pending", index=True)  # pending|processing|indexed|error
    cs_chunk_count: int = Field(default=0)
    cs_error_message: str | None = None
