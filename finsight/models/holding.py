from datetime import datetime

from sqlmodel import SQLModel, Field


class Holding(SQLModel, table=True):
    __tablename__ = "holdings"

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    symbol: str = Field(index=True)
    exchange: str | None = None
    quantity: float = Field(default=0)
    avg_price: float = Field(default=0)
    current_price: float | None = None
    close_price: float | None = None
    pnl: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    last_updated_at: datetime | None = None
    as_of_date: datetime | None = None

