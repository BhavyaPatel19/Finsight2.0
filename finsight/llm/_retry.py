"""Small retry helper shared by HTTP-backed providers."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from finsight.llm.base import LLMError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _delay(attempt: int, response: httpx.Response | None) -> float:
    if response is not None:
        ra = response.headers.get("retry-after")
        if ra:
            try:
                return min(float(ra), 60.0)
            except ValueError:
                pass
    return min(2.0**attempt, 30.0)


def post_with_retry(client: httpx.Client, url: str, *, attempts: int = 5, **kw) -> httpx.Response:
    last: Exception | None = None
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
