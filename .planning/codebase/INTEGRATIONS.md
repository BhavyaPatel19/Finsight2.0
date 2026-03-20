# External Integrations

**Analysis Date:** 2026-03-17

## Zerodha Kite Connect

- **Purpose:** Indian retail broker API — OAuth login, portfolio holdings sync, live market quotes, LTP, OHLC, historical candles, instrument list
- **Auth method:** OAuth 2.0 — user authenticates at `https://kite.zerodha.com/connect/login`, Zerodha redirects back with `request_token`, which is exchanged for `access_token` via SHA-256 checksum (`api_key + request_token + api_secret`)
- **API version:** Kite Connect v3 (header `X-Kite-Version: 3`)
- **Authorization header format:** `token {ZERODHA_API_KEY}:{access_token}`
- **Key endpoints consumed:**
  - `POST https://api.kite.trade/session/token` — request_token → access_token exchange
  - `GET https://api.kite.trade/portfolio/holdings` — user holdings
  - `GET https://api.kite.trade/quote` — full market quotes (up to 500 instruments)
  - `GET https://api.kite.trade/quote/ltp` — last traded price (up to 1000 instruments)
  - `GET https://api.kite.trade/quote/ohlc` — OHLC data
  - `GET https://api.kite.trade/instruments/historical/{token}/{interval}` — OHLCV candles
  - `GET https://api.kite.trade/instruments/NSE` — full instrument list CSV
  - `GET https://api.kite.trade/portfolio/positions` — short-term positions
  - `GET https://api.kite.trade/user/margins` — margin information
- **Key files:**
  - `finsight/zerodha/client.py` — all raw API calls via httpx
  - `finsight/zerodha/router.py` — OAuth flow endpoints (`/zerodha/connect`, `/zerodha/callback`, `/zerodha/link`)
  - `finsight/zerodha/service.py` — token storage and holdings sync logic
  - `finsight/market/router.py` — market data endpoints (quotes, LTP, history, instrument search)
  - `finsight/config.py` — `ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `ZERODHA_REDIRECT_URI`
- **Token storage:** Stored in `ZerodhaSession` SQLite table per user; read on every market data request
- **Notes:**
  - Instrument list is cached in-memory (`_instruments_cache`) for the process lifetime; populated on first call to `search_instruments` or `get_history`
  - OAuth redirect URL must match what is registered in the Zerodha developer portal
  - Dev environment uses ngrok to expose localhost for the redirect callback
  - `access_token` expires daily (Zerodha resets at 6:00 AM IST); users must re-authenticate each trading day

---

## Ollama (Local LLM Runtime)

- **Purpose:** Local large language model inference — RAG answer generation, credibility claim extraction, Walk-the-Talk claim comparison, RAGAS evaluation judge
- **Auth method:** None — unauthenticated local HTTP API
- **Endpoint:** `http://localhost:11434` (configurable via `OLLAMA_BASE_URL`)
- **API used:** `POST /api/generate` with `{"model": ..., "prompt": ..., "stream": false}`
- **Models in use:**
  - `deepseek-r1:14b` — primary reasoning model; outputs `<think>...</think>` traces parsed by `_parse_deepseek_thinking()`
  - `llama3.1:8b-instruct-q8_0` — fast fallback model
  - `llama3` — legacy default fallback
- **Key files:**
  - `finsight/rag/service.py` — `call_ollama()` function, model selection, thinking trace parsing
  - `finsight/credibility/service.py` — claim extraction prompt via `call_ollama()`
  - `finsight/credisentiment/service.py` — Walk-the-Talk LLM analysis
  - `finsight/rag/evaluation.py` — RAGAS evaluation using Ollama as judge via LangchainLLMWrapper
  - `finsight/config.py` — `OLLAMA_BASE_URL`, `OLLAMA_MODEL_PRIMARY`, `OLLAMA_MODEL_FAST`, `OLLAMA_MODEL`
- **Notes:**
  - `httpx.Client(timeout=120.0)` — 2-minute timeout per LLM call
  - DeepSeek-R1 thinking traces are parsed and returned separately as `thinking` field in RAG response
  - RAGAS evaluation additionally wraps Ollama via `langchain_community.llms.Ollama` and `langchain_community.embeddings.OllamaEmbeddings`

---

## Screener.in (Web Scraper)

- **Purpose:** Financial document discovery for Indian-listed companies — annual reports, concall transcripts, credit rating reports, BSE/NSE announcements
- **Auth method:** None — public website scraped without authentication; session cookies obtained from homepage visit
- **Base URL:** `https://www.screener.in`
- **API used:**
  - `GET https://www.screener.in/api/company/search/?q={query}` — JSON company search
  - `GET https://www.screener.in/company/{symbol}/consolidated/` — HTML page scraping for document links
- **Key files:**
  - `finsight/scraper/screener_scraper.py` — `search_company()`, `get_company_documents()`, `download_document()`
  - `finsight/scraper/router.py` — `/scraper/search-company`, `/scraper/company-documents`, `/scraper/download-selected`
