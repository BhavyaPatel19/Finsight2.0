"""Small retry helper shared by HTTP-backed providers."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque

import httpx

from finsight.llm.base import LLMError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
# A Retry-After longer than this is a daily quota, not a per-minute one: waiting it out inside an
# eval run would stall for hours, so the call fails at once with the wait in the message.
QUOTA_WAIT_S = 300.0


def _attempts(default: int) -> int:
    try:
        return max(1, int(os.getenv("LLM_RETRY_ATTEMPTS", default)))
    except ValueError:
        return default


def _delay(attempt: int, response: httpx.Response | None) -> float:
    if response is not None:
        ra = response.headers.get("retry-after")
        if ra:
            try:
                wait = float(ra)
            except ValueError:
                wait = None
            if wait is not None:
                if wait > QUOTA_WAIT_S:
                    raise LLMError(
                        f"provider quota exhausted (retry after {wait / 3600:.1f} h); "
                        "re-run later — cached steps are not repeated"
                    )
                return min(wait, 120.0)
    if response is not None and response.status_code == 429:
        return min(10.0 * 2**attempt, 120.0)  # rate limited with no hint: back off in tens of seconds
    return min(2.0**attempt, 30.0)


class TokenBudget:
    """Client-side per-minute pacing, so a long eval stays under a free or trial tier's limits
    instead of spending its retries on 429s. ``LLM_TOKENS_PER_MINUTE`` (e.g. 7000 for Groq's 8K
    TPM free tier, 25000 for Cerebras' trial) and ``LLM_REQUESTS_PER_MINUTE`` (e.g. 4 for the
    Cerebras trial's 5 RPM) turn it on; unset leaves calls unpaced. One budget per process."""

    def __init__(self, tpm: int, rpm: int = 0):
        self.tpm = tpm if tpm > 0 else 10**12
        self.rpm = rpm
        self._spent: deque[tuple[float, int]] = deque()
        self._lock = threading.Lock()

    @staticmethod
    def estimate(payload: dict) -> int:
        chars = sum(len(m.get("content") or "") for m in payload.get("messages", []))
        return int(chars / 3.5) + int(payload.get("max_tokens") or 0)

    def _wait_for(self, tokens: int, now: float) -> float:
        while self._spent and now - self._spent[0][0] >= 60.0:
            self._spent.popleft()
        tokens = min(tokens, self.tpm)
        used = sum(t for _, t in self._spent)
        if self.rpm and len(self._spent) >= self.rpm:
            return self._spent[len(self._spent) - self.rpm][0] + 60.0 - now
        if used + tokens <= self.tpm:
            self._spent.append((now, tokens))
            return 0.0
        # Wait until enough of the window has expired to fit this call.
        need, freed = used + tokens - self.tpm, 0
        for ts, t in self._spent:
            freed += t
            if freed >= need:
                return ts + 60.0 - now
        return 60.0

    def reserve(self, tokens: int) -> None:
        while True:
            with self._lock:
                wait = self._wait_for(tokens, time.monotonic())
            if wait <= 0:
                return
            logger.info("LLM pacing: waiting %.1fs to stay under %d tokens/min", wait, self.tpm)
            time.sleep(wait)

    async def areserve(self, tokens: int) -> None:
        while True:
            with self._lock:
                wait = self._wait_for(tokens, time.monotonic())
            if wait <= 0:
                return
            logger.info("LLM pacing: waiting %.1fs to stay under %d tokens/min", wait, self.tpm)
            await asyncio.sleep(wait)


_budget: TokenBudget | None = None


def _env_int(name: str) -> int:
    try:
        return max(0, int(os.getenv(name, "0")))
    except ValueError:
        return 0


def budget() -> TokenBudget | None:
    global _budget
    tpm, rpm = _env_int("LLM_TOKENS_PER_MINUTE"), _env_int("LLM_REQUESTS_PER_MINUTE")
    if not tpm and not rpm:
        return None
    if _budget is None or (_budget.tpm, _budget.rpm) != (tpm or 10**12, rpm):
        _budget = TokenBudget(tpm, rpm)
    return _budget


def post_with_retry(client: httpx.Client, url: str, *, attempts: int = 5, **kw) -> httpx.Response:
    last: Exception | None = None
    attempts = _attempts(attempts)
    if (b := budget()) is not None and "json" in kw:
        b.reserve(TokenBudget.estimate(kw["json"]))
    for attempt in range(attempts):
        try:
            r = client.post(url, **kw)
            if r.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                wait = _delay(attempt, r)
                logger.warning("LLM %s -> %s, retrying in %.1fs", url, r.status_code, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{e.response.status_code} from {url}: {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            last = e
            if attempt < attempts - 1:
                wait = _delay(attempt, None)
                logger.warning("LLM %s -> %s, retrying in %.1fs", url, e, wait)
                time.sleep(wait)
    raise LLMError(f"request to {url} failed: {last}") from last


async def apost_with_retry(client: httpx.AsyncClient, url: str, *, attempts: int = 5, **kw) -> httpx.Response:
    last: Exception | None = None
    attempts = _attempts(attempts)
    if (b := budget()) is not None and "json" in kw:
        await b.areserve(TokenBudget.estimate(kw["json"]))
    for attempt in range(attempts):
        try:
            r = await client.post(url, **kw)
            if r.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                wait = _delay(attempt, r)
                logger.warning("LLM %s -> %s, retrying in %.1fs", url, r.status_code, wait)
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{e.response.status_code} from {url}: {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            last = e
            if attempt < attempts - 1:
                wait = _delay(attempt, None)
                logger.warning("LLM %s -> %s, retrying in %.1fs", url, e, wait)
                await asyncio.sleep(wait)
    raise LLMError(f"request to {url} failed: {last}") from last
