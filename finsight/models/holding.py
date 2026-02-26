from datetime import datetime

from sqlmodel import SQLModel, Field


class Holding(SQLModel, table=True):
    __tablename__ = "holdings"

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolios.id", index=True)
    symbol: str = Field(index=True)
    quantity: float = Field(default=0)
    avg_price: float = Field(default=0)
    current_price: float | None = None
    last_updated_at: datetime | None = None
    # For daily snapshot: optional as_of_date
    as_of_date: datetime | None = None
