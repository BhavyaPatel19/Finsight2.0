"""
Market data provider interface.

Two implementations: yfinance (free, delayed, no account) and Zerodha Kite
(live, needs a paid Kite Connect app + per-user OAuth). Routers only see
this interface, so the app runs fully without a broker.

Shapes (kept identical to what the frontend already consumes):

    quotes:      {"NSE:INFY": {"last_price": float, "volume": int,
                               "ohlc": {"open", "high", "low", "close"}}}
                 where ohlc.close is the *previous* session close (Kite convention)
    ltp:         {"INFY": float}
    candles:     [{"timestamp": iso8601, "open", "high", "low", "close", "volume"}]
    instruments: [{"instrument_token": int, "symbol", "name", "exchange",
                   "segment", "instrument_type"}]
"""

from __future__ import annotations

import abc


class MarketDataProvider(abc.ABC):
    #: short identifier shown in the UI
    name: str
    #: True when prices are real-time (broker feed) rather than delayed
    live: bool = False

    @abc.abstractmethod
    def get_quotes(self, symbols: list[str]) -> dict:
        """symbols like ["NSE:INFY", ...]. Missing/failed symbols are simply absent."""

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        quotes = self.get_quotes(symbols)
        return {key.split(":")[-1]: q["last_price"] for key, q in quotes.items() if q.get("last_price") is not None}

    @abc.abstractmethod
    def get_history(
        self,
        symbol: str,
        interval: str = "day",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """interval: minute, 5minute, 15minute, 30minute, 60minute, day (Kite names)."""

    @abc.abstractmethod
    def search_instruments(self, query: str, limit: int = 15) -> list[dict]: ...
