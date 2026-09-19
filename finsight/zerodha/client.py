"""
Zerodha Kite Connect API: OAuth login, token exchange, portfolio holdings, and market data.
"""
import hashlib
from datetime import datetime
from typing import Any

import httpx

from finsight.config import ZERODHA_API_KEY, ZERODHA_API_SECRET

KITE_SESSION_URL = "https://api.kite.trade/session/token"
KITE_HOLDINGS_URL = "https://api.kite.trade/portfolio/holdings"
KITE_LOGIN_BASE = "https://kite.zerodha.com/connect/login"
KITE_QUOTE_URL = "https://api.kite.trade/quote"
KITE_LTP_URL = "https://api.kite.trade/quote/ltp"
KITE_OHLC_URL = "https://api.kite.trade/quote/ohlc"
KITE_HISTORICAL_URL = "https://api.kite.trade/instruments/historical"
KITE_INSTRUMENTS_URL = "https://api.kite.trade/instruments"


def get_oauth_login_url() -> str:
    """Return Zerodha OAuth login URL. User must be sent here; after login Zerodha redirects to your Redirect URL with request_token."""
    if not ZERODHA_API_KEY:
        return ""
    return f"{KITE_LOGIN_BASE}?api_key={ZERODHA_API_KEY}&v=3"


def _checksum(request_token: str) -> str:
    s = f"{ZERODHA_API_KEY}{request_token}{ZERODHA_API_SECRET}"
    return hashlib.sha256(s.encode()).hexdigest()


def exchange_request_token(request_token: str) -> dict[str, Any] | None:
    """
    Exchange request_token (from Zerodha redirect) for access_token.
    Returns {"access_token": "...", "user_id": "..."} or None on failure.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not ZERODHA_API_KEY or not ZERODHA_API_SECRET or not request_token:
        logger.error("exchange_request_token: missing API_KEY=%s, API_SECRET=%s, request_token=%s",
                      bool(ZERODHA_API_KEY), bool(ZERODHA_API_SECRET), bool(request_token))
        return None
    checksum = _checksum(request_token)
    data = {
        "api_key": ZERODHA_API_KEY,
        "request_token": request_token,
        "checksum": checksum,
    }
    logger.info("exchange_request_token: posting to %s with api_key=%s, request_token=%s",
                KITE_SESSION_URL, ZERODHA_API_KEY, request_token)
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                KITE_SESSION_URL,
                data=data,
                headers={"X-Kite-Version": "3"},
            )
            logger.info("exchange_request_token: status_code=%s, body=%s", r.status_code, r.text[:500])
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                logger.error("exchange_request_token: Zerodha returned non-success: %s", out)
                return None
            return {
                "access_token": out.get("data", {}).get("access_token"),
                "user_id": out.get("data", {}).get("user_id"),
            }
    except Exception as e:
        logger.exception("exchange_request_token: exception during token exchange: %s", e)
        return None


def fetch_holdings(access_token: str) -> list[dict[str, Any]]:
    """
    Fetch holdings from Kite. Returns list of dicts with symbol, quantity, avg_price, current_price, pnl.
    """
    if not ZERODHA_API_KEY or not access_token:
        return []
    auth_header = f"token {ZERODHA_API_KEY}:{access_token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                KITE_HOLDINGS_URL,
                headers={
                    "Authorization": auth_header,
                    "X-Kite-Version": "3",
                },
            )
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                return []
            data = out.get("data") or []
            return [
                {
                    "symbol": item.get("tradingsymbol", ""),
                    "exchange": item.get("exchange", ""),
                    "isin": item.get("isin", ""),
                    "quantity": float(item.get("quantity", 0)),
                    "avg_price": float(item.get("average_price", 0)),
                    "current_price": item.get("last_price"),
                    "close_price": item.get("close_price"),
                    "pnl": item.get("pnl"),
                    "day_change": item.get("day_change"),
                    "day_change_pct": item.get("day_change_percentage"),
                }
                for item in data
            ]
    except Exception:
        return []


def fetch_positions(access_token: str) -> list[dict[str, Any]]:
    """Fetch positions (short-term) from Kite."""
    if not ZERODHA_API_KEY or not access_token:
        return []
    auth_header = f"token {ZERODHA_API_KEY}:{access_token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://api.kite.trade/portfolio/positions",
                headers={"Authorization": auth_header, "X-Kite-Version": "3"},
            )
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                return []
            return out.get("data", {}).get("net", []) or []
    except Exception:
        return []


def fetch_margins(access_token: str) -> dict[str, Any]:
    """Fetch margin info."""
    if not ZERODHA_API_KEY or not access_token:
        return {}
    auth_header = f"token {ZERODHA_API_KEY}:{access_token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://api.kite.trade/user/margins",
                headers={"Authorization": auth_header, "X-Kite-Version": "3"},
            )
            r.raise_for_status()
            return r.json() or {}
    except Exception:
        return {}


def _kite_headers(access_token: str) -> dict:
    return {
        "Authorization": f"token {ZERODHA_API_KEY}:{access_token}",
        "X-Kite-Version": "3",
    }


def fetch_quotes(access_token: str, symbols: list[str]) -> dict[str, Any]:
    """
    Fetch full market quotes for up to 500 instruments.
    symbols: list of 'NSE:INFY', 'BSE:RELIANCE' etc.
    Returns dict keyed by 'NSE:INFY' with full quote data.
    """
    if not access_token or not symbols:
        return {}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                KITE_QUOTE_URL,
                params=[("i", s) for s in symbols[:500]],
                headers=_kite_headers(access_token),
            )
            r.raise_for_status()
            out = r.json()
            return out.get("data", {}) if out.get("status") == "success" else {}
    except Exception:
        return {}


def fetch_ltp(access_token: str, symbols: list[str]) -> dict[str, float]:
    """
    Fetch LTP for up to 1000 instruments.
    Returns dict like {'NSE:INFY': 1412.95, ...}
    """
    if not access_token or not symbols:
        return {}
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                KITE_LTP_URL,
                params=[("i", s) for s in symbols[:1000]],
                headers=_kite_headers(access_token),
            )
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                return {}
            return {
                key: val.get("last_price", 0)
                for key, val in out.get("data", {}).items()
            }
    except Exception:
        return {}


def fetch_historical(
    access_token: str,
    instrument_token: int,
    interval: str = "day",
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Fetch historical candle data for a single instrument.
    interval: minute, 3minute, 5minute, 15minute, 30minute, 60minute, day
    Returns list of {timestamp, open, high, low, close, volume}
    """
    if not access_token or not instrument_token:
        return []
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if not from_date:
        from_date = "2024-01-01"
    url = f"{KITE_HISTORICAL_URL}/{instrument_token}/{interval}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                url,
                params={"from": from_date, "to": to_date},
                headers=_kite_headers(access_token),
            )
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                return []
            candles = out.get("data", {}).get("candles", [])
            return [
                {
                    "timestamp": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5],
                }
                for c in candles
            ]
    except Exception:
        return []


def fetch_instruments(access_token: str, exchange: str = "NSE") -> list[dict]:
    """
    Download the full instrument list CSV for an exchange.
    Returns list of dicts with instrument_token, tradingsymbol, name, etc.
    """
    if not access_token:
        return []
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{KITE_INSTRUMENTS_URL}/{exchange}",
                headers=_kite_headers(access_token),
            )
            r.raise_for_status()
            import csv
            import io
            reader = csv.DictReader(io.StringIO(r.text))
            return list(reader)
    except Exception:
        return []
