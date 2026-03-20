# Technical Concerns

**Analysis Date:** 2026-03-17

---

## Security

### Critical

**Wildcard CORS with credentials enabled:**
- Config: `finsight/main.py` lines 33–39
- `allow_origins=["*"]` is combined with `allow_credentials=True`. This is a browser-rejected configuration in practice and is incorrect — browsers refuse credentialed requests to wildcard origins. More importantly, if the origin is ever switched to a real list, the current mental model is that credentials are safe, which is misleading. In production this must be scoped to the actual frontend domain.
- Fix approach: Set `allow_origins=["https://yourdomain.com"]` and remove the wildcard.

**JWT stored in `localStorage` — XSS vulnerable:**
- Files: `frontend/src/context/AuthContext.jsx`, `frontend/src/api/client.js`
- JWT tokens (`fs_token`, `fs_user`) are read and written directly from `localStorage`. Any XSS vulnerability in a dependency or inline script can exfiltrate the token silently. There is no CSRF protection either since the token is sent as a Bearer header.
- Fix approach: Move token to an `HttpOnly`, `SameSite=Strict` cookie managed by the backend. Remove `localStorage` token storage entirely.

**Default fallback secret key hardcoded in source:**
- File: `finsight/config.py` line 17
- `SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")` — if the `.env` file is missing or the env var is not set, the application silently uses a well-known fallback. Any JWT signed with this key is forgeable by anyone who reads the source code.
- Fix approach: Remove the fallback entirely. Raise a startup error if `SECRET_KEY` is absent or equals the placeholder.

**JWT passed in query string for Zerodha OAuth flow:**
- File: `finsight/zerodha/router.py` lines 50–52
- The `/zerodha/connect-redirect?token=<JWT>` endpoint puts a full JWT in the URL query parameter. Query strings appear in server access logs, browser history, and HTTP Referer headers. This leaks a valid bearer token.
- Fix approach: Use a short-lived one-time state parameter or a separate session-cookie mechanism instead of passing the full JWT in the URL.

**No file type or content validation on PDF upload:**
- File: `finsight/ingestion/router.py` lines 112–130
- Only the filename extension `.pdf` is checked (`file.filename.lower().endswith(".pdf")`). There is no magic byte / MIME-type check of the actual file content. An attacker can upload any file with a `.pdf` extension.
- Fix approach: Read the first 4 bytes and verify the PDF magic number (`%PDF`). Also enforce a maximum upload size.

**No upload size limit:**
- File: `finsight/ingestion/router.py` and `finsight/credisentiment/router.py`
- `await file.read()` reads the entire file into memory with no size cap. A large upload can exhaust server memory.
- Fix approach: Check `file.size` before reading, or stream to disk with a byte limit.

### High

**Zerodha access token stored plaintext in SQLite:**
- File: `finsight/models/zerodha_session.py`
- `access_token: str` is stored as a plain string in the `zerodha_sessions` table in `finsight.db`. The token grants full read (and potentially trade) access to a user's brokerage account. If the database file is exfiltrated, all tokens are immediately usable.
- Fix approach: Encrypt the token at rest using a key derived from `SECRET_KEY` (e.g., Fernet from `cryptography`).

**No rate limiting on auth endpoints:**
- File: `finsight/auth/router.py`
- `/auth/login` and `/auth/register` have no rate limiting. Brute-force and credential-stuffing attacks are unrestricted.
- Fix approach: Add `slowapi` or similar rate-limiting middleware targeting `/auth/login` (e.g., 5 requests per minute per IP).

**No password complexity requirements:**
- File: `finsight/auth/schemas.py` lines 4–7
- `UserCreate.password` is typed as plain `str` with no minimum length, character requirements, or Pydantic validators. A one-character password is accepted.
- Fix approach: Add `@field_validator("password")` enforcing minimum 8 characters.

**Zerodha request_token exposed in HTML on callback fallback:**
- File: `finsight/zerodha/router.py` lines 152–158
- When the link cookie is absent, the `/zerodha/callback` endpoint renders the raw `request_token` in an HTML page. While this token is single-use and short-lived, rendering it in the response body is a bad pattern and could cause confusion or misuse.
- Fix approach: Return a generic success/failure page without the token; require the user to restart the flow.

