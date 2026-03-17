# Codebase Structure

**Analysis Date:** 2026-03-17

## Directory Layout

```
8thsem/                        # Project root (run uvicorn from here)
├── finsight/                  # Backend Python package
│   ├── main.py                # FastAPI app creation + router registration
│   ├── config.py              # All env-driven configuration
│   ├── deps.py                # Shared FastAPI dependencies (get_current_user)
│   ├── database/              # DB engine + session factory
│   ├── models/                # SQLModel ORM table definitions
│   ├── auth/                  # JWT auth — register, login, /me
│   ├── zerodha/               # Zerodha Kite Connect OAuth + holdings sync
│   ├── portfolio/             # Portfolio metrics over synced holdings
│   ├── ingestion/             # PDF upload, text extraction, chunking, scheduler
│   ├── rag/                   # Hybrid RAG pipeline (BM25 + ChromaDB + reranker)
│   ├── sentiment/             # FinBERT document-level sentiment scoring
│   ├── credibility/           # Claim extraction + credibility scoring
│   ├── credisentiment/        # Division-level sentiment + Walk-the-Talk LLM
│   ├── market/                # Live quotes, LTP, historical candles, instrument search
│   └── scraper/               # BSE/NSE/Screener.in PDF scrapers
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── main.jsx           # React DOM mount point
│   │   ├── App.jsx            # Route declarations + ProtectedLayout
│   │   ├── api/client.js      # Axios client + all API call functions
│   │   ├── context/           # AuthContext (global auth state)
│   │   ├── components/        # Shared UI components (Sidebar)
│   │   └── pages/             # One file per route/page
│   ├── vite.config.js         # Vite + /api proxy config
│   └── package.json
├── chroma_db/                 # ChromaDB persisted vector store (auto-created)
├── documents/                 # Downloaded PDFs + extracted .txt files (auto-created)
├── uploads/                   # User-uploaded PDFs (auto-created)
├── finsight.db                # SQLite database file (auto-created)
├── requirements.txt           # Python dependencies
└── .env                       # Secrets (not committed)
```

## Directory Purposes

**`finsight/` (backend package):**
- Purpose: Single Python package for the entire backend
- Contains: All domain modules as sub-packages, each with its own `router.py`, `service.py`, `schemas.py`
- Key files: `finsight/main.py`, `finsight/config.py`, `finsight/deps.py`

**`finsight/database/`:**
- Purpose: Database engine setup and session management
- Contains: `session.py` — SQLite engine, `get_session` generator dependency, `init_db()` table creation
- Key files: `finsight/database/session.py`

**`finsight/models/`:**
- Purpose: All SQLModel ORM table definitions in one place, imported across all service layers
- Contains: One file per DB table class, `enums.py` for shared enum types, `__init__.py` for consolidated re-exports
- Key files: `finsight/models/__init__.py`, `finsight/models/user.py`, `finsight/models/document.py`, `finsight/models/holding.py`

**`finsight/auth/`:**
- Purpose: User registration, login, JWT issuance
- Contains: `router.py` (`/auth/register`, `/auth/login`, `/auth/me`), `service.py` (bcrypt hash + verify), `security.py` (JWT encode/decode), `schemas.py`
- Key files: `finsight/auth/security.py`, `finsight/auth/service.py`

**`finsight/zerodha/`:**
- Purpose: Zerodha Kite Connect OAuth 2.0 integration and holdings sync
- Contains: `client.py` (raw KiteConnect API calls), `service.py` (token storage, holdings sync), `router.py` (OAuth redirect flow + sync endpoints), `schemas.py`
- Key files: `finsight/zerodha/client.py`, `finsight/zerodha/router.py`

**`finsight/portfolio/`:**
- Purpose: Portfolio analytics over holdings already synced from Zerodha
- Contains: `service.py` (joins Holdings + market prices), `router.py` (`/portfolio/holdings`, `/portfolio/insights`), `schemas.py`
- Key files: `finsight/portfolio/service.py`

**`finsight/ingestion/`:**
- Purpose: PDF document management — upload, parse, chunk, schedule
- Contains: `router.py` (upload, list, delete, process endpoints), `service.py` (orchestration), `parsers.py` (PDF text extraction + smart chunking), `file_manager.py` (disk I/O), `scheduler.py` (APScheduler daily jobs)
- Key files: `finsight/ingestion/parsers.py`, `finsight/ingestion/scheduler.py`

