from datetime import datetime

from sqlmodel import SQLModel, Field


class ZerodhaSession(SQLModel, table=True):
    __tablename__ = "zerodha_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)
    access_token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
