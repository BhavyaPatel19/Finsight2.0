# Technology Stack

**Analysis Date:** 2026-03-17

## Backend

**Language/Runtime:**
- Python 3.11+ (uses union type syntax `str | None`, `list[int] | None` — requires 3.10+)

**Framework:**
- FastAPI — async HTTP API with lifespan context manager for startup/shutdown
- Uvicorn (with `[standard]` extras) — ASGI server
- Entry point: `finsight/main.py`

**Database:**
- SQLite — single-file database at `finsight.db` in project root
- Connection URL: `sqlite:///finsight.db` (configurable via `DATABASE_URL` env var)

**ORM:**
- SQLModel — thin wrapper over SQLAlchemy + Pydantic for unified models and schemas
- SQLAlchemy — underlying engine, session management in `finsight/database/session.py`

**Key Backend Libraries:**
- `python-jose[cryptography]` — JWT encoding/decoding (HS256 algorithm)
- `passlib[bcrypt]` — password hashing via bcrypt
- `python-multipart` — multipart form handling for file uploads
- `email-validator` — email field validation in Pydantic schemas
- `apscheduler` — background job scheduler (BackgroundScheduler with IntervalTrigger)
- `httpx` — async-compatible HTTP client for all external API calls
- `python-dotenv` — `.env` file loading via `load_dotenv()`
- `beautifulsoup4` (bs4) — HTML parsing in the Screener.in scraper
- `pymupdf` (fitz) — primary PDF text extraction
- `pdfplumber` — fallback PDF text extraction when PyMuPDF yields no text

## Frontend

**Framework:**
- React 18.3.1 with React DOM 18.3.1
- React Router DOM 6.23.1 — client-side routing with `ProtectedLayout`

**Build Tool:**
- Vite 5.3.1 with `@vitejs/plugin-react` 4.3.1
- Dev server on port 5173
- API proxy: `/api` → `http://127.0.0.1:8000` (strips `/api` prefix)

**Key Frontend Libraries:**
- `axios` 1.7.2 — HTTP client; interceptor injects `Authorization: Bearer <token>` from `localStorage`
- `recharts` 2.12.7 — charts (pie chart for portfolio, candlestick for market)
- `lucide-react` 0.395.0 — icon set

**TypeScript Support:**
- `@types/react` 18.3.3 and `@types/react-dom` 18.3.0 installed as devDependencies
- No `tsconfig.json` present — project uses plain `.jsx` files, not TypeScript

## AI/ML

**LLM (Inference):**
- Ollama — local LLM runtime at `http://localhost:11434`
- Primary model: `deepseek-r1:14b` (configurable via `OLLAMA_MODEL_PRIMARY`)
- Fast model: `llama3.1:8b-instruct-q8_0` (configurable via `OLLAMA_MODEL_FAST`)
- Legacy fallback: `llama3` (configurable via `OLLAMA_MODEL`)
- Called via `httpx` POST to `/api/generate` in `finsight/rag/service.py`

**Embeddings:**
- `sentence-transformers` library
- Model: `BAAI/bge-base-en-v1.5` (768-dim, cosine similarity)
- Query prefix: `"Represent this sentence for searching relevant passages: {text}"`
- Document embedding: no prefix (BGE convention)
- Lazy-loaded singleton in `finsight/rag/service.py`

**Reranker:**
- `sentence-transformers` CrossEncoder
- Model: `BAAI/bge-reranker-base` (~275MB)
- Lazy-loaded singleton in `finsight/rag/reranker.py`
- Applied after Reciprocal Rank Fusion, returns top-k candidates

**Vector Store:**
- `chromadb` — `PersistentClient` with HNSW cosine space
- Collection: `finsight_docs` in `chroma_db/` directory
- Metadata tracks `embedding_model` to auto-clear on model change
- Wrapped in `finsight/rag/vectorstore.py`

**Sentiment Analysis:**
- `transformers` + `torch` — HuggingFace Transformers pipeline
- Model: `ProsusAI/finbert` — financial domain BERT for sequence classification
- Labels: positive, negative, neutral (softmax probabilities)
- Lazy-loaded in `finsight/sentiment/service.py`
- Also used in `finsight/credisentiment/service.py` for division-level analysis

**BM25 Keyword Retrieval:**
- `rank-bm25` >= 0.2.2 — BM25Okapi implementation
- In-memory index rebuilt from `DocumentChunk` table on first query
- Invalidated on new document indexing
- Implemented in `finsight/rag/bm25_store.py`

**RAG Evaluation:**
- `ragas` >= 0.1.21 — RAG quality metrics (faithfulness, answer_relevancy, context_precision)
- `langchain-community` >= 0.2.0 — LangchainLLMWrapper and OllamaEmbeddings for RAGAS judge
- Uses `datasets` (HuggingFace) for Dataset construction
- Implemented in `finsight/rag/evaluation.py`

## Infrastructure

**Auth:**
- Custom JWT auth: HS256 tokens, 24-hour expiry
- Tokens stored in `localStorage` as `fs_token` and `fs_user`
- Backend: `python-jose` + `passlib[bcrypt]` in `finsight/auth/security.py`
- Bearer token injected by Axios interceptor on all frontend API calls

**Scheduler:**
- APScheduler `BackgroundScheduler` — daily interval jobs for document fetching and portfolio snapshots
- Started in FastAPI lifespan (`finsight/ingestion/scheduler.py`)
- Current scheduled functions are stubs — placeholder implementations

**CORS:**
- `CORSMiddleware` with `allow_origins=["*"]` — open for all origins
- Applied globally in `finsight/main.py`

**Environment Configuration:**
- `.env` file at project root loaded via `python-dotenv`
- Config module: `finsight/config.py`

**Development Tunneling:**
- ngrok used for Zerodha OAuth redirect URL during local development
- `ZERODHA_REDIRECT_URI` must match the ngrok URL configured in the Zerodha developer portal

## Run Commands

```bash
# Backend (from 8thsem/ with venv active)
uvicorn finsight.main:app --reload

# Frontend (from frontend/)
npm run dev

# Ollama (local LLM runtime)
ollama serve
ollama pull deepseek-r1:14b
ollama pull llama3.1:8b-instruct-q8_0
ollama pull llama3
```

---

*Stack analysis: 2026-03-17*
