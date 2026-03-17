# Architecture

**Analysis Date:** 2026-03-17

## Pattern Overview

**Overall:** Monolithic client-server with modular backend domain packaging

**Key Characteristics:**
- Backend is a single FastAPI application split into domain-bounded modules (one Python package per feature area)
- Frontend is a single-page React application communicating over HTTP REST; all routes are protected via `ProtectedLayout`
- No shared state between backend modules — all cross-module access goes through direct service function imports or SQLModel sessions
- Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`, removing any CORS friction during development

## Layers

**API Layer (Routers):**
- Purpose: Accept HTTP requests, validate inputs, call service functions, shape responses
- Location: `finsight/{module}/router.py` (one per domain module)
- Contains: FastAPI `APIRouter` instances, route handlers, Pydantic `response_model` declarations
- Depends on: Service layer, `finsight/deps.py` for auth guard, `finsight/database/session.py` for DB session
- Used by: FastAPI app (`finsight/main.py`) via `app.include_router`

**Service Layer:**
- Purpose: Business logic — computations, ML model calls, orchestration
- Location: `finsight/{module}/service.py`
- Contains: Pure functions receiving a `Session` argument; all DB writes happen here
- Depends on: SQLModel models, ML libraries (FinBERT, SentenceTransformers), Ollama HTTP client, ChromaDB
- Used by: Router handlers only

**Data Layer (Models):**
- Purpose: ORM table definitions used by all service layers
- Location: `finsight/models/` — one file per table, re-exported from `finsight/models/__init__.py`
- Contains: `SQLModel` classes with `table=True`
- Depends on: SQLModel, Python enums in `finsight/models/enums.py`
- Used by: All service layers, session init in `finsight/database/session.py`

**Schema Layer:**
- Purpose: Pydantic request/response shapes that are distinct from DB models
- Location: `finsight/{module}/schemas.py`
- Contains: Pydantic models for API input validation and typed response serialization
- Depends on: Nothing (pure Pydantic)
- Used by: Router handlers

**Frontend Pages:**
- Purpose: Full-page React components, each mapping to one URL route
- Location: `frontend/src/pages/`
- Contains: Local state via `useState`/`useEffect`; all data fetched from `frontend/src/api/client.js`
- Depends on: `AuthContext`, centralized `client.js` API module, Recharts for charts, Lucide for icons
- Used by: `App.jsx` route declarations

## Data Flow

**Authenticated API Request:**
1. React page calls a named function from `frontend/src/api/client.js` (e.g., `portfolioApi.holdings()`)
2. Axios interceptor in `client.js` reads `fs_token` from `localStorage` and injects `Authorization: Bearer <token>`
3. Vite proxy rewrites `/api/portfolio/holdings` → `http://127.0.0.1:8000/portfolio/holdings`
4. FastAPI router receives request; `Depends(get_current_user)` in `finsight/deps.py` validates JWT, fetches `User` from DB
5. Router calls service function (e.g., `get_holdings_with_metrics(session, user.id)`)
6. Service queries SQLite via SQLModel `Session`, computes results, returns plain dicts or ORM objects
7. Router wraps result in a Pydantic `response_model` and returns JSON
8. React page stores response in component state and renders

**RAG Query Pipeline:**
1. User selects documents in Chat page, clicks "Prepare" → `POST /rag/prepare`
2. `process_for_rag` in `finsight/rag/service.py`: extracts structured PDF text → page-aware chunks → BGE embeddings → ChromaDB + SQLite `DocumentChunk` rows
3. User submits question → `POST /rag/query`
4. `answer_question` embeds query with BGE-base-en-v1.5, retrieves top-30 dense hits from ChromaDB and top-30 BM25 hits from in-memory BM25 store
5. Reciprocal Rank Fusion merges both lists → cross-encoder reranker (`finsight/rag/reranker.py`) selects top-k
6. Strict grounding prompt built with section/page citations → sent to Ollama (DeepSeek-R1 or Llama 3.1 via `finsight/rag/service.py:call_ollama`)
7. `<think>...</think>` stripped from DeepSeek-R1 output; answer, thinking trace, navigation breadcrumbs, and source snippets returned

**Zerodha OAuth Flow:**
1. Frontend calls `GET /zerodha/connect-url` → backend returns ngrok-based redirect URL with short-lived JWT
2. Frontend opens that URL in a new browser tab → hits `/zerodha/connect-redirect?token=` → backend decodes JWT, sets `zerodha_link_uid` cookie, redirects to Zerodha login
3. Zerodha redirects back to `/zerodha/callback?request_token=&status=success`
4. Backend reads cookie, exchanges `request_token` for `access_token` via KiteConnect, saves to `ZerodhaSession` table
5. Frontend calls `POST /zerodha/sync` → backend reads holdings from Kite API, upserts into `Holding` table

