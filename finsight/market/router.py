"""
Market data endpoints: quotes, LTP, historical candles, instrument search,
fundamentals, AI insights and news.

Price data comes from the active MarketDataProvider (yfinance by default,
Zerodha Kite when the user has linked a broker account).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.market.providers import MarketNotLinked, get_market_provider, market_status
from finsight.models import User, Holding, Portfolio

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC",
    "SBIN", "BAJFINANCE", "BHARTIARTL", "LT", "ICICIBANK",
]


def _provider(session: Session, user_id: int):
    try:
        return get_market_provider(session, user_id)
    except MarketNotLinked as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _get_user_holding_symbols(session: Session, user_id: int) -> list[str]:
    """Get all holding symbols for a user via the Portfolio → Holding join."""
    portfolio = session.exec(
        select(Portfolio).where(Portfolio.user_id == user_id)
    ).first()
    if not portfolio:
        return []
    holdings = session.exec(
        select(Holding).where(Holding.portfolio_id == portfolio.id)
    ).all()
    return [h.symbol for h in holdings]


def _symbols_or_holdings(session: Session, user_id: int, symbols: str | None) -> list[str]:
    if symbols:
        return [f"NSE:{s.strip().upper()}" for s in symbols.split(",") if s.strip()]
    return [f"NSE:{s}" for s in _get_user_holding_symbols(session, user_id)]


@router.get("/status")
def get_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Which price source is active for this user, and whether Zerodha is available."""
    return market_status(session, current_user.id)


@router.get("/quotes")
def get_quotes(
    symbols: str = Query(None, description="Comma-separated symbols like INFY,RELIANCE,TCS"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch full market quotes for given symbols or all portfolio holdings."""
    provider = _provider(session, current_user.id)
    sym_list = _symbols_or_holdings(session, current_user.id, symbols)
    if not sym_list:
        return {"quotes": {}, "provider": provider.name}
    return {"quotes": provider.get_quotes(sym_list), "provider": provider.name}


@router.get("/ltp")
def get_ltp(
    symbols: str = Query(None, description="Comma-separated symbols"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch LTP for given symbols or all portfolio holdings."""
    provider = _provider(session, current_user.id)
    sym_list = _symbols_or_holdings(session, current_user.id, symbols)
    if not sym_list:
        return {"ltp": {}}
    return {"ltp": provider.get_ltp(sym_list)}


@router.get("/history/{symbol}")
def get_history(
    symbol: str,
    interval: str = Query("day", description="minute, 5minute, 15minute, day"),
    from_date: str = Query(None),
    to_date: str = Query(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch historical candle data for a single symbol."""
    provider = _provider(session, current_user.id)
    candles = provider.get_history(symbol.upper(), interval, from_date, to_date)
    if not candles:
        raise HTTPException(status_code=404, detail=f"No history for {symbol.upper()} on NSE")
    return {"symbol": symbol.upper(), "interval": interval, "candles": candles, "provider": provider.name}


@router.get("/watchlist")
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch full quotes for default blue-chip watchlist stocks."""
    provider = _provider(session, current_user.id)
    sym_list = [f"NSE:{s}" for s in DEFAULT_WATCHLIST]
    return {"watchlist": DEFAULT_WATCHLIST, "quotes": provider.get_quotes(sym_list)}


@router.get("/instruments/search")
def search_instruments(
    q: str = Query(..., min_length=1, description="Search query"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Search instruments by symbol or name. Returns top 15 matches."""
    provider = _provider(session, current_user.id)
    return {"results": provider.search_instruments(q, limit=15)}


@router.get("/fundamentals/{symbol}")
def get_fundamentals_endpoint(
    symbol: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get fundamental metrics for a stock (PE, ROE, ROCE, etc.).
    Uses 24h SQLite cache to avoid excessive yfinance requests.
    """
    from finsight.market.fundamentals import get_fundamentals

    return get_fundamentals(session, symbol.upper())


@router.get("/insights/{symbol}")
def get_insights(
    symbol: str,
    sector: str = Query(None, description="Sector hint from fundamentals"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return an LLM-generated insight using live fundamentals data."""
    from finsight.market.fundamentals import get_fundamentals
    from finsight.market.insights import get_company_insight

    fund_data = get_fundamentals(session, symbol.upper())
    if "error" in fund_data:
        fund_data = None

    text = get_company_insight(symbol.upper(), sector=sector, fundamentals=fund_data)
    return {"symbol": symbol.upper(), "insight": text}


@router.get("/news/{symbol}")
def get_news(
    symbol: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch latest news headlines for a stock from Google News RSS."""
    from finsight.market.news import fetch_news

    articles = fetch_news(symbol.upper())
    return {"symbol": symbol.upper(), "articles": articles}