### Medium

**CORS open during development — not gated by environment:**
- File: `finsight/main.py` lines 34–35
- The wildcard origin is not behind any `DEBUG` or environment flag. Deploying the current code to production exposes the API to cross-origin requests from any domain.
- Fix approach: Read allowed origins from an env var (`ALLOWED_ORIGINS`); default to `[]` (deny all) when not set, forcing explicit configuration.

**No HTTPS enforcement or HSTS headers:**
- Files: `finsight/main.py` (no security middleware added)
- There is no `HTTPSRedirectMiddleware`, no `Strict-Transport-Security` header, and no `X-Content-Type-Options` or `X-Frame-Options` headers. The API can serve sensitive financial data over plain HTTP.
- Fix approach: Add `from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware` and security header middleware in production.

---

## Performance

**FinBERT is reloaded on every sentiment recompute call:**
- File: `finsight/sentiment/service.py` lines 6–16
- `get_finbert_model()` calls `AutoTokenizer.from_pretrained()` and `AutoModelForSequenceClassification.from_pretrained()` every time it is invoked. There is no module-level singleton. Each call to `compute_sentiment_for_document` pays the full ~500 MB model load cost.
- Impact: Sentiment recompute takes minutes per call; concurrent calls will attempt parallel loads.
- Fix approach: Move the model and tokenizer to module-level singletons (same pattern used in `finsight/rag/service.py` with `_embedding_model`).

**BM25 index loads all DocumentChunk rows into RAM on every invalidation:**
- File: `finsight/rag/bm25_store.py` lines 15–53
- `build_bm25_index()` fetches every `DocumentChunk` row from SQLite and tokenizes all of them synchronously on the request thread. As the document library grows this blocks the event loop and consumes significant memory.
- Impact: First RAG query after any new document ingestion causes a full BM25 rebuild on the FastAPI worker thread, stalling concurrent requests.
- Fix approach: Rebuild the index in a background thread/process; consider persisting the BM25 index to disk.

**Cross-encoder reranker (275 MB) loaded on first RAG query:**
- File: `finsight/rag/reranker.py` lines 9–13
- `CrossEncoder("BAAI/bge-reranker-base")` is loaded lazily on the first request. This causes a 5–15 second hang on the first RAG query after server start.
- Fix approach: Warm up the model at startup in the lifespan handler (`finsight/main.py`), or document the cold-start delay clearly.

**FinBERT runs sentence-by-sentence in a Python loop (no batching):**
- Files: `finsight/sentiment/service.py` lines 53–62, `finsight/credisentiment/service.py` lines 126–136
- Each sentence is tokenized and inference-run individually inside a `for` loop with `torch.no_grad()`. Batching sentences (e.g., 32 at a time) would be ~10–20× faster on CPU and dramatically faster on GPU.
- Impact: Long documents (500 sentences) take several minutes to analyze.
- Fix approach: Use `tokenizer(batch, padding=True, truncation=True, return_tensors="pt")` with batches.

**Instruments cache is an in-process list with O(n) linear search:**
- File: `finsight/market/router.py` lines 45–66, 186–213
- `_instruments_cache` holds all NSE instruments (~2,000+ entries) and is searched with a linear scan for every `/market/history/{symbol}` and `/market/instruments/search` request.
- Fix approach: Index the cache by symbol for O(1) lookup.

**Synchronous HTTP calls inside FastAPI endpoints:**
- Files: `finsight/rag/service.py` line 287 (`httpx.Client`), `finsight/scraper/bse_scraper.py`, `finsight/scraper/screener_scraper.py`
- All external HTTP calls use synchronous `httpx.Client` inside async FastAPI endpoints. This blocks the event loop for the duration of each network call, including scraper waits of 1–2.5 seconds.
- Fix approach: Switch to `httpx.AsyncClient` and `await` the calls, or run them via `asyncio.to_thread()`.

**RAG query blocks the request thread for up to 120 seconds:**
- File: `finsight/rag/service.py` line 287
- `httpx.Client(timeout=120.0)` is used synchronously for the Ollama LLM call. During this 0–120 second window, the FastAPI worker is fully blocked.
- Fix approach: Use `httpx.AsyncClient` or run the LLM call in a thread pool via `asyncio.to_thread()`.

---

