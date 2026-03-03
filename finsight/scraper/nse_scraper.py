"""
NSE India corporate filings scraper.
Searches for annual reports, quarterly results, and other filings from NSE.

Anti-bot measures:
- Session cookie rotation (pre-visit NSE homepage for cookies)
- Rotating User-Agent pool (shared with BSE scraper)
- Rate limiting with random delays
- Retry with exponential backoff
- Proper Referer/Origin headers
"""
import os
import re
import time
import random
from datetime import datetime, timedelta

import httpx

from finsight.scraper.bse_scraper import (
    _USER_AGENTS,
    _rate_limit,
)

NSE_BASE = "https://www.nseindia.com"
NSE_CORP_INFO_URL = f"{NSE_BASE}/api/corporates-corporateActions"
NSE_ANNOUNCEMENTS_URL = f"{NSE_BASE}/api/corporate-announcements"
NSE_SEARCH_URL = f"{NSE_BASE}/api/search/autocomplete"
NSE_ANNUAL_REPORTS_URL = f"{NSE_BASE}/api/annual-reports"


def _get_nse_headers() -> dict:
    """Get NSE-specific request headers."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        "Origin": NSE_BASE,
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
    }


def _get_nse_session() -> httpx.Client:
    """Create an NSE session with cookies by pre-visiting the homepage."""
    client = httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers=_get_nse_headers(),
    )
    # Pre-visit NSE homepage to get session cookies — critical for anti-bot
    try:
        client.get(
            NSE_BASE,
            headers={
                "User-Agent": random.choice(_USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        time.sleep(random.uniform(0.5, 1.5))
    except Exception:
        pass
    return client


def _nse_request_with_retry(
    url: str,
    params: dict | None = None,
    max_retries: int = 3,
) -> httpx.Response | None:
    """NSE request with session cookies and retry logic."""
    _rate_limit()

    for attempt in range(max_retries):
        try:
            client = _get_nse_session()
            try:
                resp = client.get(url, params=params, headers=_get_nse_headers())
                resp.raise_for_status()
                return resp
            finally:
                client.close()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                wait = (2 ** attempt) * 4 + random.uniform(1, 3)
                time.sleep(wait)
                continue
            if e.response.status_code >= 500:
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
                continue
            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            wait = (2 ** attempt) * 2 + random.uniform(0, 2)
            time.sleep(wait)
            continue
        except Exception:
            return None
    return None


def search_nse_company(query: str) -> list[dict]:
    """
    Search NSE for a company by name.
    Returns list of {symbol, company_name, industry}.
    """
    try:
        resp = _nse_request_with_retry(
            NSE_SEARCH_URL,
            params={"q": query},
        )
        if not resp:
            return []
        data = resp.json()
        symbols = data.get("symbols", [])
        return [
            {
                "symbol": item.get("symbol", ""),
                "company_name": item.get("symbol_info", "") or item.get("symbol", ""),
                "industry": "",
            }
            for item in symbols[:15]
        ]
    except Exception:
        return []


def search_nse_announcements(
    symbol: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Search NSE corporate announcements for a symbol.
    Returns list of {title, date, attachment_url, category, company}.
    """
    if not to_date:
        to_date = datetime.now().strftime("%d-%m-%Y")
    if not from_date:
        from_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")

    params = {
        "index": "equities",
        "from_date": from_date,
        "to_date": to_date,
        "symbol": symbol.upper(),
    }

    try:
        resp = _nse_request_with_retry(NSE_ANNOUNCEMENTS_URL, params=params)
        if not resp:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []

        results = []
        for item in data[:30]:
            attachment = item.get("attchmntFile", "") or item.get("attchmntText", "")
            if attachment and not attachment.startswith("http"):
                attachment = f"{NSE_BASE}{attachment}" if attachment.startswith("/") else ""

            results.append({
                "title": item.get("desc", "").strip(),
                "date": item.get("an_dt", "") or item.get("dt", ""),
                "category": item.get("attchmntText", "Announcement"),
                "attachment_url": attachment,
                "company": item.get("sm_name", "") or symbol,
            })
        return results
    except Exception:
        return []


def download_nse_filing(url: str, save_dir: str, filename: str | None = None) -> str | None:
    """Download a filing from NSE. Returns the saved file path or None."""
    if not url:
        return None

    os.makedirs(save_dir, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1].split("?")[0]
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath):
        return filepath

    _rate_limit()
    try:
        client = _get_nse_session()
        try:
            resp = client.get(url, headers=_get_nse_headers(), timeout=60.0)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
        finally:
            client.close()
    except Exception:
        return None