**`finsight/rag/`:**
- Purpose: Full hybrid retrieval-augmented generation pipeline
- Contains: `service.py` (embed, retrieve, rerank, generate), `vectorstore.py` (ChromaDB CRUD), `bm25_store.py` (in-memory BM25 index), `reranker.py` (cross-encoder reranking), `evaluation.py` (RAGAS scoring), `router.py`, `schemas.py`
- Key files: `finsight/rag/service.py`, `finsight/rag/vectorstore.py`, `finsight/rag/bm25_store.py`

**`finsight/sentiment/`:**
- Purpose: FinBERT sentence-level sentiment over full document text
- Contains: `service.py` (lazy-load FinBERT, run inference, aggregate, save), `router.py` (`/sentiment/{symbol}`, `/sentiment/recompute/{document_id}`), `schemas.py`
- Key files: `finsight/sentiment/service.py`

**`finsight/credibility/`:**
- Purpose: Claim extraction from documents + credibility score computation
- Contains: `service.py` (LLM-based claim extraction, score calculation), `fundamentals.py` (financial ratio helpers), `router.py`, `schemas.py`
- Key files: `finsight/credibility/service.py`

**`finsight/credisentiment/`:**
- Purpose: Combined feature — division-level FinBERT sentiment + "Walk the Talk" LLM comparison of management claims vs actuals
- Contains: `service.py` (two main functions: `analyze_division_sentiment`, `walk_the_talk`), `router.py`, `schemas.py`
- Key files: `finsight/credisentiment/service.py`

**`finsight/market/`:**
- Purpose: Live market data proxied from Zerodha Kite Connect
- Contains: `router.py` only (all logic inline — quotes, LTP, historical candles, instrument search + in-memory instrument cache)
- Key files: `finsight/market/router.py`

**`finsight/scraper/`:**
- Purpose: Web scraping of BSE, NSE, and Screener.in for company documents
- Contains: `bse_scraper.py`, `nse_scraper.py`, `screener_scraper.py`, `router.py`
- Key files: `finsight/scraper/bse_scraper.py`, `finsight/scraper/screener_scraper.py`

**`frontend/src/pages/`:**
- Purpose: Top-level route components, one per page
- Contains: `Dashboard.jsx`, `Portfolio.jsx`, `Market.jsx`, `Documents.jsx`, `Chat.jsx`, `Sentiment.jsx`, `Credibility.jsx`, `CredibilitySentiment.jsx`, `Login.jsx`, `Register.jsx`

**`frontend/src/api/`:**
- Purpose: Centralized HTTP call definitions; keeps pages free of fetch boilerplate
- Contains: `client.js` — single Axios instance + 9 named API objects: `authApi`, `zerodhaApi`, `portfolioApi`, `marketApi`, `ingestionApi`, `ragApi`, `sentimentApi`, `credibilityApi`, `scraperApi`, `credisentimentApi`

**`frontend/src/context/`:**
- Purpose: React Context providers for global state
- Contains: `AuthContext.jsx` — `AuthProvider` + `useAuth` hook; manages `user`, `loading`, `login`, `register`, `logout`

**`frontend/src/components/`:**
- Purpose: Shared UI building blocks
- Contains: `Sidebar.jsx` — navigation sidebar rendered inside `ProtectedLayout`

## Key File Locations

**Entry Points:**
- `finsight/main.py`: FastAPI application, all router registrations, lifespan hooks
- `frontend/src/main.jsx`: React DOM root mount
- `frontend/src/App.jsx`: All route definitions and `ProtectedLayout` guard

**Configuration:**
- `finsight/config.py`: All backend config — database URL, JWT secret, Zerodha keys, Ollama URL/models, ChromaDB path, chunk sizes
- `frontend/vite.config.js`: Dev server port (5173), `/api` proxy to `http://127.0.0.1:8000`
- `.env`: Runtime secrets (not committed) — loaded by `finsight/config.py` via `python-dotenv`
- `requirements.txt`: Python package pinning

**Core Logic:**
- `finsight/deps.py`: `get_current_user` — the single auth dependency injected everywhere
- `finsight/database/session.py`: `get_session`, `init_db` — database lifecycle
- `finsight/rag/service.py`: `answer_question`, `process_for_rag` — the full RAG pipeline
- `finsight/credisentiment/service.py`: `analyze_division_sentiment`, `walk_the_talk` — AI credibility analysis
- `frontend/src/api/client.js`: All API call functions consumed by pages

