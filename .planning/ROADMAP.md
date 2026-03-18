# Roadmap: FinSight CrediSentiment

## Overview

Transform FinSight's standalone Credibility and Sentiment tabs into a unified CrediSentiment experience with separated processing pipelines, FinBERT singleton performance, two-stage Walking the Talk claim verification using full document content, and polished category-grouped output. The journey moves from infrastructure (model singletons, pipeline separation, data model) through backend analysis capabilities (FinBERT batching, DeepSeek R1 two-stage prompting) to frontend display and UX polish. Every phase produces a testable increment.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Model and Singleton Foundation** - Dual status fields on Document model, FinBERT singleton with batch inference, ComparisonChunk table
- [x] **Phase 2: Navigation and Tab Structure** - Remove standalone Credibility/Sentiment tabs, create CrediSentiment tab with FinBERT Sentiment and Walking the Talk sub-tabs
- [x] **Phase 3: CrediSentiment Processing Pipeline** - Section-aware chunking (3500/500), separate ChromaDB collection, processing endpoint (completed 2026-03-17)
- [ ] **Phase 4: Document Processing UI** - RAG and CrediSentiment processing buttons on Documents tab with status indicators, remove processing controls from other tabs
- [x] **Phase 5: FinBERT Sentiment Analysis** - Batch inference (32 sentences), document picker filtered to RAG-processed docs, manual analyze trigger, division-level breakdown (completed 2026-03-18)
- [x] **Phase 6: Walking the Talk Backend** - Two-stage DeepSeek R1 prompting, full chunked content, 10 claim categories, robust think-tag parsing, async Ollama calls (completed 2026-03-18)
- [ ] **Phase 7: Walking the Talk Display** - Structured comparison table, narrative report, category grouping, per-category summaries, summary statistics strip
- [ ] **Phase 8: UX Polish and State Persistence** - CSS display toggle for tab persistence, clear results button, empty states

## Phase Details

### Phase 1: Data Model and Singleton Foundation
**Goal**: The backend infrastructure supports independent RAG and CrediSentiment processing with performant model loading
**Depends on**: Nothing (first phase)
**Requirements**: PROC-01, BERT-01, PERF-02
**Success Criteria** (what must be TRUE):
  1. Document model exposes separate `status` (RAG) and `cs_status` (CrediSentiment) fields, both queryable via API
  2. FinBERT model loads once at server startup and subsequent sentiment calls reuse the loaded model without re-downloading
  3. ComparisonChunk table exists and can store chunks with different parameters than RAG DocumentChunk table
  4. Existing RAG pipeline continues to function identically (no regressions)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Navigation and Tab Structure
**Goal**: Users navigate to a unified CrediSentiment tab with sub-tabs instead of separate Credibility and Sentiment pages
**Depends on**: Phase 1
**Requirements**: NAV-01, NAV-02, NAV-03, UX-03
**Success Criteria** (what must be TRUE):
  1. Sidebar no longer shows standalone "Credibility" or "Sentiment" navigation items
  2. Sidebar shows a "CrediSentiment" navigation item that opens a page with two sub-tabs
  3. "FinBERT Sentiment" sub-tab is selectable and renders its panel
  4. "Walking the Talk" sub-tab is selectable and renders its panel
  5. Each sub-tab shows an appropriate empty state when no document is selected
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md — Remove standalone nav/routes, update sub-tab labels and display toggle

### Phase 3: CrediSentiment Processing Pipeline
**Goal**: Documents can be processed through a CrediSentiment-specific pipeline with larger chunks optimized for claim comparison
**Depends on**: Phase 1
**Requirements**: PROC-02, PROC-03
**Success Criteria** (what must be TRUE):
  1. A document can be processed for CrediSentiment independently of RAG processing
  2. CrediSentiment chunks use 3500-char size with 500-char overlap and section-aware boundaries
  3. CrediSentiment embeddings are stored in a separate ChromaDB collection (`credisentiment_docs`) from RAG embeddings
  4. Processing a document for CrediSentiment does not affect its RAG processing status or chunks
**Plans**: 1 plan

Plans:
- [ ] 03-01-PLAN.md — Vectorstore, section-aware chunking pipeline, process endpoint, and tests