**Sentiment Analysis Flow:**
1. User calls `POST /sentiment/recompute/{document_id}`
2. Service reads extracted text from `doc.text_path` on disk
3. FinBERT (ProsusAI/finbert) runs sentence-by-sentence, aggregating positive/negative/neutral probabilities
4. Result saved to `SentimentScore` table and returned

**State Management (Frontend):**
- Global auth state in `AuthContext` (React Context API), persisted to `localStorage` (`fs_token`, `fs_user`)
- All other state is local to individual page components; no Redux or Zustand
- 401 responses automatically clear localStorage and redirect to `/login` via Axios response interceptor

## Key Abstractions

**Domain Module:**
- Purpose: Self-contained feature area with its own router, service, schemas, and optionally models
- Examples: `finsight/rag/`, `finsight/sentiment/`, `finsight/credibility/`, `finsight/credisentiment/`
- Pattern: Each module exposes exactly one `router` imported by `finsight/main.py`

**`get_current_user` Dependency:**
- Purpose: Central auth guard reused by every protected route via FastAPI `Depends`
- Location: `finsight/deps.py`
- Pattern: Decodes JWT `sub` claim → queries `User` table → raises HTTP 401 on failure

**`get_session` Dependency:**
- Purpose: Yields a SQLModel `Session` that is automatically closed after each request
- Location: `finsight/database/session.py`
- Pattern: Generator-based FastAPI dependency; single global SQLite engine with `check_same_thread=False`

**API Client Module:**
- Purpose: Single Axios client instance with interceptors; exposes named API objects per domain
- Location: `frontend/src/api/client.js`
- Pattern: Named exports (`authApi`, `portfolioApi`, `ragApi`, etc.) group all calls per backend module; pages import only what they need

**ProtectedLayout:**
- Purpose: Route guard that redirects unauthenticated users to `/login`
- Location: `frontend/src/App.jsx`
- Pattern: Wraps every authenticated route in `<ProtectedLayout>` which checks `useAuth().user`

## Entry Points

**Backend:**
- Location: `finsight/main.py`
- Triggers: `uvicorn finsight.main:app --reload` from project root
- Responsibilities: Creates FastAPI app, registers CORS middleware, runs `init_db()` + `start_scheduler()` on startup, registers all 10 domain routers

**Frontend:**
- Location: `frontend/src/main.jsx`
- Triggers: `npm run dev` (Vite) or production build
- Responsibilities: Mounts React app into `#root`, wraps in `BrowserRouter` and `AuthProvider`

**Database Initialization:**
- Location: `finsight/database/session.py:init_db`
- Triggers: Called in FastAPI `lifespan` context manager at startup
- Responsibilities: Imports all SQLModel table classes and calls `SQLModel.metadata.create_all`

## Error Handling

**Strategy:** Fail-fast at router layer with explicit HTTP exceptions; service layer returns `None` or error dicts on failure rather than raising

**Patterns:**
- Router guards: `if not result: raise HTTPException(status_code=404, ...)`
- Auth failures: `get_current_user` raises HTTP 401; Axios interceptor on frontend catches 401 and clears session
- ML failures: `get_finbert_model()` returns `(None, None)` on import error; service falls back to a zero-score placeholder record
- LLM failures: `call_ollama` catches all exceptions and returns `"[LLM error: ...]"` string
- RAG processing: `process_for_rag` wraps entire pipeline in try/except; sets `doc.status = "error"` and saves `error_message`
- Scheduler jobs: Currently placeholder implementations that silently do nothing (`pass`)

## Cross-Cutting Concerns

**Logging:** Python `logging` module used in `finsight/market/router.py`; no centralized logging config — other modules use no logging

**Validation:** Pydantic schemas in `finsight/{module}/schemas.py` validate all request bodies; SQLModel field constraints validate DB writes

**Authentication:** Bearer JWT (HS256, 24h expiry) issued at login, validated on every request via `get_current_user` dependency; token stored in `localStorage`

**Background Jobs:** APScheduler `BackgroundScheduler` started in lifespan; two daily jobs registered (`fetch_docs`, `portfolio_snapshot`) but both are currently stub implementations

**Configuration:** All secrets and URLs loaded from `.env` via `python-dotenv` in `finsight/config.py`; fallback defaults present for all values

---

*Architecture analysis: 2026-03-17*
