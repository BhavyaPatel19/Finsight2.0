from datetime import datetime

from sqlmodel import Field, SQLModel


class DivisionSentiment(SQLModel, table=True):
    """Per-division FinBERT sentiment scores for a document."""
    __tablename__ = "division_sentiments"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    symbol: str = Field(index=True)
    division_name: str = Field(index=True)
    positive_score: float = Field(default=0.0)
    negative_score: float = Field(default=0.0)
    neutral_score: float = Field(default=0.0)
    overall_score: float = Field(default=0.0)  # positive - negative
    sentence_count: int = Field(default=0)
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class WalkTheTalkResult(SQLModel, table=True):
    """LLM comparison of management claims vs actual outcomes."""
    __tablename__ = "walk_the_talk_results"

    id: int | None = Field(default=None, primary_key=True)
    claims_document_id: int = Field(foreign_key="documents.id", index=True)
    actuals_document_id: int = Field(foreign_key="documents.id", index=True)
    symbol: str = Field(index=True)
    overall_score: float = Field(default=0.0)  # 0-100
    claims_json: str | None = None  # JSON string of individual claim comparisons
    narrative_summary: str | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
