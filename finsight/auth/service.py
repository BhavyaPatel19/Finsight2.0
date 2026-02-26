from datetime import datetime

from sqlmodel import Session, select

from finsight.models import User
from finsight.auth.security import get_password_hash, verify_password, create_access_token
from finsight.auth.schemas import UserCreate


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return session.exec(stmt).first()


def create_user(session: Session, data: UserCreate) -> User:
    user = User(
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
