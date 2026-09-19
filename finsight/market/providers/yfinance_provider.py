"""
yfinance-backed market data: free, no account, ~15-min delayed for NSE.

NSE symbols map to Yahoo tickers by appending ".NS". Instrument search uses
the bundled NIFTY 500 list first (instant), then Yahoo's search endpoint.
"""
from __future__ import annotations

import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from finsight.market.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Kite interval name -> (yfinance interval, max lookback Yahoo allows)
_INTERVALS: dict[str, tuple[str, timedelta]] = {
    "minute": ("1m", timedelta(days=7)),
    "3minute": ("2m", timedelta(days=60)),
    "5minute": ("5m", timedelta(days=60)),
    "15minute": ("15m", timedelta(days=60)),
    "30minute": ("30m", timedelta(days=60)),
    "60minute": ("60m", timedelta(days=730)),
    "day": ("1d", timedelta(days=365 * 20)),
}

_QUOTE_TTL_S = 60.0


def _to_yahoo(symbol: str) -> str:
    sym = symbol.split(":")[-1].upper()
    return sym if sym.endswith((".NS", ".BO")) else f"{sym}.NS"


def _from_yahoo(ticker: str) -> str:
    return ticker.removesuffix(".NS").removesuffix(".BO").upper()


def _load_bundled_instruments() -> list[dict]:
    path = _DATA_DIR / "nifty500.csv"
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sym = (r.get("Symbol") or "").strip()
            if not sym:
                continue
            rows.append({
                "instrument_token": 0,
                "symbol": sym,
                "name": (r.get("Company Name") or "").strip(),
                "exchange": "NSE",
                "segment": "NSE",
                "instrument_type": "EQ",
                "industry": (r.get("Industry") or "").strip(),
            })
    return rows


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"
    live = False

    def __init__(self):
        self._quote_cache: dict[str, tuple[float, dict]] = {}
        self._instruments: list[dict] | None = None

    # -- hooks (monkeypatched in tests; wrap the yfinance calls) --------------

    def _recent(self, ticker: str):
        """Last few daily bars for one ticker. Per-ticker calls are far more
        reliable than the batch yf.download(), which silently drops symbols
        when Yahoo throttles."""
        import yfinance as yf
        return yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)

    def _history(self, ticker: str, interval: str, start: datetime, end: datetime):
        import yfinance as yf
        return yf.Ticker(ticker).history(start=start, end=end, interval=interval, auto_adjust=False)

    def _yahoo_search(self, query: str, limit: int) -> list[dict]:
        import yfinance as yf
        return list(yf.Search(query, max_results=limit).quotes or [])

    # -- quotes -----------------------------------------------------------------

    def get_quotes(self, symbols: list[str]) -> dict:
        if not symbols:
            return {}
        now = time.time()
        wanted = {s.upper(): _to_yahoo(s) for s in symbols}
        out: dict = {}
        missing: list[str] = []
        for key, ticker in wanted.items():
            hit = self._quote_cache.get(ticker)
            if hit and now - hit[0] < _QUOTE_TTL_S:
                out[key] = hit[1]
            elif ticker not in missing:
                missing.append(ticker)

        if missing:
            def fetch(ticker: str):
                try:
                    return ticker, self._shape_quote(self._recent(ticker))
                except Exception as e:
                    logger.warning("yfinance quote failed for %s: %s", ticker, e)
                    return ticker, None

            with ThreadPoolExecutor(max_workers=8) as ex:
                fetched = dict(ex.map(fetch, missing))
            for key, ticker in wanted.items():
                q = fetched.get(ticker)
                if q:
                    self._quote_cache[ticker] = (now, q)
                    out[key] = q
        return out

    @staticmethod
    def _shape_quote(df) -> dict | None:
        if df is None or len(df) == 0 or "Close" not in df:
            return None
        df = df.dropna(subset=["Close"])
        if len(df) == 0:
            return None
        last = df.iloc[-1]
        prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else float(last["Open"])
        vol = last.get("Volume")
        return {
            "last_price": round(float(last["Close"]), 2),
            "volume": int(vol) if vol == vol else 0,  # NaN-safe
            "ohlc": {
                "open": round(float(last["Open"]), 2),
                "high": round(float(last["High"]), 2),
                "low": round(float(last["Low"]), 2),
                "close": round(prev_close, 2),
            },
            "timestamp": df.index[-1].isoformat() if hasattr(df.index[-1], "isoformat") else None,
        }

    # -- history ----------------------------------------------------------------

    def get_history(self, symbol, interval="day", from_date=None, to_date=None) -> list[dict]:
        yf_interval, max_back = _INTERVALS.get(interval, _INTERVALS["day"])
        end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) if to_date else datetime.now() + timedelta(days=1)
        default_back = timedelta(days=365) if interval == "day" else max_back
        start = datetime.strptime(from_date, "%Y-%m-%d") if from_date else end - default_back
        # Yahoo refuses intraday requests older than its window; clamp instead of failing.
        floor = datetime.now() - max_back + timedelta(days=1)
        if start < floor:
            start = floor
        try:
            df = self._history(_to_yahoo(symbol), yf_interval, start, end)
        except Exception as e:
            logger.warning("yfinance history failed for %s: %s", symbol, e)
            return []
        if df is None or df.empty:
            return []
        candles = []
        for ts, row in df.iterrows():
            if row["Close"] != row["Close"]:  # NaN
                continue
            candles.append({
                "timestamp": ts.isoformat(),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
            })
        return candles

    # -- search -----------------------------------------------------------------

    def search_instruments(self, query: str, limit: int = 15) -> list[dict]:
        if self._instruments is None:
            self._instruments = _load_bundled_instruments()
        q = query.strip().upper()
        if not q:
            return []
        exact = [i for i in self._instruments if i["symbol"] == q]
        prefix = [i for i in self._instruments if i["symbol"].startswith(q) and i["symbol"] != q]
        byname = [i for i in self._instruments if q in i["name"].upper()
                  and i not in exact and i not in prefix]
        results = (exact + prefix + byname)[:limit]

        if len(results) < 5:
            seen = {r["symbol"] for r in results}
            try:
                for hit in self._yahoo_search(query, limit):
                    sym = hit.get("symbol", "")
                    if not sym.endswith(".NS") or hit.get("quoteType") not in (None, "EQUITY"):
                        continue
                    plain = _from_yahoo(sym)
                    if plain in seen:
                        continue
                    seen.add(plain)
                    results.append({
                        "instrument_token": 0, "symbol": plain,
                        "name": hit.get("longname") or hit.get("shortname") or plain,
                        "exchange": "NSE", "segment": "NSE", "instrument_type": "EQ",
                        "industry": hit.get("industry", ""),
                    })
                    if len(results) >= limit:
                        break
            except Exception as e:
                logger.warning("yahoo search failed: %s", e)
        return results
