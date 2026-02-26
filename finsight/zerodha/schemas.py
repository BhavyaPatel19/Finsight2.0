from pydantic import BaseModel


class ZerodhaLinkBody(BaseModel):
    request_token: str


class ZerodhaLoginUrl(BaseModel):
    login_url: str


class HoldingItem(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    current_price: float | None = None
    pnl: float | None = None


class PortfolioSummary(BaseModel):
    holdings: list[HoldingItem]
    total_value: float | None = None
    total_pnl: float | None = None
