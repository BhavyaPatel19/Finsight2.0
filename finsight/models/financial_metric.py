from datetime import datetime

from sqlmodel import Field, SQLModel


class FinancialMetric(SQLModel, table=True):
    __tablename__ = "financial_metrics"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    pe: float | None = None
    roce: float | None = None
    revenue_growth: float | None = None
    margin: float | None = None
    debt: float | None = None
    source_document_id: int | None = Field(default=None, foreign_key="documents.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
