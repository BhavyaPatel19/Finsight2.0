# Code Conventions

**Analysis Date:** 2026-03-17

## Python/Backend

### Style Guide
- No `pyproject.toml`, `.flake8`, or `setup.cfg` detected — no enforced linter or formatter configured.
- Code follows PEP 8 conventions by practice (snake_case functions, UPPER_CASE module-level constants).
- Imports are grouped: stdlib first, then third-party (`fastapi`, `sqlmodel`), then internal `finsight.*`.

### Type Annotations
- Service functions use full type annotations with return types: `def get_user_by_email(session: Session, email: str) -> User | None`
- Union types use the Python 3.10+ pipe syntax: `User | None`, `tuple[User, str] | None`
- Pydantic/SQLModel models serve as implicit type contracts for request/response bodies.
- Some service files (e.g., `finsight/sentiment/service.py`) omit return annotations on inner helpers.
- Lazy imports inside functions are used for heavy ML libraries (torch, transformers) to avoid slow startup — e.g., `finsight/sentiment/service.py` imports `torch` and `re` inside `compute_sentiment_for_document`.

### Error Handling Pattern
- Routers raise `HTTPException` directly when preconditions fail (missing resource, invalid input).
- Services return `None` on failure; routers check for `None` and raise accordingly:
  ```python
  # finsight/auth/router.py
  result = login_user(session, data.email, data.password)
  if not result:
      raise HTTPException(status_code=401, detail="Invalid email or password")
  ```
- External calls (Zerodha API, scraper, ML models) use bare `except Exception` blocks with logging or silent fallback:
  ```python
  # finsight/sentiment/service.py
  except Exception:
      return None, None   # graceful fallback to placeholder score
  ```
- `finsight/deps.py` validates JWT and raises `HTTPException(401)` with `WWW-Authenticate` headers.

### Logging
- Used selectively — only in `finsight/market/router.py`, `finsight/credibility/fundamentals.py`, `finsight/zerodha/client.py`, `finsight/portfolio/service.py`.
- Pattern: `logger = logging.getLogger(__name__)` at module level (or inside a function for lazily imported modules).
- No centralized logging config or log level configuration — relies on uvicorn defaults.
- Most routers and services have no logging at all.

### Module Structure Pattern
Each domain (auth, sentiment, credibility, market, etc.) follows this layout:
```
finsight/{domain}/
├── router.py     # FastAPI APIRouter — thin HTTP layer only
├── service.py    # Business logic, DB queries, ML calls
├── schemas.py    # Pydantic request/response models
└── (optional) client.py / fundamentals.py / scheduler.py
```
- Routers delegate entirely to service functions — no business logic in routers.
- Database session injected via `Depends(get_session)` from `finsight/database/session.py`.
- Auth guard injected via `Depends(get_current_user)` from `finsight/deps.py`.
- `finsight/models/__init__.py` re-exports all SQLModel table models with an explicit `__all__`.

### Naming Conventions
- Functions: `snake_case` (`get_user_by_email`, `compute_sentiment_for_document`)
- Classes/Models: `PascalCase` (`UserCreate`, `SentimentScore`, `ZerodhaSession`)
- Constants: `UPPER_SNAKE_CASE` (`DEFAULT_CHUNK_SIZE`, `DEFAULT_WATCHLIST`, `ALGORITHM`)
- Private helpers in routers: prefixed with underscore (`_get_access_token`, `_ensure_instruments_loaded`)
- Router variables: always named `router = APIRouter()`, re-exported as `router as {module}_router` in `main.py`
- Pydantic schema files named `schemas.py`; ORM files use the model name directly (e.g., `user.py`, `holding.py`)

### Docstrings
- Router endpoint functions use single-line docstrings describing the HTTP action:
  ```python
  """Return all documents for the document picker in RAG tab."""
  ```
- Service functions mostly lack docstrings; exceptions exist for complex ones like `get_finbert_model`.
- No Google/NumPy style multi-line docstrings observed.

---

## JavaScript/Frontend

### Component Patterns
- All components are functional — no class components.
- Default export per file; component name matches filename:
  ```jsx
  // frontend/src/pages/Sentiment.jsx
  export default function Sentiment() { ... }
  ```
- Page components live in `frontend/src/pages/`, shared UI in `frontend/src/components/`.
- Helper functions (formatters, color mappers) defined as `const` arrow functions at the top of each file before the component:
  ```jsx
  const scoreColor = (s) => { ... }
  const sentimentLabel = (s) => { ... }
  export default function Sentiment() { ... }
  ```

### State Management
- Local state only via `useState` — no Redux, Zustand, or other global state library.
- Global auth state via a hand-rolled React Context: `frontend/src/context/AuthContext.jsx`.
  - Provides `user`, `loading`, `login`, `register`, `logout`.
  - Consumed via `useAuth()` custom hook.
- API calls triggered inside components via `async` event handlers or `useEffect`.
- Loading state tracked with a dedicated `loading` boolean per page component.
- Error handling: `catch {}` blocks silently reset state to empty array/null; user-facing error messages displayed inline via string state (e.g., `syncMsg`).

### API Layer
- All HTTP calls centralized in `frontend/src/api/client.js`.
- Single Axios instance with base URL `/api` (proxied to FastAPI via Vite).
- Request interceptor attaches `Bearer {token}` from `localStorage.getItem('fs_token')`.
- Response interceptor handles 401 globally: clears localStorage and redirects to `/login`.
- API functions grouped by domain as named exports (`authApi`, `portfolioApi`, `marketApi`, etc.).

### Styling Approach
- Custom CSS classes via `frontend/src/index.css` (global stylesheet).
- Class names follow a flat BEM-lite style: `card`, `btn btn-primary btn-sm`, `badge badge-success`, `page-header`, `page-title`.
- Inline styles used for one-off spacing and color overrides — common and acceptable per codebase norms:
  ```jsx
  <div className="card mb-6" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
  ```
- No CSS modules, Tailwind, styled-components, or CSS-in-JS.
- Lucide React for icons (`import { TrendingUp, RefreshCw } from 'lucide-react'`).
- Recharts for all charting (`BarChart`, `AreaChart`, `ResponsiveContainer`, etc.).

### File Naming
- Pages: `PascalCase.jsx` (`Sentiment.jsx`, `CredibilitySentiment.jsx`)
- Components: `PascalCase.jsx` (`Sidebar.jsx`)
- API client: `camelCase.js` (`client.js`)
- Context: `PascalCase.jsx` (`AuthContext.jsx`)
- No index barrel files — each file imported directly by path.

### Import Order
1. React hooks (`import { useState, useEffect } from 'react'`)
2. Internal API client (`import { sentimentApi } from '../api/client'`)
3. Icon library (`import { TrendingUp } from 'lucide-react'`)
4. Charting library (`import { BarChart ... } from 'recharts'`)

---

## Git Conventions

### Branch Naming
- Feature branches observed: `panth-sentiment`, `working-dash-and-market`
- No enforced convention — branches named descriptively by feature or developer.

### Commit Style
- Conventional Commits format: `feat:`, `fix:`, `chore:` prefixes observed in recent history.
- Examples from log:
  - `feat: add Credibility Sentiment tab with division-level FinBERT and Walk the Talk LLM analysis`
  - `chore: add chroma_db vector store for working document search`
  - `feat: hybrid RAG pipeline with BM25, cross-encoder reranking, RAGAS evaluation`

### CI/CD
- No `.github/workflows/` directory — no CI pipeline configured.
- No `Dockerfile` or containerization detected.

---

*Convention analysis: 2026-03-17*
