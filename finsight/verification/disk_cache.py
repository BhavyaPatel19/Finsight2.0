"""
Optional on-disk cache for Walk-the-Talk LLM work: extracted claims per document and one
verdict per (claim, evidence). Off unless WTT_DISK_CACHE names a directory.

Evaluation runs use it so a run stopped by a provider's daily quota (or a crash) resumes where
it left off instead of paying for the same calls again. Keys are SHA-256 over everything that
changes the answer — input text, model, prompt, evidence — so editing a prompt or re-indexing a
document misses the cache rather than serving a stale result. Failed calls are never stored.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def cache_dir() -> Path | None:
    d = os.getenv("WTT_DISK_CACHE", "").strip()
    return Path(d) if d else None


def key(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _path(kind: str, k: str) -> Path | None:
    d = cache_dir()
    return d / kind / f"{k}.json" if d else None


def get(kind: str, k: str) -> Any | None:
    p = _path(kind, k)
    if p is None or not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def put(kind: str, k: str, value: Any) -> None:
    p = _path(kind, k)
    if p is None:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False))
    tmp.replace(p)  # atomic: a killed run never leaves a half-written entry
