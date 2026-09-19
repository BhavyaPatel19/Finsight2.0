"""
Market data provider selection.

    from finsight.market.providers import get_market_provider
    provider = get_market_provider(session, user.id)

MARKET_DATA_PROVIDER (config):
    "auto"     → Zerodha when the app has Kite credentials AND this user has
                 linked their account; otherwise yfinance   (default)
    "yfinance" → always yfinance
    "zerodha"  → Zerodha only; raises if the user has not linked
"""

from __future__ import annotations

from sqlmodel import Session

from finsight import config
from finsight.market.providers.base import MarketDataProvider
from finsight.market.providers.yfinance_provider import YFinanceProvider
from finsight.market.providers.zerodha_provider import ZerodhaProvider

__all__ = ["MarketDataProvider", "get_market_provider", "market_status", "MarketNotLinked"]

_yfinance = YFinanceProvider()


class MarketNotLinked(RuntimeError):
    """MARKET_DATA_PROVIDER=zerodha but this user has no linked Kite session."""


def zerodha_configured() -> bool:
    return bool(config.ZERODHA_API_KEY and config.ZERODHA_API_SECRET)


def _user_token(session: Session, user_id: int) -> str | None:
    from finsight.zerodha.service import get_zerodha_token_for_user

    return get_zerodha_token_for_user(session, user_id)


def get_market_provider(session: Session, user_id: int) -> MarketDataProvider:
    mode = (config.MARKET_DATA_PROVIDER or "auto").lower()
    if mode == "yfinance":
        return _yfinance
    token = _user_token(session, user_id) if zerodha_configured() else None
    if mode == "zerodha":
        if not token:
            raise MarketNotLinked("Zerodha not linked for this user")
        return ZerodhaProvider(token)
    if mode != "auto":
        raise ValueError(f"unknown MARKET_DATA_PROVIDER {mode!r}; expected auto, yfinance or zerodha")
    return ZerodhaProvider(token) if token else _yfinance


def market_status(session: Session, user_id: int) -> dict:
    token = _user_token(session, user_id)
    try:
        provider = get_market_provider(session, user_id)
        name, live = provider.name, provider.live
    except MarketNotLinked:
        name, live = "zerodha", True
    return {
        "provider": name,
        "live": live,
        "zerodha_configured": zerodha_configured(),
        "zerodha_linked": bool(token),
    }
