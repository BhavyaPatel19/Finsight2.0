from datetime import datetime

from sqlmodel import Field, SQLModel


class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolios"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(default="Default")
    created_at: datetime = Field(default_factory=datetime.utcnow)
