"""
Scraper API endpoints: search BSE filings, download documents, auto-fetch for portfolio.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Holding, Document
from finsight.scraper.bse_scraper import (
    search_company,
    search_filings,
    download_filing,
    nse_to_bse,
    add_symbol_mapping,
)

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


@router.get("/search-company")
def api_search_company(query: str = Query(..., min_length=1)):
    """Search BSE for a company by name or scrip code."""
    results = search_company(query)
    return {"results": results}


@router.get("/filings")
def api_search_filings(
    symbol: str = Query(None, description="NSE symbol like INFY"),
    scrip_code: str = Query(None, description="BSE scrip code like 500209"),
    category: str = Query("", description="Filing category filter"),
    from_date: str = Query(None),
    to_date: str = Query(None),
    current_user: User = Depends(get_current_user),
):
    """
    Search BSE filings for a company.
    Pass either NSE symbol or BSE scrip_code.
    """
    if not symbol and not scrip_code:
        raise HTTPException(status_code=400, detail="Provide symbol or scrip_code")

    if symbol and not scrip_code:
        scrip_code = nse_to_bse(symbol)
        if not scrip_code:
            raise HTTPException(
                status_code=404,
                detail=f"No BSE mapping for {symbol}. Use scrip_code directly or add mapping."
            )

    filings = search_filings(scrip_code, category, from_date, to_date)
    return {"symbol": symbol, "scrip_code": scrip_code, "filings": filings}


@router.post("/download")
def api_download_filing(
    url: str = Query(..., description="Attachment URL from BSE"),
    symbol: str = Query("UNKNOWN", description="NSE symbol"),
    doc_type: str = Query("annual_report", description="Document type"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Download a filing PDF from BSE and register it as a Document.
    """
    filepath = download_filing(url, UPLOAD_DIR)
    if not filepath:
        raise HTTPException(status_code=500, detail="Failed to download filing")

    filename = os.path.basename(filepath)

    # Check if already registered
    existing = session.exec(
        select(Document).where(Document.pdf_path == filepath)
    ).first()
    if existing:
        return {"status": "already_exists", "document_id": existing.id, "filename": filename}

    doc = Document(
        symbol=symbol.upper(),
        doc_type=doc_type,
        pdf_path=filepath,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    return {"status": "downloaded", "document_id": doc.id, "filename": filename, "path": filepath}


@router.post("/auto-fetch")
def api_auto_fetch(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Auto-fetch filings for all portfolio holdings.
    Searches BSE for each holding's symbol and downloads available filings.
    """
    holdings = session.exec(
        select(Holding).where(Holding.user_id == current_user.id)
    ).all()

    if not holdings:
        return {"status": "no_holdings", "fetched": 0}

    results = []
    for h in holdings:
        bse_code = nse_to_bse(h.symbol)
        if not bse_code:
            results.append({"symbol": h.symbol, "status": "no_bse_mapping"})
            continue

        filings = search_filings(bse_code, category="Result")
        downloaded = 0
        for f in filings[:3]:  # Download up to 3 most recent filings per symbol
            if not f.get("attachment_url"):
                continue

            filepath = download_filing(f["attachment_url"], UPLOAD_DIR)
            if not filepath:
                continue

            # Check if already registered
            existing = session.exec(
                select(Document).where(Document.pdf_path == filepath)
            ).first()
            if existing:
                continue

            doc = Document(
                symbol=h.symbol.upper(),
                doc_type="quarterly_result",
                pdf_path=filepath,
            )
            session.add(doc)
            downloaded += 1

        session.commit()
        results.append({"symbol": h.symbol, "status": "ok", "downloaded": downloaded})

    return {"status": "done", "results": results}


@router.post("/add-mapping")
def api_add_mapping(
    nse_symbol: str = Query(...),
    bse_scrip: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Add or update an NSE → BSE symbol mapping."""
    add_symbol_mapping(nse_symbol, bse_scrip)
    return {"status": "ok", "nse_symbol": nse_symbol.upper(), "bse_scrip": bse_scrip}
