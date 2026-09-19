"""
Fetch financial fundamentals from free web sources and compute
a credibility / quality score (0-100) for Indian stocks.

Sources tried in order:
  1. screener.in (public company page — no API key needed)

Scoring rubric (each factor 0-20, total 0-100):
  • P/E Ratio       → lower is better (< 15 = 20, > 40 = 0)
  • ROCE            → higher is better (> 20% = 20, < 5% = 0)
  • Debt/Equity     → lower is better (< 0.5 = 20, > 2 = 0)
  • Revenue Growth  → positive is good (> 15% = 20, negative = 0)
  • Promoter Hold.  → higher is better (> 60% = 20, < 30% = 0)
"""

import logging
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCREENER_URL = "https://www.screener.in/company/{symbol}/consolidated/"
SCREENER_STANDALONE_URL = "https://www.screener.in/company/{symbol}/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ── In-memory cache: symbol → (timestamp, result_dict) ──
_score_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 3600  # 1 hour


@dataclass
class FundamentalData:
    symbol: str
    pe: float | None = None
    roce: float | None = None
    debt_to_equity: float | None = None
    revenue_growth: float | None = None
    promoter_holding: float | None = None
    market_cap: float | None = None
    book_value: float | None = None
    dividend_yield: float | None = None
    source: str = "screener.in"


def _parse_number(text: str) -> float | None:
    """Parse a number from text like '1,234.56', '12.3%', '₹ 4,50,000 Cr.'"""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("₹", "").replace("%", "")
    text = text.replace("Cr.", "").replace("Cr", "").strip()
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _extract_ratio(soup: BeautifulSoup, label: str) -> float | None:
    """Find a ratio from screener.in's ratios list."""
    # Try the top ratios section first
    for li in soup.select("li.flex.flex-space-between"):
        name_el = li.select_one("span.name")
        value_el = li.select_one("span.number")
        if not name_el or not value_el:
            continue
        if label.lower() in name_el.get_text(strip=True).lower():
            return _parse_number(value_el.get_text(strip=True))

    # Fallback: search all text
    for el in soup.find_all(string=re.compile(label, re.IGNORECASE)):
        parent = el.parent
        if parent:
            # Look for adjacent number
            next_sibling = parent.find_next_sibling()
            if next_sibling:
                val = _parse_number(next_sibling.get_text(strip=True))
                if val is not None:
                    return val
    return None


def fetch_fundamentals_screener(symbol: str) -> FundamentalData | None:
    """Fetch fundamentals from screener.in for a given NSE symbol."""
    data = FundamentalData(symbol=symbol.upper())

    for url_tpl in [SCREENER_URL, SCREENER_STANDALONE_URL]:
        url = url_tpl.format(symbol=symbol.upper())
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                r = client.get(url, headers=HEADERS)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")

                # ── Top ratios section ──
                ratios_section = soup.select("ul#top-ratios li, li.flex.flex-space-between")
                for li in ratios_section:
                    name = li.select_one("span.name")
                    value = li.select_one("span.number, span.value")
                    if not name or not value:
                        continue
                    n = name.get_text(strip=True).lower()
                    v = _parse_number(value.get_text(strip=True))

                    if "stock p/e" in n or "p/e" in n:
                        data.pe = v
                    elif "roce" in n:
                        data.roce = v
                    elif "debt" in n and "equity" in n:
                        data.debt_to_equity = v
                    elif "book value" in n:
                        data.book_value = v
                    elif "dividend yield" in n:
                        data.dividend_yield = v
                    elif "market cap" in n:
                        data.market_cap = v

                # ── Revenue growth from P&L ──
                # Look for compounded sales growth in the growth section
                growth_tables = soup.select("table.ranges-table, section#profit-loss table")
                for table in growth_tables:
                    for row in table.select("tr"):
                        cells = row.select("td")
                        header = row.select_one("td, th")
                        if header and "sales growth" in header.get_text(strip=True).lower():
                            # Take the most recent value
                            for cell in reversed(cells[1:]):
                                val = _parse_number(cell.get_text(strip=True))
                                if val is not None:
                                    data.revenue_growth = val
                                    break

                # If no revenue growth found from table, try ratios
                if data.revenue_growth is None:
                    data.revenue_growth = _extract_ratio(soup, "Sales Growth")

                # ── Promoter holding ──
                shareholding_section = soup.select("section#shareholding table")
                for table in shareholding_section:
                    for row in table.select("tr"):
                        header = row.select_one("td")
                        if header and "promoter" in header.get_text(strip=True).lower():
                            cells = row.select("td")
                            # Get most recent quarter's value
                            for cell in reversed(cells[1:]):
                                val = _parse_number(cell.get_text(strip=True))
                                if val is not None:
                                    data.promoter_holding = val
                                    break
                            break

                logger.info(
                    "Fetched fundamentals for %s: PE=%s ROCE=%s D/E=%s RevGr=%s Prom=%s",
                    symbol,
                    data.pe,
                    data.roce,
                    data.debt_to_equity,
                    data.revenue_growth,
                    data.promoter_holding,
                )
                return data

        except Exception as e:
            logger.warning("Error fetching fundamentals for %s from %s: %s", symbol, url, e)
            continue

    return data  # Return partial data even if scraping partially failed


