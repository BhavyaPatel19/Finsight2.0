from pydantic import BaseModel


class HoldingMetric(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    current_price: float | None
    pe: float | None = None
    roce: float | None = None
    revenue_growth: float | None = None


class PortfolioMetrics(BaseModel):
    holdings: list[HoldingMetric]
    total_value: float | None = None


class InsightSummary(BaseModel):
    portfolio_credibility_score: float | None = None
    low_credibility_exposure_pct: float | None = None
    sentiment_weighted_exposure: float | None = None
    summary: str | None = None
