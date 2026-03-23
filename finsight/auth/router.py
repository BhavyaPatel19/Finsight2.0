from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import Session

from finsight.database.session import get_session
from finsight.auth.schemas import UserCreate, UserLogin, Token, UserResponse, UserUpdate
from finsight.auth.service import create_user, login_user, get_user_by_email, update_user, delete_user
from finsight.deps import get_current_user
from finsight.models import User

router = APIRouter()


@router.post("/register", response_model=UserResponse)
def register(
    data: UserCreate,
    session: Session = Depends(get_session),
):
    if not data.first_name.strip():
        raise HTTPException(status_code=400, detail="First name cannot be empty")
    if not data.last_name.strip():
        raise HTTPException(status_code=400, detail="Last name cannot be empty")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
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


@router.put("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if data.email and data.email != current_user.email:
        existing = get_user_by_email(session, data.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
    if data.first_name is not None and not data.first_name.strip():
        raise HTTPException(status_code=400, detail="First name cannot be empty")
    if data.last_name is not None and not data.last_name.strip():
        raise HTTPException(status_code=400, detail="Last name cannot be empty")
    if data.password is not None and len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    return update_user(session, current_user, data)


@router.delete("/me")
def delete_me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    delete_user(session, current_user)
    return {"ok": True}
