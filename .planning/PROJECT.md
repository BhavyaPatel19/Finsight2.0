# FinSight

## What This Is

AI-powered financial intelligence platform for Indian retail investors. Connects to Zerodha brokerage for portfolio tracking, provides live market data, and uses NLP/LLM models to analyze company financial documents — extracting sentiment (FinBERT), comparing management claims against outcomes (Walking the Talk via DeepSeek), and answering questions over documents (RAG with Ollama).

## Core Value

Investors can verify whether company management delivers on their promises by comparing con-call claims against actual earnings, powered by locally-run AI models with no data leaving the machine.

## Requirements

### Validated

- ✓ User authentication (JWT, email/password) — existing
- ✓ Zerodha OAuth integration for portfolio sync — existing
- ✓ Portfolio overview with holdings, P&L, allocation — existing
- ✓ Live market quotes and watchlist via Kite Connect — existing
- ✓ Candlestick charting for individual instruments — existing
- ✓ PDF document upload and management — existing
- ✓ PDF text extraction (PyMuPDF + pdfplumber fallback) — existing
- ✓ RAG pipeline: chunking, embedding, ChromaDB vector store, BM25 hybrid retrieval, cross-encoder reranking — existing
- ✓ RAG Q&A chat with Ollama (Llama 3) — existing
- ✓ FinBERT sentiment analysis on financial documents — existing
- ✓ Division-level FinBERT sentiment breakdown — existing
- ✓ Walking the Talk LLM credibility comparison — existing (needs rework)
- ✓ BSE filing scraper for document retrieval — existing

### Active

- [ ] Remove standalone Credibility and Sentiment tabs from navigation
- [ ] Consolidate into CrediSentiment tab with two sub-tabs: "FinBERT Sentiment" and "Walking the Talk"
- [ ] Separate document processing pipelines for RAG vs CrediSentiment (different chunking/embedding parameters)
- [ ] Document processing controls on Documents tab: "Process for RAG" / "Process for CrediSentiment" buttons with visual status indicators
- [ ] Only show RAG-processed documents in RAG tab document picker
- [ ] Only show CrediSentiment-processed documents in Walking the Talk document picker
- [ ] FinBERT-processed documents use RAG chunking; RAG-processed docs visible in FinBERT sub-tab
- [ ] Manual FinBERT trigger: user selects document, clicks "Analyze" button
- [ ] Walking the Talk: manual selection of two documents (claims con-call vs actuals earnings report)
- [ ] Walking the Talk uses DeepSeek R1 14B via Ollama for claim extraction and verification
- [ ] Walking the Talk output: structured comparison table (Claim, Claimed Value, Actual Value, Verdict, Evidence) + narrative report below
- [ ] Research optimal chunking/embedding parameters for document comparison pipeline (separate from RAG)
- [ ] Persist CrediSentiment results across tab switches
- [ ] Clear chat/results option on CrediSentiment tab

### Out of Scope

- Automated document pair detection — user manually selects both documents
- Auto-processing on upload — processing is explicit from Documents tab
- Changes to existing RAG chunking/embedding parameters — existing pipeline untouched
- JWT/localStorage migration to httpOnly cookies — deferred to hardening phase
- Database migration to PostgreSQL — deferred
- Rate limiting / security hardening — deferred

## Context

- **Brownfield project** — fully functional platform with 9 backend modules, 7 frontend pages, 10 DB tables
- **Local-first AI** — all models (FinBERT, Ollama Llama 3, DeepSeek R1 14B) run locally via Ollama; no external API calls for inference
- **DeepSeek R1 14B** — locally run via Ollama; outputs `<think>...</think>` reasoning traces that need parsing
- **Existing RAG pipeline** must not be modified — separate chunking/embedding for CrediSentiment comparison
- **CrediSentiment service** already exists at `finsight/credisentiment/` but needs rework for the new two-document comparison flow
- **FinBERT** currently reloads on every call (~500MB) — should be singleton for performance
- **Codebase map** available at `.planning/codebase/` with STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, CONCERNS docs

## Constraints

- **Tech stack**: Python/FastAPI backend, React/Vite frontend — no changes
- **LLM**: DeepSeek R1 14B via local Ollama for Walking the Talk comparison
- **Sentiment**: FinBERT (ProsusAI/finbert) for sentiment analysis
- **Vector store**: ChromaDB for embeddings — separate collections/parameters per pipeline
- **No external AI APIs**: All inference must run locally
- **RAG pipeline frozen**: Existing chunking, embedding, and retrieval parameters must not change

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Remove standalone Sentiment + Credibility tabs | Consolidate into single CrediSentiment tab with sub-tabs for cleaner UX | — Pending |
| Separate chunking/embedding for CrediSentiment vs RAG | Different pipelines need different parameters for optimal accuracy | — Pending |
| Document processing initiated from Documents tab only | Single point of control; clear visual feedback on processing status | — Pending |
| DeepSeek R1 14B for Walking the Talk | Best local reasoning model at 14B; balances quality and speed | — Pending |
| Manual document selection for WTT comparison | Simpler UX; user knows which docs to compare | — Pending |
| FinBERT uses RAG chunking, shares document pool | Avoids redundant processing; sentiment analysis works well with RAG-sized chunks | — Pending |
| WTT output: table + narrative | Table for quick scan, narrative for detailed analysis | — Pending |

---
*Last updated: 2026-03-17 after initialization*
