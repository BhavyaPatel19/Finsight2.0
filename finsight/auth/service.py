from datetime import datetime

from sqlmodel import Session, select

from finsight.models import User, Watchlist, WatchlistItem, Portfolio, Holding, ZerodhaSession
from finsight.auth.security import get_password_hash, verify_password, create_access_token
from finsight.auth.schemas import UserCreate, UserUpdate


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return session.exec(stmt).first()


def create_user(session: Session, data: UserCreate) -> User:
    user = User(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=data.email,
        hashed_password=get_password_hash(data.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(session, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return user


def login_user(session: Session, email: str, password: str) -> tuple[User, str] | None:
    user = authenticate_user(session, email, password)
    if not user:
        return None
    token = create_access_token(data={"sub": str(user.id)})
    return user, token


def update_user(session: Session, user: User, data: UserUpdate) -> User:
    if data.first_name is not None:
        user.first_name = data.first_name.strip()
    if data.last_name is not None:
        user.last_name = data.last_name.strip()
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.hashed_password = get_password_hash(data.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user: User) -> None:
    watchlists = session.exec(select(Watchlist).where(Watchlist.user_id == user.id)).all()
    watchlist_ids = [w.id for w in watchlists if w.id is not None]
    if watchlist_ids:
        for item in session.exec(select(WatchlistItem).where(WatchlistItem.watchlist_id.in_(watchlist_ids))).all():
            session.delete(item)
    for wl in watchlists:
        session.delete(wl)

    portfolios = session.exec(select(Portfolio).where(Portfolio.user_id == user.id)).all()
    portfolio_ids = [p.id for p in portfolios if p.id is not None]
    if portfolio_ids:
        for holding in session.exec(select(Holding).where(Holding.portfolio_id.in_(portfolio_ids))).all():
            session.delete(holding)
    for p in portfolios:
        session.delete(p)

    zsession = session.exec(select(ZerodhaSession).where(ZerodhaSession.user_id == user.id)).first()
    if zsession:
        session.delete(zsession)

    session.delete(user)
    session.commit()
