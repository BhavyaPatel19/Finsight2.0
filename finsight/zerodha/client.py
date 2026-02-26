"""
Zerodha Kite Connect API: OAuth login, token exchange, and portfolio holdings.
"""
import hashlib
from typing import Any

import httpx

from finsight.config import ZERODHA_API_KEY, ZERODHA_API_SECRET

KITE_SESSION_URL = "https://api.kite.trade/session/token"
KITE_HOLDINGS_URL = "https://api.kite.trade/portfolio/holdings"
KITE_LOGIN_BASE = "https://kite.zerodha.com/connect/login"


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
    if not ZERODHA_API_KEY or not ZERODHA_API_SECRET or not request_token:
        return None
    checksum = _checksum(request_token)
    data = {
        "api_key": ZERODHA_API_KEY,
        "request_token": request_token,
        "checksum": checksum,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                KITE_SESSION_URL,
                data=data,
                headers={"X-Kite-Version": "3"},
            )
            r.raise_for_status()
            out = r.json()
            if out.get("status") != "success":
                return None
            return {
                "access_token": out.get("data", {}).get("access_token"),
                "user_id": out.get("data", {}).get("user_id"),
            }
    except Exception:
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
                    "quantity": float(item.get("quantity", 0)),
                    "avg_price": float(item.get("average_price", 0)),
                    "current_price": item.get("last_price"),
                    "pnl": item.get("pnl"),
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
