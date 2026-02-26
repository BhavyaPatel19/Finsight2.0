"""
BSE India corporate filings scraper.
Searches for annual reports, quarterly results, and other filings.
Downloads PDFs to the uploads/ directory.
"""
import os
import re
import time
from typing import Any
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

BSE_CORP_FILINGS_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w"
BSE_ANNUAL_REPORT_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w"

# Common User-Agent to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


def search_company(query: str) -> list[dict]:
    """
    Search BSE for a company by name or scrip code.
    Returns list of {scrip_code, company_name, industry}.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                BSE_SEARCH_URL,
                params={"scripcode": "", "compname": query, "scripgrp": "", "segment": "Equity", "status": "Active"},
                headers=HEADERS,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                return []
            return [
                {
                    "scrip_code": item.get("SCRIP_CD", ""),
                    "company_name": item.get("LONG_NAME", "") or item.get("scrip_name", ""),
                    "industry": item.get("INDUSTRY", ""),
                }
                for item in data[:20]
            ]
    except Exception:
        return []


def search_filings(
    scrip_code: str,
    category: str = "",
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Search BSE corporate filings for a company.
    category: 'Board Meeting', 'Company Update', 'Result', etc. Leave empty for all.
    Returns list of {title, date, attachment_url, category}.
    """
    if not to_date:
        to_date = datetime.now().strftime("%Y%m%d")
    if not from_date:
        from_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    params = {
        "pageno": "1",
        "strCat": category,
        "strPrevDate": from_date,
        "strScrip": scrip_code,
        "strSearch": "P",
        "strToDate": to_date,
        "strType": "C",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(BSE_CORP_FILINGS_URL, params=params, headers=HEADERS)
            r.raise_for_status()
            data = r.json()

            if not isinstance(data, dict):
                return []

            table = data.get("Table", [])
            results = []
            for item in table:
                attachment = item.get("ATTACHMENTNAME", "")
                if attachment:
                    attachment_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attachment}"
                else:
                    attachment_url = ""

                results.append({
                    "title": item.get("NEWSSUB", "").strip(),
                    "date": item.get("NEWS_DT", ""),
                    "category": item.get("CATEGORYNAME", ""),
                    "attachment_url": attachment_url,
                    "company": item.get("SLONGNAME", ""),
                })
            return results
    except Exception:
        return []


def download_filing(url: str, save_dir: str, filename: str | None = None) -> str | None:
    """
    Download a filing PDF from BSE.
    Returns the saved file path or None on failure.
    """
    if not url:
        return None

    os.makedirs(save_dir, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1]
    # Sanitize filename
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath):
        return filepath

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(url, headers=HEADERS)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(r.content)
            return filepath
    except Exception:
        return None


# ── NSE symbol ↔ BSE scrip code mapping ──────────────────

# Common NSE → BSE mappings for major stocks (expandable)
_SYMBOL_MAP = {
    "RELIANCE": "500325",
    "TCS": "532540",
    "INFY": "500209",
    "HDFCBANK": "500180",
    "ICICIBANK": "532174",
    "ITC": "500875",
    "SBIN": "500112",
    "BHARTIARTL": "532454",
    "KOTAKBANK": "500247",
    "LT": "500510",
    "WIPRO": "507685",
    "HCLTECH": "532281",
    "AXISBANK": "532215",
    "TATAMOTORS": "500570",
    "TATASTEEL": "500470",
    "MARUTI": "532500",
    "SUNPHARMA": "524715",
    "TITAN": "500114",
    "BAJFINANCE": "500034",
    "ASIANPAINT": "500820",
}


def nse_to_bse(nse_symbol: str) -> str | None:
    """Convert NSE tradingsymbol to BSE scrip code. Returns None if not found."""
    return _SYMBOL_MAP.get(nse_symbol.upper())


def add_symbol_mapping(nse_symbol: str, bse_scrip: str):
    """Add or update a symbol mapping."""
    _SYMBOL_MAP[nse_symbol.upper()] = str(bse_scrip)
