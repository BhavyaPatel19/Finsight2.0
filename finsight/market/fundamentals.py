"""
Fetch fundamental metrics for Indian stocks via yfinance.
Results are cached in SQLite for 24 hours to avoid rate limiting.
"""

import logging
from datetime import datetime, timedelta

from sqlmodel import Session, select

from finsight.models.stock_metrics import StockMetrics

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24


def _fetch_from_yfinance(symbol: str) -> dict:
    """
    Fetch fundamentals from Yahoo Finance for an NSE-listed stock.
    Returns a flat dict of metrics. Never raises — returns partial data on failure.
    """
    import yfinance as yf

    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
    except Exception as e:
        logger.warning("yfinance .info failed for %s: %s", symbol, e)
        return {}

    metrics = {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "eps": info.get("epsTrailingTwelveMonths"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "debt_to_equity": info.get("debtToEquity"),
        "book_value": info.get("bookValue"),
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }

    # Convert ROE from decimal (0.18) to percentage (18.0)
    if metrics["roe"] is not None:
        metrics["roe"] = round(metrics["roe"] * 100, 2)

    # Convert dividend yield from decimal to percentage
    if metrics["dividend_yield"] is not None:
        metrics["dividend_yield"] = round(metrics["dividend_yield"] * 100, 2)

    # Calculate ROCE: operating_income / (total_assets - current_liabilities)
    try:
        financials = ticker.financials
        balance = ticker.balance_sheet
        if financials is not None and balance is not None:
            op_income = financials.loc["Operating Income"].iloc[0] if "Operating Income" in financials.index else None
            total_assets = balance.loc["Total Assets"].iloc[0] if "Total Assets" in balance.index else None
            current_liab = balance.loc["Current Liabilities"].iloc[0] if "Current Liabilities" in balance.index else None
            if op_income and total_assets and current_liab:
                capital_employed = total_assets - current_liab
                if capital_employed > 0:
                    metrics["roce"] = round((op_income / capital_employed) * 100, 2)
    except Exception as e:
        logger.debug("ROCE calculation failed for %s: %s", symbol, e)

    return metrics


def get_fundamentals(session: Session, symbol: str) -> dict:
    """
    Get fundamentals for a stock, using SQLite cache with 24h TTL.
    Returns dict with all metric fields + symbol + fetched_at.
    """
    # Check cache
    stmt = select(StockMetrics).where(StockMetrics.symbol == symbol)
    cached = session.exec(stmt).first()

    if cached and cached.fetched_at:
        age = datetime.utcnow() - cached.fetched_at
        if age < timedelta(hours=CACHE_TTL_HOURS):
            return _model_to_dict(cached)

    # Fetch fresh from yfinance
    metrics = _fetch_from_yfinance(symbol)
    if not metrics:
        # yfinance failed — return cached data if available, else empty
        if cached:
            return _model_to_dict(cached)
        return {"symbol": symbol, "error": "Could not fetch metrics"}

    # Upsert into DB
    if cached:
        for key, val in metrics.items():
            if val is not None:
                setattr(cached, key, val)
        cached.fetched_at = datetime.utcnow()
    else:
        cached = StockMetrics(symbol=symbol, fetched_at=datetime.utcnow(), **metrics)
        session.add(cached)

    session.commit()
    session.refresh(cached)
    return _model_to_dict(cached)


def _model_to_dict(m: StockMetrics) -> dict:
    """Convert StockMetrics model to API response dict."""
    return {
        "symbol": m.symbol,
        "pe_ratio": m.pe_ratio,
        "pb_ratio": m.pb_ratio,
        "roe": m.roe,
        "roce": m.roce,
        "eps": m.eps,
        "dividend_yield": m.dividend_yield,
        "market_cap": m.market_cap,
        "debt_to_equity": m.debt_to_equity,
        "book_value": m.book_value,
        "high_52w": m.high_52w,
        "low_52w": m.low_52w,
        "promoter_holding": m.promoter_holding,
        "sector": m.sector,
        "industry": m.industry,
        "fetched_at": m.fetched_at.isoformat() if m.fetched_at else None,
    }
