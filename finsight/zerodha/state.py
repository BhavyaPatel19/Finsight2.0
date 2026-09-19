"""
CSRF protection for the Zerodha OAuth link flow.

/connect stores a signed `user_id.nonce.mac` cookie and sends the nonce to
Kite as `redirect_params=state=<nonce>`; /callback accepts the link only
if the cookie verifies AND the returned `state` equals the nonce. Without
this, an attacker could link *their* brokerage to a victim's account by
luring the victim to /callback with the attacker's request_token.
"""
from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from finsight import config

COOKIE = "zerodha_link"
MAX_AGE = 600  # seconds


def _mac(user_id: int, nonce: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), f"{user_id}.{nonce}".encode(), sha256).hexdigest()[:32]


def issue(user_id: int) -> tuple[str, str]:
    """-> (cookie_value, nonce)"""
    nonce = secrets.token_urlsafe(16)
    return f"{user_id}.{nonce}.{_mac(user_id, nonce)}", nonce


def verify(cookie_value: str | None, state: str | None) -> int | None:
    """User id if the cookie is authentic and `state` matches its nonce, else None."""
    if not cookie_value or not state:
        return None
    try:
        uid_s, nonce, mac = cookie_value.split(".", 2)
        uid = int(uid_s)
    except ValueError:
        return None
    if not hmac.compare_digest(mac, _mac(uid, nonce)) or not hmac.compare_digest(nonce, state):
        return None
    return uid