def compute_credibility_score(data: FundamentalData) -> float:
    """
    Compute a credibility/quality score 0-100 from fundamentals.
    Each factor contributes up to 20 points.
    """
    score = 0.0
    factors_counted = 0

    # 1. P/E Ratio (lower is better for value; 0-20)
    if data.pe is not None and data.pe > 0:
        factors_counted += 1
        if data.pe <= 12:
            score += 20
        elif data.pe <= 20:
            score += 18 - (data.pe - 12) * (8 / 8)  # 18→10
        elif data.pe <= 30:
            score += 10 - (data.pe - 20) * (6 / 10)  # 10→4
        elif data.pe <= 50:
            score += 4 - (data.pe - 30) * (4 / 20)  # 4→0
        else:
            score += 0

    # 2. ROCE (higher is better; 0-20)
    if data.roce is not None:
        factors_counted += 1
        if data.roce >= 25:
            score += 20
        elif data.roce >= 15:
            score += 12 + (data.roce - 15) * (8 / 10)
        elif data.roce >= 8:
            score += 5 + (data.roce - 8) * (7 / 7)
        elif data.roce >= 0:
            score += (data.roce / 8) * 5
        else:
            score += 0

    # 3. Debt-to-Equity (lower is better; 0-20)
    if data.debt_to_equity is not None:
        factors_counted += 1
        if data.debt_to_equity <= 0.1:
            score += 20
        elif data.debt_to_equity <= 0.5:
            score += 16 + (0.5 - data.debt_to_equity) * (4 / 0.4)
        elif data.debt_to_equity <= 1.0:
            score += 10 + (1.0 - data.debt_to_equity) * (6 / 0.5)
        elif data.debt_to_equity <= 2.0:
            score += (2.0 - data.debt_to_equity) * (10 / 1.0)
        else:
            score += 0

    # 4. Revenue Growth (positive is good; 0-20)
    if data.revenue_growth is not None:
        factors_counted += 1
        if data.revenue_growth >= 20:
            score += 20
        elif data.revenue_growth >= 10:
            score += 12 + (data.revenue_growth - 10) * (8 / 10)
        elif data.revenue_growth >= 0:
            score += (data.revenue_growth / 10) * 12
        elif data.revenue_growth >= -10:
            score += 0
        else:
            score += 0

    # 5. Promoter Holding (higher is better; 0-20)
    if data.promoter_holding is not None:
        factors_counted += 1
        if data.promoter_holding >= 70:
            score += 20
        elif data.promoter_holding >= 50:
            score += 12 + (data.promoter_holding - 50) * (8 / 20)
        elif data.promoter_holding >= 30:
            score += 5 + (data.promoter_holding - 30) * (7 / 20)
        elif data.promoter_holding >= 10:
            score += (data.promoter_holding - 10) * (5 / 20)
        else:
            score += 0

    # Normalize: if fewer factors available, scale up proportionally
    if factors_counted > 0 and factors_counted < 5:
        score = (score / (factors_counted * 20)) * 100
    elif factors_counted == 0:
        return 0.0

    return round(min(100, max(0, score)), 1)


def fetch_and_score(symbol: str) -> dict[str, Any]:
    """Fetch fundamentals and compute credibility score. Uses in-memory cache (1hr TTL)."""
    key = symbol.upper()

    # Check cache
    if key in _score_cache:
        cached_time, cached_result = _score_cache[key]
        if time.time() - cached_time < CACHE_TTL:
            logger.debug("Cache hit for %s", key)
            return cached_result

    fundamentals = fetch_fundamentals_screener(symbol)
    if not fundamentals:
        result = {"symbol": key, "score": None, "fundamentals": None}
        _score_cache[key] = (time.time(), result)
        return result

    score = compute_credibility_score(fundamentals)
    result = {
        "symbol": key,
        "score": score,
        "fundamentals": asdict(fundamentals),
    }
    _score_cache[key] = (time.time(), result)
    logger.info("Scored %s: %.1f/100 (PE=%s ROCE=%s)", key, score, fundamentals.pe, fundamentals.roce)
    return result