### Phase 4: Document Processing UI
**Goal**: Users initiate and monitor document processing for both RAG and CrediSentiment pipelines from the Documents tab
**Depends on**: Phase 1, Phase 3
**Requirements**: PROC-04, PROC-05, PROC-06, PROC-07, PROC-08
**Success Criteria** (what must be TRUE):
  1. Each document row on the Documents tab shows a "Process for RAG" button and a "Process for CrediSentiment" button
  2. Each processing button displays a status indicator with four distinct states: unprocessed, processing, processed, error
  3. A spinner or progress indicator is visible while processing is actively running
  4. RAG tab and CrediSentiment tab no longer contain any document processing controls
**Plans**: 1 plan

Plans:
- [ ] 04-01-PLAN.md — Dual processing buttons, status badges, polling, and upload removal from CrediSentiment tab

### Phase 5: FinBERT Sentiment Analysis
**Goal**: Users can run FinBERT sentiment analysis on any RAG-processed document with fast batch inference and division-level results
**Depends on**: Phase 1, Phase 2, Phase 4
**Requirements**: BERT-02, BERT-03, BERT-04, BERT-05
**Success Criteria** (what must be TRUE):
  1. FinBERT Sentiment sub-tab document picker shows only documents with RAG processing status "processed"
  2. User clicks "Analyze" button to trigger FinBERT analysis (no auto-trigger on document selection)
  3. FinBERT processes sentences in batches of 32 with dynamic padding (observable via faster execution)
  4. Division-level sentiment breakdown displays positive, negative, and neutral scores per division
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Walking the Talk Backend
**Goal**: The backend can extract claims from a con-call transcript and verify them against an earnings report using two-stage DeepSeek R1 prompting over full document content
**Depends on**: Phase 3
**Requirements**: WTT-01, WTT-02, WTT-03, WTT-04, WTT-07, WTT-10, PERF-01
**Success Criteria** (what must be TRUE):
  1. API accepts two document IDs (claims doc and actuals doc) and returns structured comparison results
  2. Walking the Talk document picker shows only documents with CrediSentiment processing status "processed"
  3. DeepSeek R1 processes all chunks of both documents (no 8000-char truncation)
  4. Claims are extracted in a first LLM pass, then verified against actuals in a second pass
  5. Claims are classified into the 10 supported categories (revenue_growth, margin_expansion, capex, debt_reduction, market_share, new_products, cost_optimization, employee_growth, geographic_expansion, regulatory_compliance)
  6. DeepSeek R1 `<think>` tags are robustly parsed with fallback for malformed output
  7. Ollama calls run asynchronously and do not block the FastAPI event loop
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md — Enum expansion, prompt templates, async Ollama, parsing utilities, and tests
- [ ] 06-02-PLAN.md — Async two-stage walk_the_talk pipeline, WTT document filter endpoint

### Phase 7: Walking the Talk Display
**Goal**: Users see Walking the Talk results as a structured, scannable comparison with category grouping and summary statistics
**Depends on**: Phase 2, Phase 6
**Requirements**: WTT-05, WTT-06, WTT-08, WTT-09
**Success Criteria** (what must be TRUE):
  1. Comparison results display as a structured table with columns: Claim, Claimed Value, Actual Value, Verdict (Met/Missed/Partial), Evidence
  2. A narrative report section appears below the structured table
  3. Claims are grouped by category with a per-category summary
  4. A summary statistics strip shows total claims count with breakdowns: X met, Y missed, Z unclear
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

### Phase 8: UX Polish and State Persistence
**Goal**: CrediSentiment results survive tab switches and users can reset analysis state cleanly
**Depends on**: Phase 5, Phase 7
**Requirements**: UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. Switching between FinBERT Sentiment and Walking the Talk sub-tabs preserves results on both (no data loss or re-fetch)
  2. Tab persistence implemented via CSS display toggle (both panels always rendered, inactive hidden with display:none)
  3. "Clear Results" button on CrediSentiment tab resets analysis state on the active sub-tab
**Plans**: TBD

Plans:
- [ ] 08-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Model and Singleton Foundation | 0/TBD | Not started | - |
| 2. Navigation and Tab Structure | 1/1 | Complete    | 2026-03-17 |
| 3. CrediSentiment Processing Pipeline | 1/1 | Complete   | 2026-03-17 |
| 4. Document Processing UI | 0/1 | Not started | - |
| 5. FinBERT Sentiment Analysis | 1/1 | Complete   | 2026-03-18 |
| 6. Walking the Talk Backend | 2/2 | Complete   | 2026-03-18 |
| 7. Walking the Talk Display | 0/TBD | Not started | - |
| 8. UX Polish and State Persistence | 0/TBD | Not started | - |
