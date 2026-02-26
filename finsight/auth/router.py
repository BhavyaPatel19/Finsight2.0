from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.auth.schemas import UserCreate, UserLogin, Token, UserResponse
from finsight.auth.service import create_user, login_user, get_user_by_email
from finsight.deps import get_current_user
from finsight.models import User

router = APIRouter()


@router.post("/register", response_model=UserResponse)
def register(
    data: UserCreate,
    session: Session = Depends(get_session),
):
    if get_user_by_email(session, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(session, data)
    return user


@router.post("/login", response_model=Token)
def login(
    data: UserLogin,
    session: Session = Depends(get_session),
):
    result = login_user(session, data.email, data.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user, token = result
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
