# Feature Landscape

**Domain:** Financial credibility analysis and sentiment intelligence (claim verification, FinBERT sentiment, document comparison)
**Researched:** 2026-03-17
**Confidence:** MEDIUM (based on domain expertise and codebase analysis; web search unavailable for competitor verification)

## Table Stakes

Features users expect from a credibility/sentiment analysis tool. Missing any of these makes the product feel incomplete or untrustworthy.

### Claim Extraction and Verification

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Forward-looking claim extraction from con-calls | Core value proposition -- users come specifically for this | High | Already exists via DeepSeek R1 prompt; needs structured categories |
| Claim-vs-actual comparison table | Users need scannable output showing what was promised vs delivered | Med | Exists: claim/claimed_value/actual_value/met/explanation format |
| Met/Missed/Unclear verdict per claim | Binary outcome is the minimum useful output | Low | Exists with tri-state (true/false/null) |
| Overall credibility score (0-100) | Users need a summary number before diving into details | Low | Exists with radial dial visualization |
| Narrative summary of comparison | Score alone is not enough; users need qualitative assessment | Med | Exists via LLM-generated narrative_summary |
| Category-based claim grouping | Users scan by area (revenue, margins, expansion) not random order | Low | Categories exist but not grouped in UI |
| Document metadata display (which docs compared, dates) | Trust requires knowing what was compared | Low | Partially exists -- shows doc labels below narrative |
| Processing status/progress indicator | LLM analysis takes 1-3 minutes; users need to know it is working | Low | Exists with spinner + text |

### FinBERT Sentiment Analysis

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Document-level sentiment score | Baseline output -- overall positive/negative/neutral breakdown | Low | Exists in older sentiment service |
| Division/section-level breakdown | Users care about sentiment differences across business segments | Med | Exists with horizontal bar chart + table |
| Positive/Negative/Neutral proportions | Standard FinBERT output format | Low | Exists in division sentiment table |
| Multi-document analysis in one batch | Users want to compare sentiment across multiple filings | Low | Exists -- checkbox selection + batch analyze |
| Visual bar chart of division scores | Faster comprehension than table alone | Low | Exists with Recharts horizontal bars |

### Document Management (for this feature)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Document picker with metadata | Users need to identify documents by symbol, type, year | Low | Exists in left panel |
| Document upload with metadata fields | Users bring their own PDFs | Low | Exists with symbol, doc_type, fiscal_year fields |
| Processing status per document (pending/indexed/error) | Users need to know which docs are ready for analysis | Low | Exists with StatusBadge component |
| Filtering documents by processing pipeline | RAG-processed docs should not show in WTT picker and vice versa | Med | Planned but not yet implemented |

## Differentiators

Features that set the product apart. Not universally expected but add significant value.

### High-Value Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Claim category taxonomy (8+ categories) | Goes beyond basic "met/missed" to structured financial analysis | Med | See Claim Categories section below |
| Sentiment trend over time (same company, multiple quarters) | Shows whether management tone is improving or deteriorating | Med | Partially exists in sentiment history endpoint but no UI in CrediSentiment tab |
| Cross-document sentiment comparison (side by side) | Lets users see how tone changed between claims doc and actuals doc | Med | FinBERT runs on individual docs; no side-by-side comparison view |
| Credibility score history (same company, multiple pairs) | Shows whether management credibility improves over time | Med | WalkTheTalkResult stores per-pair but no historical trend view |
| Claim severity/materiality weighting | Not all claims matter equally -- revenue guidance matters more than vague "we plan to" | High | Would require LLM to assign importance weights |
| Evidence source linking (page/paragraph references) | Users can verify LLM output against original text | High | Currently truncates at 8000 chars; no source linking |
| Sentiment-to-credibility correlation | Show whether optimistic sentiment in claims doc correlates with missed targets | Med | Sentiment context passed to WTT prompt but not visualized |
| Export results (PDF/CSV) | Analysts need to share findings with teams | Med | Not implemented |

### Medium-Value Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Automatic document type detection | Reduce user effort -- system identifies con-call vs earnings report | Med | Currently manual selection |
| Claim confidence scoring | LLM rates how confident it is in each claim match | Low | Could add to LLM prompt with minimal effort |
| Red flag highlighting | Automatically flag patterns like "consistently optimistic guidance with missed targets" | Med | Would analyze WTT history |
| Comparative heatmap (divisions x quarters) | Dense visualization of sentiment patterns over time | Med | Requires sentiment data for multiple periods |

## Anti-Features

