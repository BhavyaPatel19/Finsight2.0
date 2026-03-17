# Testing

**Analysis Date:** 2026-03-17

## Current Coverage

### Backend Tests
**Status: None**

No test files exist anywhere under `C:/Users/This PC/Desktop/8thsem/finsight/`. There is no `tests/` directory, no `test_*.py` files, and no `conftest.py`. The `requirements.txt` contains no testing dependencies (`pytest`, `httpx` for async tests, `pytest-asyncio`, etc. are all absent).

### Frontend Tests
**Status: None**

`frontend/package.json` contains no test script, no test runner (`vitest`, `jest`), and no related dev dependencies. No `*.test.jsx`, `*.spec.js`, or `__tests__/` directories exist anywhere under `frontend/src/`.

### Integration Tests
**Status: None**

No end-to-end or integration test setup detected. No Playwright, Cypress, or similar framework referenced anywhere in the project.

---

## Testing Tools

**None configured.** The project has zero testing infrastructure:

| Layer | Framework | Config File | Status |
|---|---|---|---|
| Backend unit tests | None | None | Not present |
| Backend API tests | None | None | Not present |
| Frontend unit tests | None | None | Not present |
| Frontend E2E tests | None | None | Not present |
| CI pipeline | None | None | Not present |

---

## Test Gaps

Every part of the application is untested. Priority gaps by risk:

### Critical — Authentication & Authorization
- `finsight/auth/service.py`: `create_user`, `authenticate_user`, `login_user` — core security logic with no tests.
- `finsight/deps.py`: `get_current_user` JWT validation — incorrect behavior here bypasses all auth guards.
- `finsight/auth/router.py`: `/register`, `/login`, `/me` endpoints — no test for duplicate email, bad password, expired token.

### Critical — RAG Pipeline
- `finsight/rag/service.py`: The hybrid BM25 + cross-encoder + ChromaDB retrieval pipeline is complex and has many edge cases (empty results, bad queries, model failures).
- `finsight/rag/evaluation.py`: RAGAS evaluation logic wraps an external LLM — needs mocking and contract tests.
- No tests for the `/rag/query` endpoint response shape.

### High — ML Model Services
- `finsight/sentiment/service.py`: `compute_sentiment_for_document` — no test for FinBERT load failure fallback, empty text, or score aggregation math.
- `finsight/credibility/service.py`: Claim extraction and credibility scoring — LLM-dependent, needs mocked tests.
- `finsight/credibility/fundamentals.py`: Screener.in scraping + scoring — no tests; scraper failures silently return zero scores.

### High — Data Integrity
- `finsight/portfolio/service.py`: Holdings metrics computation — financial calculations are untested.
- `finsight/ingestion/service.py` and `finsight/ingestion/file_manager.py`: PDF upload, chunking, and ChromaDB indexing — file system side effects make these hard to test but high value.

### Medium — API Contract Tests
- No endpoint response schema tests — any breaking change to a router's return structure would not be caught.
- Zerodha OAuth flow (`finsight/zerodha/router.py`) is entirely untested.

### Medium — Frontend Logic
- `frontend/src/api/client.js`: Axios interceptors (401 redirect, token injection) — pure JS logic that could be unit tested.
- `frontend/src/context/AuthContext.jsx`: Auth state machine (`login`, `logout`, token refresh) — testable with React Testing Library.
- Formatter helpers (`fmtCcy`, `scoreColor`, `sentimentLabel`) in page components — pure functions, trivially testable.

### Low — Configuration
- `finsight/config.py`: Default fallback values not validated.

---

## Recommendations

### Immediate (highest ROI)

**1. Add pytest + httpx for backend API tests**

Install:
```
pytest
pytest-asyncio
httpx
```

Create `tests/conftest.py` with an in-memory SQLite test session and FastAPI `TestClient`:
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from finsight.main import app
from finsight.database.session import get_session

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)
```

**2. Test auth endpoints first**

```python
# tests/test_auth.py
def test_register_and_login(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "pass"})
    assert r.status_code == 200

    r = client.post("/auth/login", json={"email": "a@b.com", "password": "pass"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "a@b.com", "password": "pass"})
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "pass"})
    assert r.status_code == 400
```

**3. Test service layer with mocked ML**

Mock FinBERT in sentiment tests so they run without GPU/model download:
```python
# tests/test_sentiment.py
from unittest.mock import patch, MagicMock

def test_compute_sentiment_no_model(session, tmp_path):
    # Create a document with a text file
    text_file = tmp_path / "doc.txt"
    text_file.write_text("Revenue grew 20%. Debt remains elevated.")
    ...
    with patch("finsight.sentiment.service.get_finbert_model", return_value=(None, None)):
        result = compute_sentiment_for_document(session, doc.id)
    assert result.overall_score == 0.0  # fallback placeholder
```

**4. Add vitest to frontend**

Install:
```
vitest
@testing-library/react
@testing-library/user-event
jsdom
```

Test the pure formatter functions and the API client interceptors:
```javascript
// frontend/src/pages/Sentiment.test.jsx
import { describe, it, expect } from 'vitest'
import { scoreColor, sentimentLabel } from './Sentiment'

describe('scoreColor', () => {
  it('returns green for positive scores', () => {
    expect(scoreColor(0.5)).toBe('#22d3a5')
  })
  it('returns red for negative scores', () => {
    expect(scoreColor(-0.5)).toBe('#f43f5e')
  })
})
```

### Short-term

- Add contract tests for every router's response schema using `response_model` assertions via `TestClient`.
- Add a `Makefile` or `pyproject.toml` with a `[tool.pytest.ini_options]` section to standardize test invocation.
- Test `finsight/portfolio/service.py` financial calculations against known inputs/outputs.

### Longer-term

- Add Playwright or Cypress for E2E flows: register → upload document → run sentiment → view chart.
- Set up GitHub Actions CI to run tests on every push to `main`.
- Add coverage reporting with `pytest-cov`; target 70%+ for `finsight/auth/`, `finsight/portfolio/`, and `finsight/rag/`.

---

*Testing analysis: 2026-03-17*
