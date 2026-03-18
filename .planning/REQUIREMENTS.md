# Requirements: FinSight CrediSentiment

**Defined:** 2026-03-17
**Core Value:** Investors can verify whether company management delivers on their promises by comparing con-call claims against actual earnings, powered by locally-run AI models.

## v1 Requirements

### Navigation

- [x] **NAV-01**: Standalone Credibility tab is removed from sidebar navigation
- [x] **NAV-02**: Standalone Sentiment tab is removed from sidebar navigation
- [x] **NAV-03**: CrediSentiment tab has two sub-tabs: "FinBERT Sentiment" and "Walking the Talk"

### Document Processing

- [ ] **PROC-01**: Document model has separate status fields for RAG (`status`) and CrediSentiment (`cs_status`) processing
- [x] **PROC-02**: CrediSentiment pipeline uses separate chunking parameters (3500 chars / 500 overlap, section-aware) from RAG pipeline (1500/200)
- [x] **PROC-03**: CrediSentiment embeddings stored in a separate ChromaDB collection (`credisentiment_docs`)
- [ ] **PROC-04**: Documents tab shows "Process for RAG" button per document with visual status indicator
- [ ] **PROC-05**: Documents tab shows "Process for CrediSentiment" button per document with visual status indicator
- [ ] **PROC-06**: Processing status indicators show distinct states: unprocessed / processing / processed / error
- [ ] **PROC-07**: Processing progress indicator (spinner/percentage) visible during active processing
- [ ] **PROC-08**: Processing controls removed from RAG tab and CrediSentiment tab (Documents tab is sole processing entry point)

### FinBERT Sentiment

- [ ] **BERT-01**: FinBERT model loaded as module-level singleton (load once per server process)
- [x] **BERT-02**: FinBERT processes sentences in batches of 32 with dynamic padding
- [x] **BERT-03**: User selects a document from picker showing only RAG-processed documents
- [x] **BERT-04**: User clicks "Analyze" button to trigger FinBERT analysis (manual trigger, not auto)
- [x] **BERT-05**: Division-level sentiment breakdown displayed with positive/negative/neutral scores

### Walking the Talk

- [ ] **WTT-01**: User manually selects two documents: claims doc (con-call) and actuals doc (earnings report)
- [ ] **WTT-02**: Only CrediSentiment-processed documents visible in WTT document picker
- [ ] **WTT-03**: Two-stage DeepSeek R1 14B prompting: extract claims per-chunk, then verify against actuals
- [ ] **WTT-04**: Full chunked document content used (remove 8000-char truncation)
- [ ] **WTT-05**: Output displays structured comparison table: Claim, Claimed Value, Actual Value, Verdict (Met/Missed/Partial), Evidence
- [ ] **WTT-06**: Output displays narrative report below the structured table
- [x] **WTT-07**: 10 claim categories supported: revenue_growth, margin_expansion, capex, debt_reduction, market_share, new_products, cost_optimization, employee_growth, geographic_expansion, regulatory_compliance
- [ ] **WTT-08**: Claims grouped by category in display with per-category summary
- [ ] **WTT-09**: Summary statistics strip showing total claims: X met, Y missed, Z unclear
- [x] **WTT-10**: Robust DeepSeek R1 `<think>` tag parsing with fallback for malformed/multiple think blocks

### UX / State

- [ ] **UX-01**: CrediSentiment results persist across tab switches (CSS display toggle, not conditional render)
- [ ] **UX-02**: Clear results button on CrediSentiment tab resets analysis state
- [x] **UX-03**: Empty states displayed when no document is selected on each sub-tab

### Performance

- [x] **PERF-01**: Ollama calls for DeepSeek R1 use async (`httpx.AsyncClient` or `asyncio.to_thread`)
- [ ] **PERF-02**: FinBERT singleton eliminates repeated ~500MB model loads

## v2 Requirements

### Trends & History

- **TREND-01**: Sentiment trend chart across multiple documents for same symbol over time
- **TREND-02**: Credibility history showing claim fulfillment rate per company
- **TREND-03**: Evidence source linking (click claim → jump to source passage)

### Processing

- **PROC-V2-01**: Batch processing queue for multiple documents
- **PROC-V2-02**: Cancel button for in-progress analysis
- **PROC-V2-03**: Elapsed time counter during LLM analysis

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automated document pair detection | User manually selects; simpler UX, avoids wrong matches |
| Auto-processing on upload | Processing is explicit from Documents tab per user decision |
| Changes to existing RAG chunking/embedding | Existing pipeline frozen; separate params for CrediSentiment |
| JWT/localStorage → httpOnly cookies | Deferred to security hardening milestone |
| Database migration to PostgreSQL | Deferred to scalability milestone |
| External AI API calls | All inference runs locally (Ollama, FinBERT) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NAV-01 | Phase 2 | Complete |
| NAV-02 | Phase 2 | Complete |
| NAV-03 | Phase 2 | Complete |
| PROC-01 | Phase 1 | Pending |
| PROC-02 | Phase 3 | Complete |
| PROC-03 | Phase 3 | Complete |
| PROC-04 | Phase 4 | Pending |
| PROC-05 | Phase 4 | Pending |
| PROC-06 | Phase 4 | Pending |
| PROC-07 | Phase 4 | Pending |
| PROC-08 | Phase 4 | Pending |
| BERT-01 | Phase 1 | Pending |
| BERT-02 | Phase 5 | Complete |
| BERT-03 | Phase 5 | Complete |
| BERT-04 | Phase 5 | Complete |
| BERT-05 | Phase 5 | Complete |
| WTT-01 | Phase 6 | Pending |
| WTT-02 | Phase 6 | Pending |
| WTT-03 | Phase 6 | Pending |
| WTT-04 | Phase 6 | Pending |
| WTT-05 | Phase 7 | Pending |
| WTT-06 | Phase 7 | Pending |
| WTT-07 | Phase 6 | Complete |
| WTT-08 | Phase 7 | Pending |
| WTT-09 | Phase 7 | Pending |
| WTT-10 | Phase 6 | Complete |
| UX-01 | Phase 8 | Pending |
| UX-02 | Phase 8 | Pending |
| UX-03 | Phase 2 | Complete |
| PERF-01 | Phase 6 | Complete |
| PERF-02 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after roadmap creation*