- **Document sources discovered:** BSE India (`bseindia.com`), NSE India (`nseindia.com`), company IR pages, ICRA/CRISIL/CARE/India Ratings credit agency URLs
- **Anti-bot measures:**
  - Randomized User-Agent rotation from a pool of 4 browser UA strings
  - Rate limiting: 0.8–1.5 second delay between requests
  - Session cookie initialization via homepage GET before scraping
  - `Referer: https://www.screener.in/` header on download requests
- **Download behavior:** Background thread per job (tracked in `_jobs` dict); deduplicates by `source_url`; saves to `uploads/` directory
- **Notes:**
  - HTML parsing uses `beautifulsoup4` with `html.parser`
  - Two-strategy scraping: primary looks for `<section id="documents">` with `<h3>` headings; fallback scans full page
  - Downloaded documents are registered as `Document` rows in SQLite with `status="pending"` for subsequent RAG indexing

---

## HuggingFace Model Hub (Model Download)

- **Purpose:** Source for pre-trained ML models downloaded on first use
- **Auth method:** None — public models, no API key required
- **Models downloaded:**
  - `ProsusAI/finbert` — FinBERT for financial sentiment classification (~440MB)
  - `BAAI/bge-base-en-v1.5` — BGE bi-encoder for dense retrieval embeddings (~275MB)
  - `BAAI/bge-reranker-base` — BGE cross-encoder for reranking (~275MB)
- **Key files:**
  - `finsight/sentiment/service.py` — FinBERT via `transformers.AutoTokenizer` + `AutoModelForSequenceClassification`
  - `finsight/rag/service.py` — BGE embedder via `sentence_transformers.SentenceTransformer`
  - `finsight/rag/reranker.py` — BGE reranker via `sentence_transformers.CrossEncoder`
- **Notes:**
  - All models are lazy-loaded (singleton pattern) — first request triggers download
  - Models are cached by HuggingFace's default cache directory (`~/.cache/huggingface/`)
  - No internet access needed after initial model download

---

## RAGAS (RAG Evaluation Framework)

- **Purpose:** Automated evaluation of RAG pipeline quality — faithfulness, answer relevancy, context precision
- **Auth method:** None — fully local, uses Ollama as judge
- **Key files:**
  - `finsight/rag/evaluation.py` — `run_ragas_evaluation()`
  - `finsight/rag/router.py` — `POST /rag/evaluate` endpoint
- **Dependencies:** `ragas>=0.1.21`, `langchain-community>=0.2.0`, `datasets` (HuggingFace)
- **Notes:**
  - Uses `LangchainLLMWrapper(Ollama(...))` as judge LLM — no external API calls
  - `datasets.Dataset.from_dict()` used to construct evaluation dataset
  - Returns per-question breakdown in addition to aggregate scores
  - Optional `ground_truths` improves recall-based metrics

---

## Data Storage

**Primary Database:**
- SQLite at `finsight.db` (project root)
- Connection: `DATABASE_URL` env var (default: `sqlite:///./finsight.db`)
- Session management: `finsight/database/session.py`

**Vector Store:**
- ChromaDB PersistentClient at `chroma_db/` directory (project root)
- Collection: `finsight_docs` with cosine HNSW index
- Path: `CHROMA_PERSIST_DIR` env var (default: `{project_root}/chroma_db`)

**File Storage:**
- PDFs uploaded by users: `documents/` directory (project root)
- PDFs downloaded by scraper: `uploads/` directory (project root)
- Extracted text saved as `.txt` alongside source PDF (same directory, same base name)

---

## Environment Variables

**Required for Zerodha integration:**
- `ZERODHA_API_KEY` — Kite Connect API key from developer portal
- `ZERODHA_API_SECRET` — Kite Connect API secret
- `ZERODHA_REDIRECT_URI` — OAuth callback URL (must match Zerodha portal; use ngrok URL in dev)

**Required for auth:**
- `SECRET_KEY` — JWT signing key (default is insecure placeholder; must change in production)

**Optional (have defaults):**
- `DATABASE_URL` — SQLite connection string (default: `sqlite:///finsight.db`)
- `OLLAMA_BASE_URL` — Ollama server URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL_PRIMARY` — Primary LLM (default: `deepseek-r1:14b`)
- `OLLAMA_MODEL_FAST` — Fast LLM (default: `llama3.1:8b-instruct-q8_0`)
- `OLLAMA_MODEL` — Legacy LLM fallback (default: `llama3`)
- `EMBEDDING_MODEL` — HuggingFace model ID (default: `BAAI/bge-base-en-v1.5`)
- `CHROMA_PERSIST_DIR` — ChromaDB storage path (default: `{project_root}/chroma_db`)

---

## Webhooks & Callbacks

**Incoming:**
- `GET /zerodha/callback?request_token=...&status=success` — Zerodha OAuth redirect after user login
  - Reads `zerodha_link_uid` cookie to associate token with user
  - Cookie set by `/zerodha/connect` or `/zerodha/connect-redirect`

**Outgoing:**
- None — all external calls are synchronous request-response via httpx

---

*Integration audit: 2026-03-17*
