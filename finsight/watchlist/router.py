"""
Watchlist CRUD endpoints: create, list, update, delete watchlists and their items.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User
from finsight.models.watchlist import Watchlist, WatchlistItem

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────


class WatchlistCreate(BaseModel):
    name: str
    is_default: bool = False


class WatchlistUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None


class ItemAdd(BaseModel):
    symbol: str
    notes: str | None = None


class ItemUpdate(BaseModel):
    notes: str | None = None


# ── Watchlist CRUD ───────────────────────────────────────


@router.get("/")
def list_watchlists(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all watchlists for the current user with item counts."""
    stmt = select(Watchlist).where(Watchlist.user_id == current_user.id)
    watchlists = session.exec(stmt).all()

    result = []
    for wl in watchlists:
        count_stmt = select(func.count()).where(WatchlistItem.watchlist_id == wl.id)
        item_count = session.exec(count_stmt).one()
        result.append(
            {
                "id": wl.id,
                "name": wl.name,
                "is_default": wl.is_default,
                "item_count": item_count,
                "created_at": wl.created_at.isoformat(),
                "updated_at": wl.updated_at.isoformat(),
            }
        )

    return result


@router.post("/")
def create_watchlist(
    body: WatchlistCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new watchlist."""
    if body.is_default:
        # Unset any existing default
        stmt = select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.is_default.is_(True),
        )
        for existing in session.exec(stmt).all():
            existing.is_default = False
            session.add(existing)

    wl = Watchlist(
        user_id=current_user.id,
        name=body.name,
        is_default=body.is_default,
    )
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return {"id": wl.id, "name": wl.name, "is_default": wl.is_default}


@router.get("/{watchlist_id}")
def get_watchlist(
    watchlist_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a watchlist with all its items."""
    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)
    items_stmt = select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id).order_by(WatchlistItem.added_at)
    items = session.exec(items_stmt).all()

    return {
        "id": wl.id,
        "name": wl.name,
        "is_default": wl.is_default,
        "items": [
            {
                "id": item.id,
                "symbol": item.symbol,
                "notes": item.notes,
                "added_at": item.added_at.isoformat(),
            }
            for item in items
        ],
    }


@router.put("/{watchlist_id}")
def update_watchlist(
    watchlist_id: int,
    body: WatchlistUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Rename or set watchlist as default."""
    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)

    if body.name is not None:
        wl.name = body.name

    if body.is_default is True:
        # Unset other defaults
        stmt = select(Watchlist).where(
            Watchlist.user_id == current_user.id,
            Watchlist.is_default.is_(True),
            Watchlist.id != watchlist_id,
        )
        for existing in session.exec(stmt).all():
            existing.is_default = False
            session.add(existing)
        wl.is_default = True

    wl.updated_at = datetime.utcnow()
    session.add(wl)
    session.commit()
    session.refresh(wl)
    return {"id": wl.id, "name": wl.name, "is_default": wl.is_default}


@router.delete("/{watchlist_id}")
def delete_watchlist(
    watchlist_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a watchlist and all its items."""
    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)

    # Delete items first
    items_stmt = select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id)
    for item in session.exec(items_stmt).all():
        session.delete(item)

    session.delete(wl)
    session.commit()
    return {"ok": True}


# ── Item CRUD ────────────────────────────────────────────


@router.post("/{watchlist_id}/items")
def add_item(
    watchlist_id: int,
    body: ItemAdd,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Add a stock to a watchlist. Skips if already present."""
    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)
    symbol = body.symbol.upper()

    # Check duplicate
    existing = session.exec(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == wl.id,
            WatchlistItem.symbol == symbol,
        )
    ).first()
    if existing:
        return {"id": existing.id, "symbol": existing.symbol, "notes": existing.notes, "duplicate": True}

    item = WatchlistItem(
        watchlist_id=wl.id,
        symbol=symbol,
        notes=body.notes,
    )
    session.add(item)

    wl.updated_at = datetime.utcnow()
    session.add(wl)

    session.commit()
    session.refresh(item)
    return {"id": item.id, "symbol": item.symbol, "notes": item.notes}


@router.put("/{watchlist_id}/items/{item_id}")
def update_item(
    watchlist_id: int,
    item_id: int,
    body: ItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update notes on a watchlist item."""
    _get_owned_watchlist(session, watchlist_id, current_user.id)

    item = session.exec(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.watchlist_id == watchlist_id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.notes = body.notes
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": item.id, "symbol": item.symbol, "notes": item.notes}


@router.delete("/{watchlist_id}/items/{symbol}")
def remove_item(
    watchlist_id: int,
    symbol: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a stock from a watchlist by symbol."""
    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)

    item = session.exec(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == wl.id,
            WatchlistItem.symbol == symbol.upper(),
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    session.delete(item)
    wl.updated_at = datetime.utcnow()
    session.add(wl)
    session.commit()
    return {"ok": True}


# ── Quotes for watchlist ─────────────────────────────────


@router.get("/{watchlist_id}/quotes")
def get_watchlist_quotes(
    watchlist_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Fetch quotes for all stocks in a watchlist via the active market provider."""
    from finsight.market.providers import MarketNotLinked, get_market_provider

    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)

    items = session.exec(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id)).all()
    if not items:
        return {"quotes": {}}

    try:
        provider = get_market_provider(session, current_user.id)
    except MarketNotLinked as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    sym_list = [f"NSE:{item.symbol}" for item in items]
    return {"quotes": provider.get_quotes(sym_list), "provider": provider.name}


# ── AI Digest ─────────────────────────────────────────────


@router.get("/{watchlist_id}/digest")
def get_watchlist_digest(
    watchlist_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Generate AI digest for all stocks in a watchlist."""
    from finsight.market.fundamentals import get_fundamentals
    from finsight.market.providers import MarketNotLinked, get_market_provider
    from finsight.watchlist.digest import generate_digest

    wl = _get_owned_watchlist(session, watchlist_id, current_user.id)

    items = session.exec(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id)).all()
    if not items:
        return {"digest": "This watchlist is empty. Add stocks to generate a digest."}

    symbols = [item.symbol for item in items]

    # Quotes are a nice-to-have for the digest; fundamentals carry it if they fail.
    quotes = {}
    try:
        provider = get_market_provider(session, current_user.id)
        quotes = provider.get_quotes([f"NSE:{s}" for s in symbols])
    except (MarketNotLinked, Exception) as e:
        logger.warning("digest: quotes unavailable: %s", e)

    # Fetch fundamentals (uses 24h cache)
    fund_data = {}
    for sym in symbols:
        try:
            fund_data[sym] = get_fundamentals(session, sym)
        except Exception:
            fund_data[sym] = {}

    digest_text = generate_digest(wl.id, wl.name, symbols, quotes, fund_data)
    return {"digest": digest_text}


# ── Helpers ──────────────────────────────────────────────


def _get_owned_watchlist(session: Session, watchlist_id: int, user_id: int) -> Watchlist:
    """Fetch a watchlist ensuring the current user owns it."""
    wl = session.exec(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == user_id,
        )
    ).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl
