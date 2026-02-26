from pydantic import BaseModel
from datetime import datetime


class SentimentScoreResponse(BaseModel):
    id: int
    document_id: int
    symbol: str
    fiscal_quarter: str | None
    fiscal_year: str | None
    overall_score: float
    risk_tone_index: float | None
    optimism_index: float | None
    computed_at: datetime

    class Config:
        from_attributes = True
