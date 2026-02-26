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
