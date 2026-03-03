"""
BSE India corporate filings scraper.
Searches for annual reports, quarterly results, and other filings.
Downloads PDFs to the uploads/ directory.

Anti-bot measures:
- Rotating User-Agent pool
- Rate limiting with configurable delays
- Retry with exponential backoff
- Session-based cookies
"""
import os
import re
import time
import random
from typing import Any
from datetime import datetime, timedelta

import httpx

BSE_CORP_FILINGS_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w"
BSE_ANNUAL_REPORT_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w"

# Rotating User-Agent pool to avoid fingerprinting
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Rate limiting: minimum seconds between requests
_MIN_DELAY = 1.0
_MAX_DELAY = 2.5
_last_request_time = 0.0


def _get_headers() -> dict:
    """Get request headers with a random User-Agent."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }


def _rate_limit():
    """Enforce minimum delay between requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    delay = random.uniform(_MIN_DELAY, _MAX_DELAY)
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.time()


def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response | None:
    """Make an HTTP request with retry and exponential backoff."""
    _rate_limit()
    headers = kwargs.pop("headers", _get_headers())
    timeout = kwargs.pop("timeout", 20.0)
    kwargs.setdefault("follow_redirects", True)

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                # Pre-visit BSE homepage to grab cookies on first attempt
                if attempt == 0:
                    try:
                        client.get("https://www.bseindia.com/", headers=_get_headers(), timeout=10)
                        time.sleep(random.uniform(0.3, 0.8))
                    except Exception:
                        pass

                resp = getattr(client, method)(url, headers=headers, **kwargs)
                resp.raise_for_status()
                return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # Likely bot-blocked, wait longer
                wait = (2 ** attempt) * 3 + random.uniform(0, 2)
                time.sleep(wait)
                headers = _get_headers()  # rotate UA
                continue
            if e.response.status_code >= 500:
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
                continue
            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
            continue
        except Exception:
            return None
    return None


