"""
Scraper API endpoints — uses Screener.in for company search and document discovery.
Flow: search company → view available docs → user picks → download selected → process → index.
"""
import os
import uuid
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Document
from finsight.scraper.screener_scraper import (
    search_company,
    get_company_documents,
    download_document,
)

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

# In-memory job tracker
_jobs: dict[str, dict] = {}


# ── Search ───────────────────────────────────────────

@router.get("/search-company")
def api_search_company(query: str = Query(..., min_length=1)):
    """Search Screener.in for companies by name or symbol."""
    results = search_company(query)
    return {"results": results}


@router.get("/company-documents")
def api_company_documents(
    symbol: str = Query(..., min_length=1, description="NSE symbol like TCS, INFY"),
    current_user: User = Depends(get_current_user),
):
    """
    Get all available documents for a company from Screener.in.
    Returns categorized lists of documents the user can choose to download.
    """
    docs = get_company_documents(symbol)
    return docs


# ── Download Selected ────────────────────────────────

class DownloadRequest(BaseModel):
    symbol: str
    company_name: str = ""
    documents: list[dict]  # [{url, title, category, date}]


def _run_download_selected(job_id: str, req: DownloadRequest):
    """Background worker: download and process selected documents."""
    from finsight.database.session import get_session as _get_session_gen

    job = _jobs[job_id]
    job["status"] = "downloading"

    session_gen = _get_session_gen()
    session = next(session_gen)

    try:
        total = len(req.documents)
        for i, doc_info in enumerate(req.documents):
            job["progress"] = i + 1
            job["total"] = total

            url = doc_info.get("url", "")
            if not url:
                continue

            # Check for existing doc
            existing = session.exec(
                select(Document).where(Document.source_url == url)
            ).first()
            if existing:
                job["documents"].append({
                    "document_id": existing.id,
                    "title": doc_info.get("title", ""),
                    "status": "already_exists",
                })
                continue

            # Download
            filepath = download_document(url, UPLOAD_DIR)
            if not filepath:
                job["documents"].append({
                    "title": doc_info.get("title", ""),
                    "status": "download_failed",
                })
                continue

            # Register in DB
            doc = Document(
                symbol=req.symbol.upper(),
                doc_type=doc_info.get("category", "filing"),
                source_url=url,
                pdf_path=filepath,
                file_size=os.path.getsize(filepath) if os.path.exists(filepath) else None,
                company_name=req.company_name or req.symbol,
                fiscal_year=doc_info.get("date", ""),
                status="pending",
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

            job["documents"].append({
                "document_id": doc.id,
                "title": doc_info.get("title", ""),
                "status": "downloaded",
            })

        job["status"] = "done"
        job["message"] = f"Processed {len([d for d in job['documents'] if d.get('status') == 'indexed'])} documents"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[:500]
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


@router.post("/download-selected")
def api_download_selected(
    req: DownloadRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Download user-selected documents. Runs in background.
    Returns a job_id to poll for status.
    """
    if not req.documents:
        raise HTTPException(status_code=400, detail="No documents selected")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "company_name": req.company_name or req.symbol,
        "symbol": req.symbol,
        "total": len(req.documents),
        "progress": 0,
        "documents": [],
        "error": None,
        "message": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    thread = threading.Thread(
        target=_run_download_selected,
        args=(job_id, req),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}")
def api_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