## Technical Debt

**Scheduled jobs are stub placeholders:**
- File: `finsight/ingestion/scheduler.py` lines 15–21
- `scheduled_fetch_documents()` and `scheduled_portfolio_snapshot()` both contain only `pass`. APScheduler runs them every 24 hours but they do nothing. This gives the false impression that automatic document fetching and portfolio snapshots are implemented.
- Impact: Users expect auto-refresh; nothing happens silently.

**Duplicate scrip codes and company entries in the static BSE company database:**
- File: `finsight/scraper/bse_scraper.py` lines 118–191
- Multiple entries share the same `scrip_code`: `532978` (Bajaj Finserv — appears 3 times), `532454` (Bharti Airtel — appears twice), `500483` (two different companies: Tata Chemicals and Tata Metaliks).
- Impact: `search_company()` deduplication by `scrip_code` will arbitrarily return whichever entry appears last; wrong `company_name` may be shown.

**Legacy ingestion pathway coexists with new on-demand RAG pathway:**
- Files: `finsight/rag/service.py` lines 99–122 (`index_chunks_for_document`), `finsight/ingestion/file_manager.py`
- There are two separate code paths for ingesting documents: the old `index_chunks_for_document` (stores page_number=0, section="") and the new `process_for_rag` (page-aware chunking). Both exist in production. Old documents processed through the legacy path will have missing page/section metadata.

**`open()` used instead of `Path.read_text()` throughout services:**
- Files: `finsight/credibility/service.py` line 13, `finsight/credisentiment/service.py` lines 287–290, `finsight/sentiment/service.py` line 24
- File handles are opened with bare `open(doc.text_path, ...)` without a context manager (`with` block). If an exception occurs before `.close()`, file descriptors leak.
- Fix approach: Use `with open(...) as f:` or `Path(doc.text_path).read_text(encoding="utf-8")`.

**Market expansion claim maps to `revenue_growth` metric — same field used twice:**
- File: `finsight/credibility/service.py` lines 80–88
- `market_expansion` category uses `metric.revenue_growth` as its actual value, which is the same field as `revenue_growth`. This conflates two distinct claim categories and makes the credibility scoring for `market_expansion` meaningless.

**`_SYMBOL_MAP` mutated at runtime in a global dict without thread safety:**
- File: `finsight/scraper/bse_scraper.py` lines 416–417
- `_SYMBOL_MAP[nse_symbol.upper()] = str(scrip)` modifies a module-level dict from request handlers. Under concurrent requests this is a data race.

---

## Scalability

**SQLite as the primary database:**
- File: `finsight/config.py` line 14
- SQLite has a single writer lock. Under concurrent RAG indexing, sentiment analysis, and portfolio sync, write contention will cause `OperationalError: database is locked` errors. The default `DATABASE_URL` falls back to `finsight.db` (SQLite).
- Scaling path: Migrate to PostgreSQL. `DATABASE_URL` env var already supports this, but no migration tooling (Alembic) is set up.

**No database migration tooling:**
- Files: `finsight/database/session.py`, no `alembic.ini` present
- Schema changes use `SQLModel.metadata.create_all()` (DDL-on-start). There is no Alembic or equivalent migration history. Schema changes require manual SQLite file management or data loss.
- Fix approach: Initialize Alembic and generate an initial migration from the current models.

**ChromaDB single collection for all users and all documents:**
- File: `finsight/rag/vectorstore.py` line 30
- All embeddings share a single ChromaDB collection `finsight_docs`. Document-level filtering is done via `where={"document_id": ...}` at query time. As the collection grows, filtering becomes slower.
- Scaling path: Partition collections by user or by symbol at the ChromaDB level.

**In-process BM25 and instrument caches are not shared across workers:**
- Files: `finsight/rag/bm25_store.py`, `finsight/market/router.py`
- `_bm25_index`, `_bm25_corpus`, and `_instruments_cache` are module-level globals. If the app is run with multiple uvicorn workers (`--workers N`), each worker maintains its own separate, unsynchronized copy. A document indexed in worker 1 will not appear in worker 2's BM25 index until it is rebuilt.
- Scaling path: Move shared state to Redis or a shared memory solution; or enforce single-worker deployment.

---

## Operational

