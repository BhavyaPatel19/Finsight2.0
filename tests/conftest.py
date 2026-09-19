"""Shared test fixtures for the FinSight test suite."""

import os

# Config refuses to load without a signing key; tests never mint real tokens.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import pytest  # noqa: E402
from sqlmodel import SQLModel, Session, create_engine

# Import all models so SQLModel registers their tables
from finsight.models import (  # noqa: F401
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
    DivisionSentiment,
    WalkTheTalkResult,
    ComparisonChunk,
)


@pytest.fixture()
def test_db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def tmp_chroma_dir(tmp_path, monkeypatch):
    """Temporary ChromaDB directory; patches config and resets singleton."""
    chroma_dir = str(tmp_path / "chroma_test")
    monkeypatch.setattr("finsight.config.CHROMA_PERSIST_DIR", chroma_dir)
    # Reset vectorstore singleton so it re-creates with patched path
    import finsight.credisentiment.vectorstore as vs_mod

    monkeypatch.setattr(vs_mod, "_collection", None)
    return chroma_dir


@pytest.fixture()
def sample_document(test_db_session):
    """A minimal Document row for testing."""
    doc = Document(
        symbol="TEST",
        doc_type="concall",
        status="pending",
        cs_status="pending",
        pdf_path="/fake/path.pdf",
    )
    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)
    return doc
