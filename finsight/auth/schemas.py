from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from finsight.auth.security import PASSWORD_MAX_BYTES


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} bytes")
    return v


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

    _password_ok = field_validator("password")(_check_password)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    created_at: datetime
    last_login_at: datetime | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v):
        return None if v is None else _check_password(v)

    class Config:
        from_attributes = True
