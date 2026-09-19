"""Shared test fixtures for the FinSight test suite."""

import os

# Config refuses to load without a signing key; tests never mint real tokens.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine

# Import all models so SQLModel registers their tables
from finsight.models import (  # noqa: F401
    ComparisonChunk,
    CredibilityScore,
    DivisionSentiment,
    Document,
    DocumentChunk,
    DocumentSection,
    ExtractedClaim,
    FinancialMetric,
    Holding,
    PageMetadata,
    Portfolio,
    SentimentScore,
    User,
    WalkTheTalkResult,
    ZerodhaSession,
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


@pytest.fixture()
def api_client(monkeypatch):
    """FastAPI TestClient on a private in-memory DB shared across request threads.

    Patches the app engine so lifespan init_db() never touches finsight.db.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    import finsight.database.session as db
    from finsight.main import app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr("finsight.main.run_migrations", lambda: None)

    def _session():
        with Session(engine) as s:
            yield s

    from finsight.auth.ratelimit import auth_limiter

    auth_limiter.reset()
    app.dependency_overrides[db.get_session] = _session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def auth_headers(api_client):
    """Register + login a throwaway user; returns Bearer headers."""
    api_client.post("/auth/register", json={
        "first_name": "Test", "last_name": "User",
        "email": "test@example.com", "password": "secret-123",
    })
    r = api_client.post("/auth/login", json={"email": "test@example.com", "password": "secret-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
