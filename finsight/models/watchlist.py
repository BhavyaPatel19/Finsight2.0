from datetime import datetime

from sqlmodel import Field, SQLModel


class Watchlist(SQLModel, table=True):
    __tablename__ = "watchlists"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(default="My Watchlist")
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WatchlistItem(SQLModel, table=True):
    __tablename__ = "watchlist_items"

    id: int | None = Field(default=None, primary_key=True)
    watchlist_id: int = Field(foreign_key="watchlists.id", index=True)
    symbol: str = Field(index=True)
    notes: str | None = None
    added_at: datetime = Field(default_factory=datetime.utcnow)