Features to explicitly NOT build for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Auto-matching document pairs | Adds complexity; user knows which docs to compare; error-prone matching would erode trust | Manual selection (current approach) |
| Real-time streaming of LLM analysis | DeepSeek R1 outputs thinking tokens that should not be shown; adds WebSocket complexity | Show spinner with estimated time |
| Sentiment prediction (forecasting future sentiment) | Unreliable; FinBERT is a classifier not a predictor | Show historical trends, let user draw conclusions |
| Automated trading signals from credibility scores | Huge liability; regulatory concerns; out of scope | Present as informational analysis only |
| Multi-language document support | Indian filings are predominantly English; adds NLP complexity | English only |
| Social media sentiment integration | Different domain; dilutes focus on document analysis | Keep focused on filed documents |
| Auto-processing on document upload | PROJECT.md explicitly marks this out of scope; user should control when processing happens | Explicit "Process" buttons on Documents tab |

## Claim Categories (Recommended Taxonomy)

The existing system uses 6 categories: `revenue_growth`, `margin`, `debt`, `expansion`, `guidance`, `other`. This is a solid foundation. Recommended expansion for completeness:

### Tier 1 -- Core Financial Categories (keep)

| Category | What It Captures | Example Claim |
|----------|-----------------|---------------|
| `revenue_growth` | Top-line growth targets, segment revenue guidance | "We expect 15% revenue growth in FY26" |
| `margin` | EBITDA, operating margin, net margin targets | "EBITDA margins to improve to 22-24%" |
| `guidance` | Forward earnings guidance, EPS estimates | "We expect EPS of Rs 45-48 for FY26" |

### Tier 2 -- Strategic Categories (expand)

| Category | What It Captures | Example Claim |
|----------|-----------------|---------------|
| `capex` | Capital expenditure plans, new facility announcements | "We plan to invest Rs 500 Cr in new plant" |
| `debt_reduction` | Deleveraging targets, debt-to-equity goals | "Target net debt/EBITDA below 2x by Q4" |
| `market_share` | Market position claims, competitive positioning | "We aim to capture 30% market share in segment" |
| `new_products` | Product launches, pipeline commitments | "Three new product lines launching in H2" |
| `cost_optimization` | Cost reduction programs, efficiency targets | "Targeting 200bps cost reduction through automation" |
| `dividend_buyback` | Shareholder return commitments | "Dividend payout ratio to increase to 40%" |
| `expansion` | Geographic or segment expansion plans (keep existing) | "Entering Southeast Asian markets in FY26" |

### Tier 3 -- Qualitative Categories (optional)

| Category | What It Captures | Example Claim |
|----------|-----------------|---------------|
| `hiring` | Headcount growth, talent acquisition plans | "Plan to add 5,000 engineers this year" |
| `regulatory` | Compliance commitments, regulatory milestones | "Expect SEBI approval by Q3" |
| `sustainability` | ESG commitments, carbon reduction targets | "Carbon neutral by 2030" |

**Recommendation:** Expand the LLM prompt to use Tier 1 + Tier 2 categories (10 total). Tier 3 is optional and can be added later based on user feedback.

## UI Patterns for Comparison Output

### Pattern 1: Score Dashboard (exists, refine)

The current layout is strong -- radial dial for overall score + narrative card beside it. Refinements:

- Add a **score breakdown bar** below the dial showing: X claims met, Y missed, Z unclear (horizontal stacked bar)
- Add **score context**: "Based on N claims extracted from [Doc A] vs [Doc B]"
- Color-code the narrative card border based on score tier (green/amber/red)

### Pattern 2: Claim Cards with Category Grouping (enhance)

Current: flat list of claim cards. Better pattern:

```
[Category Header: Revenue Growth] (2 of 3 met)
  [Claim Card 1] -- Met
  [Claim Card 2] -- Missed
  [Claim Card 3] -- Met

[Category Header: Margins] (0 of 2 met)
  [Claim Card 4] -- Missed
  [Claim Card 5] -- Unclear
```

Each category section gets a mini-summary: "2 of 3 claims met" with a colored indicator.

### Pattern 3: Summary Statistics Strip

Between the score dial and claim cards, add a statistics strip:

```
| Total Claims | Met | Missed | Unclear | Strongest Area | Weakest Area |
| 12           | 7   | 3      | 2       | Revenue Growth | Margins      |
```

### Pattern 4: Division Sentiment Bar Chart (exists, refine)

Current horizontal bar chart is effective. Refinements:

- Add **overall score annotation** on each bar (number at bar end)
- Add **sentence count** as bar opacity (more sentences = higher confidence = more opaque)
- When comparing two documents, show **paired bars** (claims doc vs actuals doc sentiment side by side)

### Pattern 5: Document Processing Status on Documents Tab

For the planned "Process for RAG" / "Process for CrediSentiment" buttons:

```
[Document Row]
  INFY - Annual Report FY25                    [RAG: Indexed] [CrediSentiment: Not processed]
  Status indicators: green checkmark / gray dash / blue spinner / red X
  Action buttons: [Process for RAG] [Process for CrediSentiment]
```

