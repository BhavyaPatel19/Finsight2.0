"""
Small in-process rate limiter for the auth endpoints (brute force /
credential stuffing). Fixed window per client IP; good enough for a
single-process deployment, and dependency-free.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self.window_s]
            if len(hits) >= self.limit:
                retry = int(self.window_s - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts, try again shortly",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)
            self._hits[key] = hits


auth_limiter = RateLimiter(limit=10, window_s=60.0)
