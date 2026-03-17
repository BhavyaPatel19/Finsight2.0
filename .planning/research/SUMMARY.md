# Project Research Summary

**Project:** FinSight CrediSentiment Pipeline
**Domain:** Financial document comparison with local LLMs (FinBERT sentiment + DeepSeek R1 claim verification)
**Researched:** 2026-03-17
**Confidence:** MEDIUM

## Executive Summary

The CrediSentiment pipeline enhances FinSight with two analysis capabilities: FinBERT-powered division-level sentiment scoring and DeepSeek R1-driven "Walk the Talk" claim verification that compares management promises against actual results. The existing implementation works but has critical performance and reliability issues -- FinBERT reloads its 500MB model on every call, WTT truncates documents to 8,000 characters (losing 80%+ of content), and DeepSeek R1's JSON output parsing fails 5-15% of the time due to malformed think tags. The recommended approach is a phased refactor that fixes infrastructure first (model singletons, pipeline separation), then improves analysis quality (chunking, two-stage prompting), and finally polishes the UI.

The architecture must cleanly separate RAG and CrediSentiment into independent pipelines that share infrastructure (embedding model, ChromaDB client, Ollama connection) but maintain separate data stores (distinct ChromaDB collections, separate chunk tables, independent status tracking). This is the single most important architectural decision -- the current tight coupling where CrediSentiment auto-triggers RAG processing creates hidden failures and prevents independent optimization. No new dependencies are required; the entire improvement uses existing libraries with different configurations.

The primary risks are memory pressure (DeepSeek R1 14B needs 8-10GB RAM alongside FinBERT and embeddings on a 16GB machine), LLM output unreliability (DeepSeek R1 is a reasoning model that resists strict format compliance), and synchronous Ollama calls blocking FastAPI's event loop during 1-3 minute inference runs. All three are solvable with known patterns: model loading sequencing, robust JSON fallback parsing, and `asyncio.to_thread()` wrapping.

## Key Findings

### Recommended Stack

No new libraries needed. The improvement centers on reconfiguring existing tools.

**Core technologies (unchanged, reconfigured):**
- **FinBERT (ProsusAI/finbert):** Sentiment analysis -- must become a singleton with batch inference (32 sentences/batch, dynamic padding). Currently reloads on every call; fix yields 10-20x speedup.
- **DeepSeek R1 14B via Ollama:** Claim extraction and verification -- switch from single monolithic prompt to two-stage pipeline (extract claims per-chunk, then verify against actuals). Temperature 0.1 for extraction, 0.3 for verification.
- **ChromaDB:** Vector store -- add second collection `finsight_comparison` with larger chunks (3500 chars vs 1500 for RAG). Same PersistentClient, same embedding model, separate data.
- **BGE-base-en-v1.5:** Shared embedding model -- single singleton serves both RAG and CrediSentiment pipelines. No need for a second model.