Use a **dual-badge** pattern: each document shows two processing statuses independently.

### Pattern 6: Empty States (exists, good)

Current empty states are well-designed with icon + instructional text. Keep this pattern for all sub-tabs.

## Document Processing UX

### Status Indicators (4-state model)

| State | Visual | Meaning |
|-------|--------|---------|
| Not processed | Gray dash badge | Document uploaded but not processed for this pipeline |
| Processing | Blue spinner badge | Currently being chunked/embedded/analyzed |
| Ready | Green checkmark badge | Processed and available for analysis |
| Error | Red X badge | Processing failed; show error on hover |

### Progress Tracking for Long Operations

| Operation | Expected Duration | UX Pattern |
|-----------|-------------------|------------|
| FinBERT analysis (single doc) | 15-60 seconds | Spinner with "Analyzing N sentences..." |
| FinBERT analysis (multi-doc) | 1-5 minutes | Progress bar: "Document 2 of 5..." |
| Walking the Talk (DeepSeek R1) | 1-3 minutes | Spinner with "DeepSeek R1 is analyzing... This may take 1-3 minutes" |
| Document indexing for CrediSentiment | 30-120 seconds | Spinner on document row in Documents tab |

### Sub-Tab Layout Pattern

The current two-tab layout (Division Sentiment / Walking the Talk) is clean. Structure:

```
[CrediSentiment Page]
  [Header: Credibility Sentiment]
  [Left Panel: Document Picker (280px fixed)]
  [Right Panel: Tab content]
    [Tab Bar: "Division Sentiment" | "Walking the Talk"]
    [Tab Content Area (scrollable)]
```

This pattern works because:
- Document picker is shared across both sub-tabs (same documents, different selections)
- Tabs are visually distinct with icons
- Content area scrolls independently

**Enhancement:** Consider adding a third future tab for "Sentiment Trends" showing historical sentiment for a company across multiple documents.

## Feature Dependencies

```
Document Upload --> Document Processing (RAG or CrediSentiment pipeline)
    |
    +--> RAG Pipeline --> RAG Chat (existing, unchanged)
    |
    +--> CrediSentiment Pipeline --> FinBERT Division Sentiment
    |                             |
    |                             +--> Walking the Talk (requires 2 processed docs)
    |
    +--> FinBERT uses RAG-indexed docs (shares document pool per PROJECT.md)

Walking the Talk --> Claim Extraction (DeepSeek R1)
                 --> Claim Comparison Table
                 --> Overall Credibility Score
                 --> Narrative Summary

Division Sentiment --> Section Detection (from PageMetadata/DocumentSection)
                   --> Per-Section FinBERT Scoring
                   --> Bar Chart + Table Visualization
```

**Key dependency:** Walking the Talk requires TWO documents to be processed. FinBERT works on single documents. The document picker behavior should differ between tabs -- multi-select for FinBERT, paired selection for WTT.

## MVP Recommendation

### Must have for this milestone (all table stakes):

1. **Category-grouped claim cards** -- Group WTT claims by category with per-category summary (currently flat list)
2. **Separate document processing pipelines** -- Documents tab shows dual processing status (RAG vs CrediSentiment)
3. **Document filtering by pipeline** -- WTT picker shows only CrediSentiment-processed docs; RAG picker shows only RAG-processed docs
4. **FinBERT singleton model loading** -- Currently reloads ~500MB model on every call; must cache
5. **Persist results across tab switches** -- Currently results may reset when switching between Sentiment and WTT tabs
6. **Clear results button** -- Let users reset and start fresh

### Should have (high-value differentiators):

7. **Summary statistics strip** -- Met/Missed/Unclear counts + strongest/weakest area
8. **Expanded claim categories** -- Add capex, debt_reduction, market_share, new_products, cost_optimization (Tier 2)
9. **Score breakdown bar** -- Visual showing proportion of met/missed/unclear claims

### Defer to next milestone:

- Sentiment trend over time (requires multiple documents per company to be useful)
- Credibility history (same -- needs multiple comparisons)
- Evidence source linking (high complexity, requires chunk-level tracking)
- Export to PDF/CSV (nice-to-have, not core)
- Cross-document sentiment comparison view

## Sources

- Codebase analysis: `finsight/credisentiment/service.py`, `finsight/credisentiment/schemas.py`, `finsight/sentiment/service.py`
- Frontend analysis: `frontend/src/pages/CredibilitySentiment.jsx`
- Project context: `.planning/PROJECT.md` (requirements, constraints, decisions)
- Domain knowledge of financial analysis platforms (Sentieo/AlphaSense claim tracking, Bloomberg earnings surprise, Refinitiv StarMine credibility models) -- LOW confidence on specific competitor features as web search was unavailable for verification
- FinBERT model behavior from ProsusAI/finbert documentation (HIGH confidence from training data, widely documented)
