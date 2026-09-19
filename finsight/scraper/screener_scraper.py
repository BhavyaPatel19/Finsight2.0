"""
Screener.in scraper — company search and document discovery.
Searches for companies via Screener's JSON API and scrapes
document links (annual reports, concalls, announcements) from
company pages.

Anti-bot measures:
- Browser-like headers
- Rate limiting between requests
- Session cookies from homepage
"""
import os
import random
import re
import time

import httpx
from bs4 import BeautifulSoup

SCREENER_BASE = "https://www.screener.in"
SEARCH_URL = f"{SCREENER_BASE}/api/company/search/"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_MIN_DELAY = 0.8
_MAX_DELAY = 1.5
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    now = time.time()
    delay = random.uniform(_MIN_DELAY, _MAX_DELAY)
    if now - _last_request_time < delay:
        time.sleep(delay - (now - _last_request_time))
    _last_request_time = time.time()


def _get_headers():
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def _get_client() -> httpx.Client:
    """Create client with session cookies."""
    client = httpx.Client(timeout=20, follow_redirects=True)
    try:
        client.get(SCREENER_BASE, headers=_get_headers())
        time.sleep(random.uniform(0.3, 0.6))
    except Exception:
        pass
    return client


# ── Company Search ───────────────────────────────────

def search_company(query: str) -> list[dict]:
    """
    Search Screener.in for companies by name/symbol.
    Returns list of {id, name, symbol, url}.
    """
    if not query or len(query.strip()) < 2:
        return []

    _rate_limit()
    try:
        headers = _get_headers()
        headers["Accept"] = "application/json"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(SEARCH_URL, params={"q": query.strip()}, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data:
            url = item.get("url", "")
            # Extract symbol from URL like /company/TCS/consolidated/
            symbol_match = re.search(r"/company/([^/]+)/", url)
            symbol = symbol_match.group(1) if symbol_match else ""
            results.append({
                "id": item.get("id"),
                "name": item.get("name", ""),
                "symbol": symbol,
                "url": url,
            })
        return results
    except Exception:
        return []


# ── Document Discovery ───────────────────────────────

# Map Screener heading text → our category key
_HEADING_TO_CATEGORY = {
    "announcements": "announcement",
    "annual reports": "annual_report",
    "credit ratings": "credit_rating",
    "concalls": "concall",
}


def get_company_documents(symbol: str) -> dict:
    """
    Scrape a company's Screener page for all available documents.
    Returns {company_name, symbol, annual_reports, concalls, announcements, credit_ratings}.
    Each document: {title, url, category, date}.
    """
    url = f"{SCREENER_BASE}/company/{symbol}/consolidated/"
    _rate_limit()

    empty = {
        "company_name": symbol, "symbol": symbol,
        "annual_reports": [], "concalls": [], "announcements": [], "credit_ratings": [],
    }

    try:
        client = _get_client()
        try:
            resp = client.get(url, headers=_get_headers())
            if resp.status_code == 404:
                url = f"{SCREENER_BASE}/company/{symbol}/"
                resp = client.get(url, headers=_get_headers())
            resp.raise_for_status()
        finally:
            client.close()
    except Exception:
        return empty

    soup = BeautifulSoup(resp.text, "html.parser")

    # Get company name
    company_name = symbol
    h1 = soup.find("h1")
    if h1:
        company_name = h1.get_text(strip=True)

    result = {
        "company_name": company_name,
        "symbol": symbol,
        "annual_reports": [],
        "concalls": [],
        "announcements": [],
        "credit_ratings": [],
    }

    # ── Strategy 1: find <section id="documents"> and locate h3 headings ──
    doc_section = soup.find("section", id="documents")
    if doc_section:
        # Find ALL h3 headings inside the documents section (at any depth)
        for h3 in doc_section.find_all("h3"):
            heading_text = h3.get_text(strip=True).lower().strip()
            category = _HEADING_TO_CATEGORY.get(heading_text)
            if not category:
                for key, cat in _HEADING_TO_CATEGORY.items():
                    if key in heading_text:
                        category = cat
                        break
            if not category:
                continue

            # Walk up from h3 to find the container div with class "documents"
            container = None
            for ancestor in h3.parents:
                if ancestor.name == "section":
                    break
                if ancestor.name == "div":
                    ancestor_classes = " ".join(ancestor.get("class", []))
                    if "documents" in ancestor_classes:
                        container = ancestor
                        break
            if not container:
                # Fallback: use h3's grandparent
                container = h3.parent
                if container:
                    container = container.parent

            parsed = _parse_document_links(container, category)

            if category == "annual_report":
                result["annual_reports"].extend(parsed)
            elif category == "concall":
                result["concalls"].extend(parsed)
            elif category == "announcement":
                result["announcements"].extend(parsed)
            elif category == "credit_rating":
                result["credit_ratings"].extend(parsed)

    # ── Strategy 2 (fallback): scan entire page for heading matches ──
    if not any([result["annual_reports"], result["concalls"],
                result["announcements"], result["credit_ratings"]]):
        for section in soup.find_all(["div", "section"]):
            heading = section.find(["h2", "h3", "h4"])
            if not heading:
                continue
            heading_text = heading.get_text(strip=True).lower()
            for key, category in _HEADING_TO_CATEGORY.items():
                if key in heading_text:
                    parsed = _parse_document_links(section, category)
                    if category == "annual_report":
                        result["annual_reports"].extend(parsed)
                    elif category == "concall":
                        result["concalls"].extend(parsed)
                    elif category == "announcement":
                        result["announcements"].extend(parsed)
                    elif category == "credit_rating":
                        result["credit_ratings"].extend(parsed)
                    break

    return result


def _parse_document_links(section, category: str) -> list[dict]:
    """Extract document links from a section."""
    docs = []
    seen_urls = set()

    for link in section.find_all("a", href=True):
        href = link["href"]
        # Only include actual document links
        if not _is_document_url(href, category):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Get full text around the link for title
        title = link.get_text(strip=True)
        if not title or len(title) < 3:
            title = category.replace("_", " ").title()

        # Try to extract date from nearby text
        parent_li = link.find_parent("li")
        date_text = ""
        if parent_li:
            full_text = parent_li.get_text(" ", strip=True)
            # Look for patterns like "Financial Year 2024" or "Jan 2024" or dates
            fy_match = re.search(r"Financial Year (\d{4})", full_text)
            month_match = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{4})", full_text)
            if fy_match:
                date_text = f"FY {fy_match.group(1)}"
            elif month_match:
                date_text = f"{month_match.group(1)} {month_match.group(2)}"

        docs.append({
            "title": title,
            "url": href,
            "category": category,
            "date": date_text,
        })

    return docs


