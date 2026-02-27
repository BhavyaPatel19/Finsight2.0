from pydantic import BaseModel
from datetime import datetime


class CredibilityScoreResponse(BaseModel):
    id: int
    symbol: str
    period: str
    score_0_100: float
    avg_deviation: float | None
    computed_at: datetime

    class Config:
        from_attributes = True


class ClaimItem(BaseModel):
    category: str
    claim_period: str | None
    claim_value: float | None
    actual_value: float | None
    deviation: float | None


class FundamentalsScoreResponse(BaseModel):
    symbol: str
    score: float | None
    pe: float | None = None
    roce: float | None = None
    debt_to_equity: float | None = None
    revenue_growth: float | None = None
    promoter_holding: float | None = None
    market_cap: float | None = None
    book_value: float | None = None
    dividend_yield: float | None = None
    source: str = "screener.in"