# ── Local company database for instant search ────────────
# BSE search APIs are heavily rate-limited and often return empty/blocked.
# This local DB provides instant results for top Indian companies.
_COMPANY_DB = [
    {"scrip_code": "500325", "company_name": "Reliance Industries Ltd", "symbol": "RELIANCE", "industry": "Oil & Gas"},
    {"scrip_code": "532540", "company_name": "Tata Consultancy Services Ltd", "symbol": "TCS", "industry": "IT"},
    {"scrip_code": "500209", "company_name": "Infosys Ltd", "symbol": "INFY", "industry": "IT"},
    {"scrip_code": "500180", "company_name": "HDFC Bank Ltd", "symbol": "HDFCBANK", "industry": "Banking"},
    {"scrip_code": "532174", "company_name": "ICICI Bank Ltd", "symbol": "ICICIBANK", "industry": "Banking"},
    {"scrip_code": "500875", "company_name": "ITC Ltd", "symbol": "ITC", "industry": "FMCG"},
    {"scrip_code": "500112", "company_name": "State Bank of India", "symbol": "SBIN", "industry": "Banking"},
    {"scrip_code": "532454", "company_name": "Bharti Airtel Ltd", "symbol": "BHARTIARTL", "industry": "Telecom"},
    {"scrip_code": "500247", "company_name": "Kotak Mahindra Bank Ltd", "symbol": "KOTAKBANK", "industry": "Banking"},
    {"scrip_code": "500510", "company_name": "Larsen & Toubro Ltd", "symbol": "LT", "industry": "Infrastructure"},
    {"scrip_code": "507685", "company_name": "Wipro Ltd", "symbol": "WIPRO", "industry": "IT"},
    {"scrip_code": "532281", "company_name": "HCL Technologies Ltd", "symbol": "HCLTECH", "industry": "IT"},
    {"scrip_code": "532215", "company_name": "Axis Bank Ltd", "symbol": "AXISBANK", "industry": "Banking"},
    {"scrip_code": "500570", "company_name": "Tata Motors Ltd", "symbol": "TATAMOTORS", "industry": "Automobile"},
    {"scrip_code": "500470", "company_name": "Tata Steel Ltd", "symbol": "TATASTEEL", "industry": "Steel"},
    {"scrip_code": "532500", "company_name": "Maruti Suzuki India Ltd", "symbol": "MARUTI", "industry": "Automobile"},
    {"scrip_code": "524715", "company_name": "Sun Pharmaceutical Industries Ltd", "symbol": "SUNPHARMA", "industry": "Pharma"},
    {"scrip_code": "500114", "company_name": "Titan Company Ltd", "symbol": "TITAN", "industry": "Consumer Goods"},
    {"scrip_code": "500034", "company_name": "Bajaj Finance Ltd", "symbol": "BAJFINANCE", "industry": "Finance"},
    {"scrip_code": "500820", "company_name": "Asian Paints Ltd", "symbol": "ASIANPAINT", "industry": "Paints"},
    {"scrip_code": "512599", "company_name": "Adani Enterprises Ltd", "symbol": "ADANIENT", "industry": "Conglomerate"},
    {"scrip_code": "532921", "company_name": "Adani Ports and SEZ Ltd", "symbol": "ADANIPORTS", "industry": "Infrastructure"},
    {"scrip_code": "532978", "company_name": "Bajaj Finserv Ltd", "symbol": "BAJAJFINSV", "industry": "Finance"},
    {"scrip_code": "500547", "company_name": "Bharat Petroleum Corporation Ltd", "symbol": "BPCL", "industry": "Oil & Gas"},
    {"scrip_code": "500087", "company_name": "Cipla Ltd", "symbol": "CIPLA", "industry": "Pharma"},
    {"scrip_code": "533278", "company_name": "Coal India Ltd", "symbol": "COALINDIA", "industry": "Mining"},
    {"scrip_code": "532488", "company_name": "Divi's Laboratories Ltd", "symbol": "DIVISLAB", "industry": "Pharma"},
    {"scrip_code": "500124", "company_name": "Dr. Reddy's Laboratories Ltd", "symbol": "DRREDDY", "industry": "Pharma"},
    {"scrip_code": "505200", "company_name": "Eicher Motors Ltd", "symbol": "EICHERMOT", "industry": "Automobile"},
    {"scrip_code": "500300", "company_name": "Grasim Industries Ltd", "symbol": "GRASIM", "industry": "Cement"},
    {"scrip_code": "500010", "company_name": "HDFC Ltd", "symbol": "HDFC", "industry": "Finance"},
    {"scrip_code": "500182", "company_name": "Hero MotoCorp Ltd", "symbol": "HEROMOTOCO", "industry": "Automobile"},
    {"scrip_code": "500440", "company_name": "Hindalco Industries Ltd", "symbol": "HINDALCO", "industry": "Metals"},
    {"scrip_code": "500696", "company_name": "Hindustan Unilever Ltd", "symbol": "HINDUNILVR", "industry": "FMCG"},
    {"scrip_code": "532187", "company_name": "IndusInd Bank Ltd", "symbol": "INDUSINDBK", "industry": "Banking"},
    {"scrip_code": "500228", "company_name": "JSW Steel Ltd", "symbol": "JSWSTEEL", "industry": "Steel"},
    {"scrip_code": "500520", "company_name": "Mahindra & Mahindra Ltd", "symbol": "M&M", "industry": "Automobile"},
    {"scrip_code": "500790", "company_name": "Nestle India Ltd", "symbol": "NESTLEIND", "industry": "FMCG"},
    {"scrip_code": "532555", "company_name": "NTPC Ltd", "symbol": "NTPC", "industry": "Power"},
    {"scrip_code": "500312", "company_name": "Oil and Natural Gas Corporation Ltd", "symbol": "ONGC", "industry": "Oil & Gas"},
    {"scrip_code": "532898", "company_name": "Power Grid Corporation of India Ltd", "symbol": "POWERGRID", "industry": "Power"},
    {"scrip_code": "540719", "company_name": "SBI Life Insurance Company Ltd", "symbol": "SBILIFE", "industry": "Insurance"},
    {"scrip_code": "500387", "company_name": "Shree Cement Ltd", "symbol": "SHREECEM", "industry": "Cement"},
    {"scrip_code": "500800", "company_name": "Tata Consumer Products Ltd", "symbol": "TATACONSUM", "industry": "FMCG"},
    {"scrip_code": "500400", "company_name": "Tata Power Company Ltd", "symbol": "TATAPOW", "industry": "Power"},
    {"scrip_code": "532755", "company_name": "Tech Mahindra Ltd", "symbol": "TECHM", "industry": "IT"},
    {"scrip_code": "532538", "company_name": "UltraTech Cement Ltd", "symbol": "ULTRACEMCO", "industry": "Cement"},
    {"scrip_code": "512070", "company_name": "UPL Ltd", "symbol": "UPL", "industry": "Chemicals"},
    {"scrip_code": "543257", "company_name": "Zomato Ltd", "symbol": "ZOMATO", "industry": "Internet"},
    {"scrip_code": "540180", "company_name": "Avenue Supermarts Ltd (DMart)", "symbol": "DMART", "industry": "Retail"},
    {"scrip_code": "500085", "company_name": "Chambal Fertilisers and Chemicals Ltd", "symbol": "CHAMBLFERT", "industry": "Fertilizers"},
    {"scrip_code": "500049", "company_name": "Bharat Electronics Ltd", "symbol": "BEL", "industry": "Defence"},
    {"scrip_code": "530965", "company_name": "Indian Oil Corporation Ltd", "symbol": "IOC", "industry": "Oil & Gas"},
    {"scrip_code": "500331", "company_name": "Pidilite Industries Ltd", "symbol": "PIDILITIND", "industry": "Chemicals"},
    {"scrip_code": "500680", "company_name": "Pfizer Ltd", "symbol": "PFIZER", "industry": "Pharma"},
    {"scrip_code": "532454", "company_name": "Bharti Airtel Ltd", "symbol": "BHARTIARTL", "industry": "Telecom"},
    {"scrip_code": "543066", "company_name": "Tata Elxsi Ltd", "symbol": "TATAELXSI", "industry": "IT"},
    {"scrip_code": "500185", "company_name": "Hindustan Petroleum Corp Ltd", "symbol": "HINDPETRO", "industry": "Oil & Gas"},
    {"scrip_code": "532978", "company_name": "Bajaj Finserv Ltd", "symbol": "BAJAJFINSV", "industry": "Finance"},
    {"scrip_code": "500295", "company_name": "Godrej Consumer Products Ltd", "symbol": "GODREJCP", "industry": "FMCG"},
    {"scrip_code": "532541", "company_name": "Voltas Ltd", "symbol": "VOLTAS", "industry": "Consumer Durables"},
    {"scrip_code": "500483", "company_name": "Tata Chemicals Ltd", "symbol": "TATACHEM", "industry": "Chemicals"},
    {"scrip_code": "500770", "company_name": "Tata Communications Ltd", "symbol": "TATACOMM", "industry": "Telecom"},
    {"scrip_code": "500900", "company_name": "Tata Investment Corp Ltd", "symbol": "TATAINVEST", "industry": "Finance"},
    {"scrip_code": "532155", "company_name": "Gail India Ltd", "symbol": "GAIL", "industry": "Gas"},
    {"scrip_code": "500103", "company_name": "Bharat Heavy Electricals Ltd", "symbol": "BHEL", "industry": "Engineering"},
    {"scrip_code": "532977", "company_name": "Bajaj Auto Ltd", "symbol": "BAJAJ-AUTO", "industry": "Automobile"},
    {"scrip_code": "500040", "company_name": "Century Textiles & Industries Ltd", "symbol": "CENTURYTEX", "industry": "Textiles"},
    {"scrip_code": "543320", "company_name": "Nykaa (FSN E-Commerce)", "symbol": "NYKAA", "industry": "E-Commerce"},
    {"scrip_code": "543396", "company_name": "Paytm (One97 Communications)", "symbol": "PAYTM", "industry": "Fintech"},
    {"scrip_code": "532978", "company_name": "Bajaj Finserv Ltd", "symbol": "BAJAJFINSV", "industry": "Finance"},
    {"scrip_code": "500483", "company_name": "Tata Metaliks Ltd", "symbol": "TATAMETALI", "industry": "Metals"},
]


