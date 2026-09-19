"""
Zerodha Kite Connect market data: live quotes for a user who has linked
their broker account. Wraps the existing client functions.
"""

from __future__ import annotations

import logging

from finsight.market.providers.base import MarketDataProvider
from finsight.zerodha.client import fetch_historical, fetch_instruments, fetch_ltp, fetch_quotes

logger = logging.getLogger(__name__)

# NSE instrument dump is ~2k rows and identical for every user; load once per process.
_instruments_cache: list[dict] = []
_by_symbol: dict[str, dict] = {}


def _ensure_instruments(access_token: str) -> None:
    global _instruments_cache, _by_symbol
    if _instruments_cache:
        return
    try:
        raw = fetch_instruments(access_token, "NSE")
        _instruments_cache = [
            {
                "instrument_token": int(i.get("instrument_token", 0)),
                "symbol": i.get("tradingsymbol", ""),
                "name": i.get("name", ""),
                "exchange": i.get("exchange", "NSE"),
                "segment": i.get("segment", ""),
                "instrument_type": i.get("instrument_type", ""),
            }
            for i in raw
            if i.get("tradingsymbol")
        ]
        _by_symbol = {i["symbol"].upper(): i for i in _instruments_cache}
        logger.info("Loaded %d NSE instruments", len(_instruments_cache))
    except Exception as e:
        logger.warning("Failed to load instruments: %s", e)


class ZerodhaProvider(MarketDataProvider):
    name = "zerodha"
    live = True

    def __init__(self, access_token: str):
        self.access_token = access_token

    def get_quotes(self, symbols: list[str]) -> dict:
        return fetch_quotes(self.access_token, symbols) if symbols else {}

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        data = fetch_ltp(self.access_token, symbols) if symbols else {}
        return {k.split(":")[-1]: v for k, v in data.items()}

    def get_history(self, symbol, interval="day", from_date=None, to_date=None) -> list[dict]:
        _ensure_instruments(self.access_token)
        inst = _by_symbol.get(symbol.upper())
        if not inst:
            return []
        return fetch_historical(self.access_token, inst["instrument_token"], interval, from_date, to_date)

    def search_instruments(self, query: str, limit: int = 15) -> list[dict]:
        _ensure_instruments(self.access_token)
        q = query.strip().upper()
        results: list[dict] = []
        exact = _by_symbol.get(q)
        if exact:
            results.append(exact)
        for inst in _instruments_cache:
            if len(results) >= limit:
                break
            if inst is exact:
                continue
            if inst["symbol"].upper().startswith(q):
                results.append(inst)
        if len(results) < limit:
            for inst in _instruments_cache:
                if len(results) >= limit:
                    break
                if inst in results:
                    continue
                if q in (inst.get("name") or "").upper():
                    results.append(inst)
        return results
