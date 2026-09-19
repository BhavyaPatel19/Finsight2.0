"""
Groq-powered AI digest for watchlists.
Summarizes all stocks in a watchlist with notable movers, 52W extremes, sector patterns.
In-memory cache with 2-hour TTL.
"""

import logging
import time


from finsight.llm import LLMError, generate, llm_configured

logger = logging.getLogger(__name__)

_digest_cache: dict[int, tuple[str, float]] = {}
_DIGEST_TTL = 2 * 60 * 60  # 2 hours



def _build_stock_line(symbol: str, quote: dict, fund: dict) -> str:
    parts = [symbol]
    ltp = quote.get("last_price")
    prev = quote.get("ohlc", {}).get("close")
    if ltp:
        parts.append(f"LTP:₹{ltp:.1f}")
        if prev:
            chg = ((ltp - prev) / prev) * 100
            parts.append(f"Chg:{chg:+.1f}%")
    if fund.get("pe_ratio"):
        parts.append(f"PE:{fund['pe_ratio']:.1f}")
    mc = fund.get("market_cap")
    if mc:
        cr = mc / 1e7
        if cr >= 100000:
            parts.append(f"MCap:₹{cr / 100000:.1f}LCr")
        else:
            parts.append(f"MCap:₹{cr:,.0f}Cr")
    h52 = fund.get("high_52w")
    l52 = fund.get("low_52w")
    if h52 and ltp:
        if ltp >= h52 * 0.98:
            parts.append("NEAR_52W_HIGH")
        elif l52 and ltp <= l52 * 1.02:
            parts.append("NEAR_52W_LOW")
    if fund.get("sector"):
        parts.append(f"Sector:{fund['sector']}")
    return " | ".join(parts)


def generate_digest(
    watchlist_id: int,
    watchlist_name: str,
    symbols: list[str],
    quotes: dict,
    fundamentals: dict,
) -> str:
    if not llm_configured():
        return "AI digest unavailable (no LLM provider configured)."

    if watchlist_id in _digest_cache:
        text, expires = _digest_cache[watchlist_id]
        if time.time() < expires:
            return text

    stock_lines = []
    for sym in symbols:
        q = quotes.get(f"NSE:{sym}", {})
        f = fundamentals.get(sym, {})
        stock_lines.append(_build_stock_line(sym, q, f))

    data_block = "\n".join(stock_lines)

    prompt = f"""You are a concise financial analyst. Below is live data for {len(symbols)} stocks in watchlist "{watchlist_name}".

{data_block}

Write a 3-5 sentence digest summarizing:
1. Notable movers (biggest gainers/losers today)
2. Any stocks near 52-week highs or lows
3. Sector patterns if multiple stocks share a sector
4. One actionable observation

Be specific — use stock names and numbers. No disclaimers."""

    try:
        digest = generate(prompt, max_tokens=300, temperature=0.3, timeout=30.0).text
        _digest_cache[watchlist_id] = (digest, time.time() + _DIGEST_TTL)
        return digest
    except LLMError as e:
        logger.warning("Digest generation failed for watchlist %d: %s", watchlist_id, e)
        return "Could not generate digest. Please try again later."
