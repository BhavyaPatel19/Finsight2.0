from datetime import datetime

from sqlmodel import Session, select

from finsight.models import Portfolio, Holding, User, ZerodhaSession
from finsight.zerodha.client import (
    fetch_holdings,
    get_oauth_login_url,
    exchange_request_token,
)


def get_zerodha_token_for_user(session: Session, user_id: int) -> str | None:
    stmt = select(ZerodhaSession).where(ZerodhaSession.user_id == user_id).limit(1)
    row = session.exec(stmt).first()
    return row.access_token if row else None


def save_zerodha_token(session: Session, user_id: int, access_token: str) -> ZerodhaSession:
    stmt = select(ZerodhaSession).where(ZerodhaSession.user_id == user_id).limit(1)
    row = session.exec(stmt).first()
    now = datetime.utcnow()
    if row:
        row.access_token = access_token
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    row = ZerodhaSession(user_id=user_id, access_token=access_token)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_or_create_default_portfolio(session: Session, user_id: int) -> Portfolio:
    stmt = select(Portfolio).where(Portfolio.user_id == user_id).limit(1)
    portfolio = session.exec(stmt).first()
    if portfolio:
        return portfolio
    portfolio = Portfolio(user_id=user_id, name="Default")
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def sync_holdings_from_zerodha(
    session: Session, portfolio_id: int, access_token: str
) -> list[Holding]:
    """Sync holdings from Zerodha API into DB. Returns list of Holding."""
    raw = fetch_holdings(access_token)
    if not raw:
        return []
    # Clear existing and re-insert for simplicity (or upsert by symbol)
    existing = session.exec(select(Holding).where(Holding.portfolio_id == portfolio_id)).all()
    for h in existing:
        session.delete(h)
    now = datetime.utcnow()
    holdings = []
    for r in raw:
        h = Holding(
            portfolio_id=portfolio_id,
            symbol=r.get("symbol", ""),
            quantity=float(r.get("quantity", 0)),
            avg_price=float(r.get("avg_price", 0)),
            current_price=r.get("current_price"),
            last_updated_at=now,
        )
        session.add(h)
        holdings.append(h)
    session.commit()
    for h in holdings:
        session.refresh(h)
    return holdings


def get_holdings(session: Session, user_id: int) -> list[Holding]:
    portfolio = get_or_create_default_portfolio(session, user_id)
    stmt = select(Holding).where(Holding.portfolio_id == portfolio.id)
    return list(session.exec(stmt).all())


def sync_holdings_for_user(session: Session, user_id: int) -> list[Holding] | None:
    """Sync holdings from Zerodha into DB. Returns list of Holding or None if no token."""
    token = get_zerodha_token_for_user(session, user_id)
    if not token:
        return None
    portfolio = get_or_create_default_portfolio(session, user_id)
    return sync_holdings_from_zerodha(session, portfolio.id, token)
