from datetime import datetime

from sqlmodel import Field, SQLModel


class ExtractedClaim(SQLModel, table=True):
    __tablename__ = "extracted_claims"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    symbol: str = Field(index=True)
    category: str = Field(index=True)  # ClaimCategory value
    claim_period: str | None = None  # e.g. FY25, Q3FY26
    claim_value: float | None = None
    context_snippet: str | None = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class CredibilityScore(SQLModel, table=True):
    __tablename__ = "credibility_scores"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    period: str = Field(index=True)  # e.g. FY25, Q3FY26
    score_0_100: float = Field(default=0)
    avg_deviation: float | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
