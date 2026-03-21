"""
Market data endpoints: live quotes, LTP, historical candles, instrument search,
and default watchlist from Kite Connect.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Holding, Portfolio, ZerodhaSession
from finsight.zerodha.client import fetch_quotes, fetch_ltp, fetch_historical, fetch_instruments

logger = logging.getLogger(__name__)
router = APIRouter()

# ── In-memory instrument cache ──
_instruments_cache: list[dict] = []

DEFAULT_WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC",
    "SBIN", "BAJFINANCE", "BHARTIARTL", "LT", "ICICIBANK",
]


def _get_access_token(session: Session, user_id: int) -> str | None:
    stmt = select(ZerodhaSession).where(ZerodhaSession.user_id == user_id)
    zs = session.exec(stmt).first()
    return zs.access_token if zs else None


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


def _ensure_instruments_loaded(access_token: str) -> None:
    """Load instruments into cache if not already loaded."""
    global _instruments_cache
    if _instruments_cache:
        return
    try:
        raw = fetch_instruments(access_token, "NSE")
        _instruments_cache = [
            {
                "instrument_token": int(i.get("instrument_token", 0)),
                "symbol": i.get("tradingsymbol", ""),
                "name": i.get("name", ""),
                "exchange": i.get("exchange", "NSE"),
                "segment": i.get("segment", ""),
                "instrument_type": i.get("instrument_type", ""),
            }
            for i in raw
            if i.get("tradingsymbol")
        ]
        logger.info("Loaded %d instruments into cache", len(_instruments_cache))
    except Exception as e:
        logger.warning("Failed to load instruments: %s", e)


@router.get("/quotes")
def get_quotes(
    symbols: str = Query(None, description="Comma-separated symbols like INFY,RELIANCE,TCS"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch full market quotes for given symbols or all portfolio holdings."""
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked. Connect first.")

    if symbols:
        sym_list = [f"NSE:{s.strip().upper()}" for s in symbols.split(",") if s.strip()]
    else:
        holding_symbols = _get_user_holding_symbols(session, current_user.id)
        sym_list = [f"NSE:{s}" for s in holding_symbols]

    if not sym_list:
        return {"quotes": {}}

    data = fetch_quotes(token, sym_list)
    return {"quotes": data}


@router.get("/ltp")
def get_ltp(
    symbols: str = Query(None, description="Comma-separated symbols"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch LTP for given symbols or all portfolio holdings."""
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked.")

    if symbols:
        sym_list = [f"NSE:{s.strip().upper()}" for s in symbols.split(",") if s.strip()]
    else:
        holding_symbols = _get_user_holding_symbols(session, current_user.id)
        sym_list = [f"NSE:{s}" for s in holding_symbols]

    if not sym_list:
        return {"ltp": {}}

    data = fetch_ltp(token, sym_list)
    result = {}
    for key, price in data.items():
        simple_key = key.split(":")[-1] if ":" in key else key
        result[simple_key] = price
    return {"ltp": result}


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
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked.")

    _ensure_instruments_loaded(token)

    inst_token = None
    for inst in _instruments_cache:
        if inst["symbol"].upper() == symbol.upper():
            inst_token = inst["instrument_token"]
            break

    # Fallback: fetch live if cache miss
    if not inst_token:
        instruments = fetch_instruments(token, "NSE")
        for inst in instruments:
            if inst.get("tradingsymbol", "").upper() == symbol.upper():
                inst_token = int(inst.get("instrument_token", 0))
                break

    if not inst_token:
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found on NSE")

    candles = fetch_historical(token, inst_token, interval, from_date, to_date)
    return {"symbol": symbol.upper(), "interval": interval, "candles": candles}


@router.get("/watchlist")
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch full quotes for default blue-chip watchlist stocks."""
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked. Connect first.")

    sym_list = [f"NSE:{s}" for s in DEFAULT_WATCHLIST]
    data = fetch_quotes(token, sym_list)
    return {"watchlist": DEFAULT_WATCHLIST, "quotes": data}


@router.get("/instruments/search")
def search_instruments(
    q: str = Query(..., min_length=1, description="Search query"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Search instruments by symbol or name. Returns top 15 matches."""
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked.")

    _ensure_instruments_loaded(token)

    query = q.strip().upper()
    results = []

    # Exact symbol match first
    for inst in _instruments_cache:
        if inst["symbol"].upper() == query:
            results.append(inst)
            break

    # Then prefix matches
    for inst in _instruments_cache:
        if inst in results:
            continue
        if inst["symbol"].upper().startswith(query):
            results.append(inst)
        if len(results) >= 15:
            break

    # Then name contains
    if len(results) < 15:
        for inst in _instruments_cache:
            if inst in results:
                continue
            if query in (inst.get("name", "") or "").upper():
                results.append(inst)
            if len(results) >= 15:
                break

    return {"results": results}


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
    """Return a Groq-generated AI insight using live fundamentals data."""
    from finsight.market.fundamentals import get_fundamentals
    from finsight.market.insights import get_company_insight

    fund_data = get_fundamentals(session, symbol.upper())
    if "error" in fund_data:
        fund_data = None

    text = get_company_insight(symbol.upper(), sector=sector, fundamentals=fund_data)
    return {"symbol": symbol.upper(), "insight": text}