def search_company(query: str) -> list[dict]:
    """
    Search for a company by name, symbol, or scrip code.
    Uses local database for instant results (BSE search APIs are heavily rate-limited).
    Returns list of {scrip_code, company_name, industry}.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []

    results = []
    for company in _COMPANY_DB:
        name = company["company_name"].lower()
        symbol = company.get("symbol", "").lower()
        scrip = company["scrip_code"]

        # Match against name, symbol, or scrip code
        if (query_lower in name
            or query_lower in symbol
            or query_lower == scrip
            or name.startswith(query_lower)
            or symbol.startswith(query_lower)):
            results.append({
                "scrip_code": scrip,
                "company_name": company["company_name"],
                "industry": company.get("industry", ""),
            })

    # Deduplicate by scrip_code
    seen = set()
    unique = []
    for r in results:
        if r["scrip_code"] not in seen:
            seen.add(r["scrip_code"])
            unique.append(r)

    return unique[:20]


def search_filings(
    scrip_code: str,
    category: str = "",
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    Search BSE corporate filings for a company.
    category: 'Board Meeting', 'Company Update', 'Result', etc. Leave empty for all.
    Returns list of {title, date, attachment_url, category, company}.
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
        resp = _request_with_retry("get", BSE_CORP_FILINGS_URL, params=params)
        if not resp:
            return []
        data = resp.json()

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


def search_annual_reports(scrip_code: str) -> list[dict]:
    """Search BSE for annual reports of a company."""
    try:
        resp = _request_with_retry(
            "get",
            BSE_ANNUAL_REPORT_URL,
            params={"scripcode": scrip_code},
        )
        if not resp:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []
        results = []
        for item in data[:10]:
            attachment = item.get("ATTACHMENT", "") or item.get("FilePath", "")
            if attachment and not attachment.startswith("http"):
                attachment = f"https://www.bseindia.com/{attachment}"
            results.append({
                "title": item.get("Year_Ended", "") or "Annual Report",
                "date": item.get("Year_Ended", ""),
                "category": "Annual Report",
                "attachment_url": attachment,
                "company": "",
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
        resp = _request_with_retry("get", url, timeout=60.0)
        if not resp:
            return None
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception:
        return None


# ── NSE symbol ↔ BSE scrip code mapping ──────────────────

# Common NSE → BSE mappings for major stocks
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
    "ADANIENT": "512599",
    "ADANIPORTS": "532921",
    "BAJAJFINSV": "532978",
    "BPCL": "500547",
    "CIPLA": "500087",
    "COALINDIA": "533278",
    "DIVISLAB": "532488",
    "DRREDDY": "500124",
    "EICHERMOT": "505200",
    "GRASIM": "500300",
    "HDFC": "500010",
    "HEROMOTOCO": "500182",
    "HINDALCO": "500440",
    "HINDUNILVR": "500696",
    "INDUSINDBK": "532187",
    "JSWSTEEL": "500228",
    "M&M": "500520",
    "NESTLEIND": "500790",
    "NTPC": "532555",
    "ONGC": "500312",
    "POWERGRID": "532898",
    "SBILIFE": "540719",
    "SHREECEM": "500387",
    "TATACONSUM": "500800",
    "TATAPOW": "500400",
    "TECHM": "532755",
    "ULTRACEMCO": "532538",
    "UPL": "512070",
}


def nse_to_bse(nse_symbol: str) -> str | None:
    """Convert NSE trading symbol to BSE scrip code.
    Falls back to dynamic BSE search if not in static map."""
    result = _SYMBOL_MAP.get(nse_symbol.upper())
    if result:
        return result

    # Dynamic lookup via BSE search API
    companies = search_company(nse_symbol)
    if companies:
        scrip = companies[0].get("scrip_code", "")
        if scrip:
            _SYMBOL_MAP[nse_symbol.upper()] = str(scrip)
            return str(scrip)
    return None


def add_symbol_mapping(nse_symbol: str, bse_scrip: str):
    """Add or update a symbol mapping."""
    _SYMBOL_MAP[nse_symbol.upper()] = str(bse_scrip)