**Critical configuration changes:**
- CrediSentiment chunks: 3500 chars, 500 overlap (vs RAG's 1500/200)
- Paragraph-boundary chunking (never split mid-paragraph)
- Ollama timeout: 300s for WTT (vs current 120s)
- DeepSeek max_tokens: 4096 for verification output

### Expected Features

**Must have (table stakes):**
- Category-grouped claim cards (currently flat list)
- Separate document processing pipelines with dual status tracking (RAG vs CS)
- Document filtering by pipeline in pickers
- FinBERT singleton model loading (performance requirement)
- Persistent results across tab switches (CSS display toggle)
- Score breakdown: met/missed/unclear counts per category

**Should have (differentiators):**
- Expanded claim taxonomy (10 categories: add capex, debt_reduction, market_share, new_products, cost_optimization)
- Summary statistics strip (total claims, strongest/weakest area)
- Claim confidence scoring from LLM
- Score context showing which documents were compared

**Defer (v2+):**
- Sentiment trend over time (needs multiple documents per company)
- Credibility history tracking
- Evidence source linking with page references
- Export to PDF/CSV
- Cross-document sentiment comparison view
- Streaming LLM output to frontend

### Architecture Approach

The architecture follows a "shared infrastructure, separate data" pattern. Both pipelines share the PDF extraction step, embedding model singleton, ChromaDB PersistentClient, and Ollama connection. They diverge at chunking (RAG: 1500-char page-aware; CS: 3500-char section-aware) and store results in separate collections and tables. The Document model gains a `cs_status` field independent of the existing `status` field.

**Major components:**
1. **`credisentiment/pipeline.py` (new)** -- Comparison-specific chunking, embedding, and processing orchestration
2. **`credisentiment/vectorstore.py` (new)** -- ChromaDB `finsight_comparison` collection CRUD, isolated from RAG collection
3. **`finsight/ml/finbert.py` (new)** -- Shared FinBERT singleton with batch inference, replaces duplicated loading in sentiment/ and credisentiment/
4. **`models/comparison_chunk.py` (new)** -- ComparisonChunk SQLModel table for CS-specific chunks
5. **Frontend CSS display toggle** -- Render both tab panels always, hide inactive with `display:none` to preserve state

### Critical Pitfalls

Ranked by impact on user experience and system reliability:

1. **DeepSeek R1 think-tag JSON parsing failures (~5-15% of calls)** -- Parse from the last `</think>` tag forward, not by stripping think blocks. Add fallback: search inside stripped think content for JSON. Validate parsed JSON against expected schema with type coercion.
2. **Document truncation to 8K chars loses 80%+ of content** -- Replace with chunk-based extraction using the new ComparisonChunk pipeline. Financial claims cluster in document middles and ends, not the first 8K characters.
3. **FinBERT reloads 500MB model on every call** -- Implement module-level singleton. This is a blocking performance bug that makes sentiment analysis take 3-10 minutes instead of 10-30 seconds.
4. **Synchronous Ollama calls block FastAPI event loop for 1-3 minutes** -- Wrap in `asyncio.to_thread()`. The entire server becomes unresponsive during WTT analysis.
5. **Memory pressure: DeepSeek R1 + FinBERT + embeddings on 16GB machine** -- Sequence model operations, configure `OLLAMA_KEEP_ALIVE=1m`, consider quantized DeepSeek R1 (`q4_K_M` variant at ~5GB vs ~10GB).

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Infrastructure and Pipeline Separation
**Rationale:** Everything else depends on clean pipeline separation and the FinBERT singleton. Fix the foundation before building features on it.
**Delivers:** Independent RAG and CrediSentiment processing pipelines, FinBERT singleton with batch inference, Document model with dual status fields, ComparisonChunk model and migration.
**Addresses:** FinBERT singleton (table stakes), dual pipeline status (table stakes), document processing separation (table stakes)
**Avoids:** Pitfall 3 (model reload), Pitfall 5 (dual pipeline data integrity), Pitfall 13 (open file handles)

### Phase 2: CrediSentiment Processing Pipeline
**Rationale:** With pipeline separation in place, build the comparison-specific chunking and vector storage. This enables the improved WTT analysis in Phase 3.
**Delivers:** `credisentiment/pipeline.py` with section-aware chunking (3500/500), `credisentiment/vectorstore.py` with `finsight_comparison` collection, "Process for CrediSentiment" endpoint and Documents tab button.
**Uses:** ChromaDB multi-collection (STACK), paragraph-boundary chunking (STACK)
**Implements:** Pipeline separation architecture, ComparisonChunk storage
**Avoids:** Pitfall 2 (context window overflow from truncation)

### Phase 3: Walk the Talk Refactor
**Rationale:** Now that documents are properly chunked and stored, replace the monolithic WTT prompt with two-stage extraction+verification. This is the highest-impact quality improvement.
**Delivers:** Two-stage DeepSeek R1 prompting (claim extraction then verification), robust JSON parsing with fallback, expanded claim categories (10 total), configurable Ollama timeout (300s).
**Addresses:** Forward-looking claim extraction (table stakes), claim verification (table stakes), expanded categories (differentiator)
**Avoids:** Pitfall 1 (think-tag parsing), Pitfall 10 (structured output unreliability), Pitfall 4 (event loop blocking via asyncio.to_thread)

### Phase 4: Frontend Polish
**Rationale:** Backend improvements are complete; now surface them properly in the UI. Category-grouped claims, persistent tab state, and dual status badges.
**Delivers:** CSS display toggle for tab persistence, category-grouped claim cards with per-category summaries, summary statistics strip, dual processing status badges on Documents tab, document picker filtering by pipeline status.
**Addresses:** Category grouping (table stakes), tab persistence (table stakes), summary stats (differentiator)
**Avoids:** Pitfall 9 (frontend state loss), Pitfall 12 (no timeout feedback)

### Phase 5: Performance and Reliability Hardening
**Rationale:** With features complete, harden for real-world usage. Memory management, concurrent request handling, SQLite contention.
**Delivers:** Async Ollama wrapper, memory pressure monitoring, SQLite WAL mode, elapsed time counter in UI, request cancellation support.
**Addresses:** System stability under load
**Avoids:** Pitfall 4 (event loop blocking), Pitfall 8 (memory pressure), Pitfall 14 (SQLite contention)

### Phase Ordering Rationale

- Phases 1-2 are infrastructure that all subsequent work depends on. Attempting WTT improvements (Phase 3) without pipeline separation would require working around the 8K truncation hack.
- Phase 3 (WTT refactor) comes before Phase 4 (frontend) because the frontend needs to display category-grouped claims that the new prompt taxonomy produces.
- Phase 5 (hardening) is last because performance issues are tolerable during development but must be fixed before any demo or user testing.
- Each phase produces a testable increment: Phase 1 can be verified by checking singleton behavior and dual status fields; Phase 2 by processing a document for CS; Phase 3 by running a comparison; Phase 4 visually; Phase 5 under concurrent load.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (WTT Refactor):** DeepSeek R1 prompt templates need empirical iteration with real financial documents. The two-stage approach is architecturally sound but specific prompt wording, temperature settings, and claim category definitions need A/B testing. Run `/gsd:research-phase` before implementing.
- **Phase 5 (Hardening):** Memory profiling on the target machine is needed. The 16GB constraint with DeepSeek R1 14B (~8-10GB) is tight. May need to evaluate the quantized `q4_K_M` variant.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** FinBERT singleton and SQLModel migration are well-documented patterns. No research needed.
- **Phase 2 (Processing Pipeline):** ChromaDB multi-collection and paragraph-boundary chunking are straightforward. Follow the code examples in STACK.md and ARCHITECTURE.md directly.
- **Phase 4 (Frontend):** CSS display toggle and category grouping are standard React patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | No new dependencies. FinBERT batching and ChromaDB multi-collection are HIGH confidence. DeepSeek R1 temperature tuning is LOW -- needs empirical validation. |
| Features | MEDIUM | Table stakes are clear from codebase analysis. Differentiator value is inferred without competitor verification (web search unavailable). |
| Architecture | HIGH | Based entirely on existing codebase analysis. Pipeline separation and component boundaries are well-defined. |
| Pitfalls | MEDIUM | Pitfalls 1-5 are directly observed in code (HIGH). DeepSeek R1 failure rates and memory thresholds are estimates (LOW-MEDIUM). |

**Overall confidence:** MEDIUM -- The architecture and infrastructure decisions are solid. The uncertainty is concentrated in DeepSeek R1 prompt engineering and memory constraints, both of which are empirically testable early.

### Gaps to Address

- **DeepSeek R1 prompt effectiveness:** The two-stage prompting architecture is sound, but specific prompt templates need testing against real concall transcripts and earnings reports. Plan for 2-3 prompt iterations in Phase 3.
- **Memory budget on target hardware:** DeepSeek R1 14B + FinBERT + embeddings on 16GB RAM is theoretically tight. Profile actual usage before Phase 5. The quantized model (`q4_K_M`) is the fallback.
- **Claim category coverage:** The 10-category taxonomy is based on domain knowledge, not corpus analysis. Some categories (dividend_buyback, sustainability) may rarely appear in Indian company filings. Validate against 5-10 real documents.
- **Sentence splitting quality:** The improved regex in STACK.md is better than the current approach but still imperfect for financial text. Consider NLTK sent_tokenize as a more robust alternative if the regex produces noisy FinBERT inputs.
- **Database migration strategy:** Adding `cs_status` and `cs_chunk_count` columns to the Document table requires an Alembic migration (or manual ALTER TABLE). Ensure existing documents get `cs_status="pending"` as default.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `finsight/credisentiment/service.py`, `finsight/sentiment/service.py`, `finsight/rag/service.py`
- Frontend component analysis of `frontend/src/pages/CredibilitySentiment.jsx`
- Project requirements at `.planning/PROJECT.md`
- ChromaDB PersistentClient multi-collection API (well-documented)
- PyTorch/Transformers batch inference patterns (well-established)

### Secondary (MEDIUM confidence)
- DeepSeek R1 model architecture and think-trace behavior (documented but failure rates are estimates)
- Financial NLP chunking best practices (literature-based, not empirically tested on this corpus)
- BGE embedding model family characteristics (well-characterized but comparison-specific performance untested)

### Tertiary (LOW confidence)
- DeepSeek R1 temperature settings (0.1/0.3) -- experiential, needs A/B testing
- Memory consumption estimates for concurrent model loading -- needs profiling
- Competitor feature benchmarks (Sentieo, AlphaSense) -- from training data, not verified

---
*Research completed: 2026-03-17*
*Ready for roadmap: yes*
