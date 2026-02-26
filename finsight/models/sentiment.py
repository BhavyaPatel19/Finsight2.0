from datetime import datetime

from sqlmodel import SQLModel, Field


class SentimentScore(SQLModel, table=True):
    __tablename__ = "sentiment_scores"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    symbol: str = Field(index=True)
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    overall_score: float = Field(default=0)  # e.g. -1 to 1 or 0 to 1
    risk_tone_index: float | None = None
    optimism_index: float | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