**Zerodha OAuth redirect hardcoded to ngrok URL:**
- File: `finsight/zerodha/router.py` lines 43–48, config comment in `finsight/config.py` line 24
- `ZERODHA_REDIRECT_URI` must match the redirect URL registered in the Zerodha developer portal. In development this is an ngrok URL. The `connect_url` endpoint derives the base URL by splitting on `/zerodha/` — if the URI format changes, the parsing breaks silently.
- Fix approach: Set `ZERODHA_REDIRECT_URI` explicitly per environment; do not derive it by string-splitting.

**No startup validation of required environment variables:**
- File: `finsight/config.py`
- Missing `ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `ZERODHA_REDIRECT_URI` are silently set to empty strings. The app starts and appears healthy but Zerodha features fail at runtime with opaque 503 errors.
- Fix approach: Add a startup check that logs clear warnings or raises `RuntimeError` for missing required vars.

**APScheduler shutdown called with `wait=False`:**
- File: `finsight/main.py` lines 26–28
- `s.shutdown(wait=False)` on app shutdown does not wait for running jobs to complete. While the current scheduled jobs are stubs, when they are implemented, this can cause data corruption on graceful stop.

**No structured logging or log level configuration:**
- Files: `finsight/market/router.py` (uses `logging.getLogger`), most other modules use no logging at all
- The majority of modules use bare `except Exception: pass` or `except Exception: return []` with no logging. Errors are silently swallowed, making production debugging extremely difficult.
- Fix approach: Configure a root logger in `finsight/main.py`; replace silent exception handling with `logger.exception()`.

**Screener.in and BSE scraping is legally and operationally fragile:**
- Files: `finsight/scraper/screener_scraper.py`, `finsight/scraper/bse_scraper.py`
- The scrapers use rotating user-agents to evade bot detection on third-party websites. This violates the terms of service of both BSE India and Screener.in. IP blocks or legal notices are possible. The BSE API URL (`api.bseindia.com`) is an internal API, not a documented public API.
- Fix approach: Use official BSE/NSE data vendor APIs (e.g., Upstox, AngelOne, or BSE's official data licensing).

**`finsight.db` SQLite file and `chroma_db/` directory not gitignored properly:**
- These files contain user data, hashed passwords, Zerodha tokens, and proprietary document embeddings. If committed to a public repository they expose sensitive data.
- Fix approach: Confirm `.gitignore` excludes `*.db`, `chroma_db/`, and `documents/`.

---

## Priority Recommendations

1. **Remove the hardcoded JWT secret fallback** (`finsight/config.py` line 17) — fail loudly at startup if `SECRET_KEY` is not set in environment. This is the highest-impact single-line fix.

2. **Move JWT tokens from `localStorage` to `HttpOnly` cookies** (`frontend/src/context/AuthContext.jsx`, `frontend/src/api/client.js`) — eliminates the XSS token-theft vector across the entire application.

3. **Restrict CORS to explicit origin list** (`finsight/main.py`) — replace `allow_origins=["*"]` with env-var-configured origins before any public deployment.

4. **Fix FinBERT singleton loading** (`finsight/sentiment/service.py`) — add module-level `_tokenizer`/`_model` globals matching the pattern in `finsight/rag/service.py` to avoid repeated ~500MB model loads.

5. **Add rate limiting to `/auth/login`** — install `slowapi` and apply a per-IP limit to prevent brute-force attacks.

6. **Encrypt the Zerodha access token at rest** (`finsight/models/zerodha_session.py`) — store encrypted ciphertext, decrypt on retrieval, to protect brokerage access if the SQLite file is exfiltrated.

7. **Initialize Alembic** for schema migration management before any production schema change causes data loss.

8. **Fix open file handles** in `finsight/credibility/service.py`, `finsight/credisentiment/service.py`, and `finsight/sentiment/service.py` — wrap all `open()` calls in `with` blocks.

9. **Implement the scheduled job stubs** (`finsight/ingestion/scheduler.py`) or remove the scheduler entirely to avoid misleading no-op background tasks.

10. **Switch external HTTP calls to async** (`finsight/rag/service.py`, scrapers) — use `httpx.AsyncClient` to prevent blocking the FastAPI event loop during Ollama and scraper network calls.

---

*Concerns audit: 2026-03-17*
