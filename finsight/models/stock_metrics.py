from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class StockMetrics(SQLModel, table=True):
    __tablename__ = "stock_metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    debt_to_equity: Optional[float] = None
    book_value: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    promoter_holding: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
