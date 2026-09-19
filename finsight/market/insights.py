"""
Groq-powered market insights for a given NSE stock symbol.
Accepts fundamentals data to produce context-rich, structured analysis.
In-memory cache with 2-hour TTL to keep insights fresh during market hours.
"""

import logging
import time
from typing import Optional


from finsight.llm import LLMError, generate, llm_configured

logger = logging.getLogger(__name__)

# Simple in-memory cache: symbol -> (text, expires_at_epoch)
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 2 * 60 * 60  # 2 hours

COMPANY_NAMES: dict[str, str] = {
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank",
    "INFY": "Infosys",
    "ITC": "ITC Limited",
    "SBIN": "State Bank of India",
    "BAJFINANCE": "Bajaj Finance",
    "BHARTIARTL": "Bharti Airtel",
    "LT": "Larsen & Toubro",
    "ICICIBANK": "ICICI Bank",
    "WIPRO": "Wipro",
    "HCLTECH": "HCL Technologies",
    "TATAMOTORS": "Tata Motors",
    "TATASTEEL": "Tata Steel",
    "NESTLEIND": "Nestle India",
    "HINDUNILVR": "Hindustan Unilever",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "AXISBANK": "Axis Bank",
    "MARUTI": "Maruti Suzuki",
    "ASIANPAINT": "Asian Paints",
}



def _format_metric(value, suffix="", prefix="", decimals=2):
    """Format a metric value for the prompt, return None if missing."""
    if value is None:
        return None
    if isinstance(value, float):
        return f"{prefix}{value:.{decimals}f}{suffix}"
    return f"{prefix}{value}{suffix}"


def _format_market_cap(mc):
    """Format market cap in human-readable form (Cr / L Cr)."""
    if mc is None:
        return None
    cr = mc / 1e7  # INR crores
    if cr >= 100000:
        return f"₹{cr / 100000:.2f}L Cr"
    return f"₹{cr:,.0f} Cr"


def _build_data_context(fundamentals: dict) -> str:
    """Build a concise data block from fundamentals dict."""
    if not fundamentals:
        return ""

    lines = []
    mappings = [
        ("pe_ratio", "P/E Ratio", "", "x"),
        ("pb_ratio", "P/B Ratio", "", "x"),
        ("roe", "ROE", "", "%"),
        ("roce", "ROCE", "", "%"),
        ("eps", "EPS", "₹", ""),
        ("debt_to_equity", "Debt/Equity", "", ""),
        ("dividend_yield", "Div Yield", "", "%"),
        ("book_value", "Book Value", "₹", ""),
    ]

    for key, label, prefix, suffix in mappings:
        val = fundamentals.get(key)
        formatted = _format_metric(val, suffix=suffix, prefix=prefix)
        if formatted:
            lines.append(f"  {label}: {formatted}")

    mc = _format_market_cap(fundamentals.get("market_cap"))
    if mc:
        lines.append(f"  Market Cap: {mc}")

    h52 = fundamentals.get("high_52w")
    l52 = fundamentals.get("low_52w")
    if h52 and l52:
        lines.append(f"  52W Range: ₹{l52:,.1f} – ₹{h52:,.1f}")

    sector = fundamentals.get("sector")
    industry = fundamentals.get("industry")
    if sector:
        ind_part = f" / {industry}" if industry else ""
        lines.append(f"  Sector: {sector}{ind_part}")

    if not lines:
        return ""
    return "CURRENT FUNDAMENTALS:\n" + "\n".join(lines)


def get_company_insight(
    symbol: str,
    sector: Optional[str] = None,
    fundamentals: Optional[dict] = None,
) -> str:
    if not llm_configured():
        return ""

    sym = symbol.upper()

    # Check cache
    if sym in _cache:
        text, expires = _cache[sym]
        if time.time() < expires:
            return text

    company_name = COMPANY_NAMES.get(sym, sym)
    data_context = _build_data_context(fundamentals)
    sector_hint = ""
    if not data_context and sector:
        sector_hint = f" (Sector: {sector})"

    prompt = f"""Analyze {company_name}{sector_hint}, an Indian listed company.
{data_context}

Respond in EXACTLY this format with no extra text:

OVERVIEW: One sentence on what the company does and its market position.

BULL CASE: One sentence on the strongest positive factor right now.

BEAR CASE: One sentence on the biggest risk or concern.

KEY METRIC: Highlight one standout number from the data above and what it signals.

VERDICT: One sentence overall assessment — is it looking strong, fair, or weak for a retail investor?"""

    try:
        insight = generate(prompt, max_tokens=400, temperature=0.3, timeout=30.0).text
        _cache[sym] = (insight, time.time() + _CACHE_TTL)
        return insight
    except LLMError as e:
        logger.warning("LLM insight failed for %s: %s", sym, e)
        return ""
