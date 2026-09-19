from sqlmodel import Session, SQLModel, create_engine

from finsight.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL or "sqlite:///./finsight.db",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Importing the models package registers them on SQLModel.metadata."""
    import finsight.models  # noqa: F401

    SQLModel.metadata.create_all(bind=engine)


def get_session():
    with Session(engine) as session:
        yield session
