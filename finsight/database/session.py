from sqlmodel import SQLModel, create_engine, Session

from finsight.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL or "sqlite:///./finsight.db",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """
    Import models and create tables.
    """
    from finsight.models import (
        User,
        Portfolio,
        Holding,
        Document,
        DocumentChunk,
        FinancialMetric,
        SentimentScore,
        ExtractedClaim,
        CredibilityScore,
        ZerodhaSession,
        PageMetadata,
        DocumentSection,
    )  # noqa: F401

    SQLModel.metadata.create_all(bind=engine)


def get_session():
    with Session(engine) as session:
        yield session

