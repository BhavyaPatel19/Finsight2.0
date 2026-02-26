"""
Market data endpoints: live quotes, LTP, and historical candles from Kite Connect.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Holding, ZerodhaSession
from finsight.zerodha.client import fetch_quotes, fetch_ltp, fetch_historical, fetch_instruments

router = APIRouter()


def _get_access_token(session: Session, user_id: int) -> str | None:
    stmt = select(ZerodhaSession).where(ZerodhaSession.user_id == user_id)
    zs = session.exec(stmt).first()
    return zs.access_token if zs else None


@router.get("/quotes")
def get_quotes(
    symbols: str = Query(None, description="Comma-separated symbols like INFY,RELIANCE,TCS"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch full market quotes for given symbols or all portfolio holdings.
    """
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked. Connect first.")

    if symbols:
        sym_list = [f"NSE:{s.strip().upper()}" for s in symbols.split(",") if s.strip()]
    else:
        # Fetch all portfolio holding symbols
        holdings = session.exec(
            select(Holding).where(Holding.user_id == current_user.id)
        ).all()
        sym_list = [f"NSE:{h.symbol}" for h in holdings]

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
    """
    Fetch LTP for given symbols or all portfolio holdings.
    """
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked.")

    if symbols:
        sym_list = [f"NSE:{s.strip().upper()}" for s in symbols.split(",") if s.strip()]
    else:
        holdings = session.exec(
            select(Holding).where(Holding.user_id == current_user.id)
        ).all()
        sym_list = [f"NSE:{h.symbol}" for h in holdings]

    if not sym_list:
        return {"ltp": {}}

    data = fetch_ltp(token, sym_list)
    # Simplify keys: 'NSE:INFY' -> 'INFY'
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
    """
    Fetch historical candle data for a single symbol.
    """
    token = _get_access_token(session, current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Zerodha not linked.")

    # We need the instrument_token for historical data
    # First try to find it from cached instruments, or fetch it
    instruments = fetch_instruments(token, "NSE")
    inst_token = None
    for inst in instruments:
        if inst.get("tradingsymbol", "").upper() == symbol.upper():
            inst_token = int(inst.get("instrument_token", 0))
            break

    if not inst_token:
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found on NSE")

    candles = fetch_historical(token, inst_token, interval, from_date, to_date)
    return {"symbol": symbol.upper(), "interval": interval, "candles": candles}
