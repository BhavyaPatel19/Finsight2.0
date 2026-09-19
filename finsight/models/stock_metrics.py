from datetime import datetime

from sqlmodel import Field, SQLModel


class StockMetrics(SQLModel, table=True):
    __tablename__ = "stock_metrics"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    roce: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    debt_to_equity: float | None = None
    book_value: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    promoter_holding: float | None = None
    sector: str | None = None
    industry: str | None = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