def _is_document_url(url: str, category: str = "") -> bool:
    """Check if URL points to a downloadable document or report."""
    if not url:
        return False
    url_lower = url.lower()
    # Skip internal screener links and anchors
    if url_lower.startswith("#") or url_lower.startswith("/"):
        return False
    if "screener.in" in url_lower:
        return False
    # BSE attachment URLs
    if "bseindia.com" in url_lower and ("attach" in url_lower or "annualreport" in url_lower.replace(" ", "")):
        return True
    # NSE archive URLs
    if "nseindia.com" in url_lower and "annual_reports" in url_lower:
        return True
    # Direct PDF links
    if url_lower.endswith(".pdf"):
        return True
    # Credit rating agency URLs
    if category == "credit_rating":
        rating_domains = ["icra", "crisil", "careratings", "care", "indiaratings", "standardandpoors", "spglobal", "moodys", "fitch"]
        if any(domain in url_lower for domain in rating_domains):
            return True
    # Company-hosted documents (e.g. tcs.com/investor-relations)
    if url_lower.endswith(".pdf") or "/investor" in url_lower:
        return True
    return False


# ── Download ─────────────────────────────────────────

def download_document(url: str, save_dir: str, filename: str | None = None) -> str | None:
    """
    Download a document PDF. Returns saved file path or None.
    """
    if not url:
        return None

    os.makedirs(save_dir, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1].split("?")[0]
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if not filename.lower().endswith(".pdf") and not filename.lower().endswith(".zip"):
        filename += ".pdf"
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath):
        return filepath

    _rate_limit()
    try:
        headers = _get_headers()
        headers["Referer"] = "https://www.screener.in/"
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            # Verify we got actual content, not an HTML error page
            ct = resp.headers.get("content-type", "")
            if "text/html" in ct and len(resp.content) < 5000:
                return None
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
    except Exception:
        return None