**Database Models:**
- `finsight/models/user.py`: `User`
- `finsight/models/portfolio.py`: `Portfolio`
- `finsight/models/holding.py`: `Holding`
- `finsight/models/document.py`: `Document`
- `finsight/models/document_chunk.py`: `DocumentChunk`
- `finsight/models/page_metadata.py`: `PageMetadata`
- `finsight/models/document_section.py`: `DocumentSection`
- `finsight/models/sentiment.py`: `SentimentScore`
- `finsight/models/credibility.py`: `ExtractedClaim`, `CredibilityScore`
- `finsight/models/division_sentiment.py`: `DivisionSentiment`, `WalkTheTalkResult`
- `finsight/models/zerodha_session.py`: `ZerodhaSession`
- `finsight/models/financial_metric.py`: `FinancialMetric`
- `finsight/models/enums.py`: `DocType`, `ClaimCategory`

## Naming Conventions

**Backend files:**
- One `router.py` per module — always named exactly `router.py`
- One `service.py` per module — always named exactly `service.py`
- One `schemas.py` per module — always named exactly `schemas.py`
- Model files named after the entity they define: `user.py`, `document.py`, `holding.py`

**Backend symbols:**
- Router variables: always `router = APIRouter()` — same name everywhere
- Service functions: snake_case verbs — `get_holdings_with_metrics`, `compute_sentiment_for_document`, `answer_question`
- Pydantic schemas: PascalCase — `PortfolioMetrics`, `RAGQueryRequest`, `HoldingMetric`
- SQLModel tables: PascalCase class, lowercase plural `__tablename__` — `class Holding`, `__tablename__ = "holdings"`

**Frontend files:**
- Page components: PascalCase `.jsx` — `Dashboard.jsx`, `CredibilitySentiment.jsx`
- API object names: camelCase noun + `Api` suffix — `portfolioApi`, `credisentimentApi`

## Where to Add New Code

**New backend feature (full domain):**
1. Create `finsight/{feature}/` with `__init__.py`, `router.py`, `service.py`, `schemas.py`
2. If it needs DB tables, add model files in `finsight/models/` and export from `finsight/models/__init__.py`
3. Import and register the router in `finsight/main.py`: `app.include_router(router, prefix="/{feature}", tags=["{feature}"])`
4. Add API calls to `frontend/src/api/client.js` as a new named export (e.g., `export const featureApi = { ... }`)
5. Add a page component in `frontend/src/pages/FeaturePage.jsx`
6. Register the route in `frontend/src/App.jsx` wrapped in `<ProtectedLayout>`

**New endpoint in existing module:**
- Add route handler to `finsight/{module}/router.py`
- Add business logic to `finsight/{module}/service.py`
- Add request/response schema to `finsight/{module}/schemas.py` if needed
- Add corresponding API function to the matching `*Api` object in `frontend/src/api/client.js`

**New DB table:**
- Create `finsight/models/{table_name}.py` with a `SQLModel` class, `table=True`, and explicit `__tablename__`
- Add the import and `__all__` entry to `finsight/models/__init__.py`
- The table will be auto-created by `init_db()` on next startup

**New React page:**
- Create `frontend/src/pages/PageName.jsx`
- Add `import PageName from './pages/PageName'` in `frontend/src/App.jsx`
- Add `<Route path="/path" element={<ProtectedLayout><PageName /></ProtectedLayout>} />`
- Add a nav link entry in `frontend/src/components/Sidebar.jsx`

**Shared utilities:**
- Backend: Place in the most relevant module's `service.py` or create a new `finsight/{module}/utils.py`; avoid cross-module imports except through the models layer
- Frontend: There is no shared `utils/` directory yet — add `frontend/src/utils/` for any reusable helpers

## Special Directories

**`chroma_db/`:**
- Purpose: ChromaDB persisted vector embeddings for all indexed document chunks
- Generated: Yes — created automatically by ChromaDB on first document indexing
- Committed: No (large binary data)

**`documents/`:**
- Purpose: Scraped/downloaded PDF files and their extracted `.txt` sidecar files
- Generated: Yes — populated by scraper and ingestion pipeline
- Committed: No

**`uploads/`:**
- Purpose: User-uploaded PDF files received via `POST /ingestion/documents/upload`
- Generated: Yes — created by the ingestion file manager
- Committed: No

**`venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-03-17*
