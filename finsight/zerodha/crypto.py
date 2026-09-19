"""
Encrypt broker access tokens at rest.

A Zerodha access token grants read (and potentially trade) access to a
brokerage account, so the SQLite file must not leak usable tokens. Tokens
are Fernet-encrypted with a key derived from SECRET_KEY; values written
before encryption existed are read as plaintext and re-encrypted on save.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from finsight import config

_PREFIX = "enc:"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(config.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_token(token: str) -> str:
    return _PREFIX + _fernet().encrypt(token.encode()).decode()


def decrypt_token(value: str) -> str:
    """Return the plaintext token. Legacy plaintext rows pass through unchanged."""
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode()).decode()
    except InvalidToken as e:  # SECRET_KEY changed: the token is unrecoverable, force a re-link
        raise ValueError("stored Zerodha token cannot be decrypted with the current SECRET_KEY") from e
