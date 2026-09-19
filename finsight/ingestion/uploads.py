"""
One place that turns an UploadFile into a file on disk, safely.

Used by both upload endpoints (/ingestion and /credisentiment) so the
validation rules — allowed types, size cap, content sniff, sanitised names
that cannot escape DOCUMENTS_DIR — cannot drift apart.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from finsight import config

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".htm": "text/html",
    ".html": "text/html",
    ".txt": "text/plain",
}


def slug(value: str, max_len: int = 40) -> str:
    """Filesystem-safe token: user input never reaches a path unsanitised."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._-")[:max_len] or "doc"


def sniff_ok(suffix: str, head: bytes) -> bool:
    if suffix == ".pdf":
        return head.startswith(b"%PDF")
    if suffix in (".htm", ".html"):
        return b"<" in head[:512]
    return True


async def save_upload(
    file: UploadFile,
    *,
    symbol: str,
    fiscal_year: str | None = None,
    fiscal_quarter: str | None = None,
) -> Path:
    """Validate and persist an uploaded filing. Raises HTTPException on bad input."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="PDF, HTML or text file required")
    if not symbol.strip():
        raise HTTPException(status_code=400, detail="symbol required")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    if not sniff_ok(suffix, content[:1024]):
        raise HTTPException(status_code=400, detail=f"File content does not look like {suffix}")

    documents_dir = Path(config.DOCUMENTS_DIR)
    documents_dir.mkdir(parents=True, exist_ok=True)
    name = (
        f"{slug(symbol)}_{slug(fiscal_year or 'na', 10)}_{slug(fiscal_quarter or 'na', 10)}"
        f"_{uuid.uuid4().hex[:8]}_{slug(Path(file.filename).stem)}{suffix}"
    )
    path = (documents_dir / name).resolve()
    if documents_dir.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid file name")
    path.write_bytes(content)
    return path
