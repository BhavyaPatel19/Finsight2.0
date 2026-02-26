# FinSight

AI-powered financial intelligence: Zerodha integration, document ingestion, RAG Q&A, sentiment, and credibility scoring.

## Setup

```bash
cd "C:\Users\This PC\Desktop\8thsem"
pip install -r requirements.txt
```

Optional: set env vars (or use defaults):

- `SECRET_KEY` – JWT signing key (default: change-me-in-production)
- `OLLAMA_BASE_URL` – Ollama API (default: http://localhost:11434)
- `OLLAMA_MODEL` – e.g. llama3
- `ZERODHA_API_KEY` / `ZERODHA_API_SECRET` – for Zerodha OAuth  
- `ZERODHA_REDIRECT_URI` – must match the Redirect URL you set in the Zerodha app (e.g. `https://yourdomain.com/zerodha/callback`)

## Zerodha API setup

1. **Create an app** at [Zerodha Developers](https://developers.kite.trade/) (or the “Create a new app” page you have open).
2. **Fill the form:**
   - **Type:** Keep **Connect** (for live quotes and holdings).
   - **App name \***: e.g. `FinSight`.
   - **Zerodha Client ID \***: Your Zerodha client ID (e.g. AB1234).
   - **Redirect URL \***: Must be an **HTTPS** URL where Zerodha will send the user after login.  
     - **Local dev:** Use a tunnel (e.g. [ngrok](https://ngrok.com/)): run `ngrok http 8000`, then set Redirect URL to `https://YOUR-NGROK-URL/zerodha/callback`.  
     - **Deployed:** Use your app URL, e.g. `https://yourdomain.com/zerodha/callback`.
   - **Description \***: e.g. `FinSight portfolio and insights`.
3. Click **Create**. Copy the **API key** and **API secret**.
4. **Set environment variables:**
   ```bash
   set ZERODHA_API_KEY=your_api_key
   set ZERODHA_API_SECRET=your_api_secret
   set ZERODHA_REDIRECT_URI=https://YOUR-NGROK-OR-DOMAIN/zerodha/callback
   ```
   (Use the **exact** Redirect URL you used in the form.)
5. **Link Zerodha in FinSight:**
   - **Option A (browser):** Log in to FinSight, then open `GET /zerodha/connect`. You’ll be sent to Zerodha login; after login you’re redirected to `/zerodha/callback` and the token is stored.
   - **Option B (API):** After Zerodha redirects to your callback, if no cookie was set you’ll see the `request_token` on the page. Then:
     ```http
     POST /zerodha/link
     Authorization: Bearer YOUR_JWT
     Content-Type: application/json
     {"request_token": "PASTE_REQUEST_TOKEN_HERE"}
     ```
6. **Sync holdings:** `POST /zerodha/sync` (with Bearer token) fetches holdings from Zerodha and saves them. Then `GET /zerodha/holdings` or `GET /portfolio/holdings` returns your portfolio.

## Run

```bash
python -m uvicorn finsight.main:app --reload
```

- API: http://127.0.0.1:8000  
- Docs: http://127.0.0.1:8000/docs  

## API Overview

| Area | Endpoints |
|------|-----------|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| **Zerodha** | `GET /zerodha/login-url`, `GET /zerodha/connect`, `GET /zerodha/callback`, `POST /zerodha/link`, `POST /zerodha/sync`, `GET /zerodha/holdings` |
| **Portfolio** | `GET /portfolio/holdings`, `GET /portfolio/insights` |
| **Ingestion** | `GET /ingestion/documents`, `POST /ingestion/documents/upload`, `POST /ingestion/run` |
| **RAG** | `POST /rag/query` (question, optional symbol/period, top_k) |
| **Sentiment** | `GET /sentiment/{symbol}`, `POST /sentiment/recompute/{document_id}` |
| **Credibility** | `GET /credibility/{symbol}`, `POST /credibility/recompute/{symbol}/{period}`, `POST /credibility/extract-claims/{document_id}` |

Protected routes require header: `Authorization: Bearer <token>` (from `/auth/login`).

## Data flow

1. **Documents**: Upload PDF via `POST /ingestion/documents/upload` (symbol, doc_type, fiscal_quarter, fiscal_year). Text is extracted, chunked, and indexed in ChromaDB.
2. **RAG**: `POST /rag/query` retrieves chunks from Chroma, sends context + question to Ollama (Llama 3), returns answer and sources.
3. **Sentiment**: Run `POST /sentiment/recompute/{document_id}` to score a document with FinBERT (needs `transformers` + `torch`).
4. **Credibility**: `POST /credibility/extract-claims/{document_id}` extracts claims via LLM; then `POST /credibility/recompute/{symbol}/{period}` compares to `FinancialMetric` and stores score 0–100.

## Project layout

```
finsight/
  main.py           # App entry, routers, lifespan
  config.py
  deps.py           # get_current_user, get_session
  auth/             # JWT, register, login
  zerodha/          # OAuth stub, holdings
  portfolio/        # Holdings + metrics, insights
  ingestion/        # PDF parsers, scheduler, upload
  rag/              # ChromaDB, embeddings, Ollama query
  sentiment/        # FinBERT scoring
  credibility/      # Claims extraction, score vs actuals
  models/           # SQLModel tables
  database/         # Session, init_db
```

SQLite DB: `finsight.db` in project root. ChromaDB: `chroma_db/`. Uploaded PDFs: `documents/`.
