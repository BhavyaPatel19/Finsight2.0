# Phase 6: Walking the Talk Backend - Research

**Researched:** 2026-03-18
**Domain:** Two-stage LLM claim extraction and verification, async Ollama integration, DeepSeek R1 output parsing
**Confidence:** HIGH

## Summary

Phase 6 transforms the existing single-pass Walking the Talk implementation into a robust two-stage pipeline. The current codebase (`finsight/credisentiment/service.py`) already has a working `walk_the_talk()` function that uses a single LLM call with both documents truncated to 8000 chars, only 4 claim categories, synchronous Ollama calls via `httpx.Client`, and fragile `<think>` tag parsing using a simple regex. All of these must be upgraded.

The key changes are: (1) split the single prompt into two stages -- claim extraction per-chunk, then verification against actuals, (2) process ALL chunks from ComparisonChunk table instead of truncating to 8000 chars, (3) expand from 4 to 10 claim categories, (4) make Ollama calls async using `httpx.AsyncClient`, (5) implement robust `<think>` tag parsing that handles malformed/unclosed/multiple think blocks, and (6) filter the WTT document picker to only show `cs_status == "indexed"` documents.

**Primary recommendation:** Refactor `walk_the_talk()` into an async two-stage pipeline that reads ComparisonChunk rows, processes chunks through stage-1 (extract claims) and stage-2 (verify claims), uses `httpx.AsyncClient` for non-blocking Ollama calls, and returns results through the existing `WalkTheTalkResult` model.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WTT-01 | User manually selects two documents: claims doc (con-call) and actuals doc (earnings report) | Existing `WalkTheTalkRequest` schema already accepts `claims_document_id` and `actuals_document_id`. Router endpoint exists at `POST /walk-the-talk`. No schema change needed, just service logic upgrade. |
| WTT-02 | Only CrediSentiment-processed documents visible in WTT document picker | Current `available-documents` endpoint returns ALL docs. Need new endpoint or filter parameter that returns only `cs_status == "indexed"` docs. |
| WTT-03 | Two-stage DeepSeek R1 14B prompting: extract claims per-chunk, then verify against actuals | Current implementation uses single prompt with both docs. Must split into: Stage 1 (per-chunk claim extraction from claims doc) and Stage 2 (verification of aggregated claims against actuals doc chunks). |
| WTT-04 | Full chunked document content used (remove 8000-char truncation) | Current code reads `doc.text_path` and truncates with `[:8000]`. Must instead load all `ComparisonChunk` rows for each document and process them iteratively. |
| WTT-07 | 10 claim categories supported | Current `ClaimCategory` enum has only 4 values. Must expand to 10: revenue_growth, margin_expansion, capex, debt_reduction, market_share, new_products, cost_optimization, employee_growth, geographic_expansion, regulatory_compliance. |
| WTT-10 | Robust DeepSeek R1 `<think>` tag parsing with fallback for malformed/multiple think blocks | Current parsing in `_parse_deepseek_thinking` uses simple `re.search(r"<think>(.*?)</think>")` which fails on unclosed tags, multiple think blocks, or nested tags. Need robust multi-pattern fallback. |
| PERF-01 | Ollama calls use async (`httpx.AsyncClient` or `asyncio.to_thread`) | Current `call_ollama()` uses synchronous `httpx.Client` which blocks the FastAPI event loop. Must create async variant. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.133.0 | Async web framework | Already installed; native async endpoint support |
| httpx | 0.28.1 | HTTP client (async + sync) | Already installed; `AsyncClient` for non-blocking Ollama calls |
| SQLModel | (installed) | ORM | Already used throughout for Document, ComparisonChunk, WalkTheTalkResult |
| Pydantic | (installed) | Request/response schemas | Already used for WalkTheTalkRequest/Response |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | - | Think tag parsing | Robust regex patterns for DeepSeek R1 output |
| json (stdlib) | - | LLM JSON output parsing | Parse structured claim extraction results |

### No New Dependencies
This phase requires zero new pip installs. All needed libraries (httpx async, FastAPI async, json, re) are already available.

## Architecture Patterns

### Current vs. Target Architecture

```
CURRENT (single-pass, synchronous):
  walk_the_talk()
    -> read text_path[:8000] for both docs
    -> single call_ollama() with both texts in one prompt
    -> synchronous httpx.Client blocks event loop
    -> simple regex strips <think> tags

TARGET (two-stage, async):
  walk_the_talk()  [now async]
    -> load ComparisonChunk rows for both documents
    -> Stage 1: for each claims chunk, async call_ollama_async() to extract claims
    -> Deduplicate/merge extracted claims across chunks
    -> Stage 2: build verification prompt with claims + all actuals chunks
    -> async call_ollama_async() to verify each claim against actuals
    -> Robust think-tag stripping with multi-pattern fallback
    -> Return through existing WalkTheTalkResult model
```

### Recommended File Changes

```
finsight/
├── credisentiment/
│   ├── service.py        # Refactor walk_the_talk() to async two-stage
│   ├── router.py         # Make walk_the_talk_endpoint async, add cs_status filter
│   ├── schemas.py        # Add category field to ClaimComparison (already exists)
│   └── prompts.py        # NEW: Stage 1 and Stage 2 prompt templates
├── models/
│   └── enums.py          # Expand ClaimCategory to 10 values
├── rag/
│   └── service.py        # Add call_ollama_async() alongside existing call_ollama()
tests/
├── test_wtt_backend.py   # NEW: Tests for two-stage pipeline, think parsing, async
```

### Pattern 1: Async Ollama Calls

**What:** Create `call_ollama_async()` that uses `httpx.AsyncClient` so FastAPI's event loop is not blocked during the 30-120 second Ollama inference calls.

**When to use:** Any endpoint that calls Ollama and should remain responsive.

**Example:**
```python
# In finsight/rag/service.py (new function alongside existing call_ollama)
async def call_ollama_async(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 2048,
) -> str:
    """Non-blocking Ollama call using httpx.AsyncClient."""
    model_name = model or OLLAMA_MODEL_PRIMARY
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"[LLM error: {e}]"
```

**Key detail:** The timeout should be increased from 120s to 180s because processing full document chunks generates longer prompts that take more time.

### Pattern 2: Two-Stage Prompting

**What:** Split claim extraction and verification into separate LLM calls.

**Stage 1 - Claim Extraction (per chunk):**
```python
STAGE1_EXTRACT_CLAIMS_PROMPT = """You are a financial analyst. Extract all forward-looking claims, promises, and guidance from this earnings call transcript excerpt.

For each claim, provide:
- claim: what was stated/promised
- category: one of [revenue_growth, margin_expansion, capex, debt_reduction, market_share, new_products, cost_optimization, employee_growth, geographic_expansion, regulatory_compliance]
- claimed_value: the specific number/target if mentioned (or null)
- context_snippet: the exact quote (brief)

Excerpt:
{chunk_text}

Respond ONLY with a JSON array. If no claims found, return [].
"""
```

**Stage 2 - Verification (claims against actuals):**
```python
STAGE2_VERIFY_CLAIMS_PROMPT = """You are a financial analyst auditing management credibility.

Here are claims extracted from an earlier earnings call:
{claims_json}

Here are the actual results from the subsequent earnings report:
{actuals_text}

For each claim, determine:
- Whether it was MET, MISSED, or PARTIAL
- The actual value achieved
- A brief explanation

Also provide an overall credibility score (0-100).

Respond ONLY with this JSON:
{{
  "overall_score": <number>,
  "claims": [
    {{
      "claim": "<original claim>",
      "category": "<category>",
      "claimed_value": "<original target>",
      "actual_value": "<what actually happened>",
      "met": true|false|null,
      "explanation": "<brief comparison>"
    }}
  ],
  "narrative_summary": "<2-3 sentence assessment>"
}}
"""
```

**Why two stages:** Single-pass with both full documents exceeds context window limits. Per-chunk extraction allows processing arbitrarily large documents. Verification as a separate pass focuses the LLM on comparison rather than dual-task extraction+verification.

### Pattern 3: Robust Think-Tag Parsing

**What:** Handle all DeepSeek R1 `<think>` tag edge cases.

```python
def strip_think_tags(text: str) -> str:
    """
    Remove <think>...</think> blocks from DeepSeek R1 output.
    Handles: properly closed tags, multiple think blocks,
    unclosed tags, nested tags, whitespace variations.
    """
    # Pass 1: Remove all properly closed <think>...</think> blocks
    result = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Pass 2: Handle unclosed <think> tag (everything from <think> to end)
    result = re.sub(r"<think>.*$", "", result, flags=re.DOTALL)

    # Pass 3: Handle orphan </think> tag
    result = result.replace("</think>", "")

    return result.strip()
```

**Why this approach:** DeepSeek R1 14B sometimes produces: unclosed `<think>` tags (starts thinking but doesn't close before generating answer), multiple `<think>` blocks, or `<think>` content mixed with actual response. The three-pass approach handles all observed failure modes.

### Pattern 4: Loading Chunks Instead of Truncated Text

**What:** Read ComparisonChunk rows from the database instead of reading text_path[:8000].

```python
from sqlmodel import select
from finsight.models import ComparisonChunk

def get_document_chunks(session: Session, document_id: int) -> list[str]:
    """Load all CrediSentiment chunks for a document, ordered by chunk_index."""
    stmt = (
        select(ComparisonChunk)
        .where(ComparisonChunk.document_id == document_id)
        .order_by(ComparisonChunk.chunk_index)
    )
    chunks = list(session.exec(stmt).all())
    return [c.text for c in chunks]
```

**Why from DB:** ComparisonChunk rows are already created during Phase 3 processing. They have proper section-aware boundaries (3500 char / 500 overlap). Reading from DB is faster than re-parsing the PDF, and the chunks are already sized appropriately for LLM context windows.

### Pattern 5: Document Picker Filtering

**What:** Filter available documents endpoint for WTT to show only `cs_status == "indexed"`.

```python
@router.get("/wtt-documents", response_model=list[AvailableDocumentResponse])
def get_wtt_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return only CrediSentiment-processed documents for WTT picker."""
    stmt = (
        select(Document)
        .where(Document.cs_status == "indexed")
        .order_by(Document.ingested_at.desc())
    )
    docs = list(session.exec(stmt).all())
    return [
        AvailableDocumentResponse(
            id=d.id, symbol=d.symbol, doc_type=d.doc_type,
            company_name=d.company_name, fiscal_quarter=d.fiscal_quarter,
            fiscal_year=d.fiscal_year, status=d.cs_status,
            chunk_count=d.cs_chunk_count or 0, file_size=d.file_size,
        )
        for d in docs
    ]
```

### Anti-Patterns to Avoid

- **Single mega-prompt with both full documents:** Exceeds DeepSeek R1 14B context window (~32K tokens). Two-stage avoids this.
- **Synchronous Ollama in async endpoint:** Marking the endpoint `async def` but calling synchronous `call_ollama()` inside it would STILL block the event loop. Must use `httpx.AsyncClient` or `asyncio.to_thread(call_ollama, ...)`.
- **Processing chunks in parallel with `asyncio.gather`:** Ollama runs locally on a single GPU. Parallel requests queue internally and may OOM. Process chunks sequentially.
- **Hardcoding category strings in multiple places:** Use the `ClaimCategory` enum as single source of truth. Reference `[e.value for e in ClaimCategory]` in prompts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async HTTP | Custom threading/subprocess | `httpx.AsyncClient` | Already installed, native async/await, handles timeouts properly |
| JSON extraction from LLM output | Complex parsing | Find first `{`/`[` and last `}`/`]`, then `json.loads` | LLM may wrap JSON in markdown fences or add preamble text |
| Claim deduplication | Exact string matching | Semantic grouping by category + fuzzy value matching | Same claim may appear in overlapping chunks due to 500-char overlap |

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop
**What goes wrong:** Using `httpx.Client` (sync) inside an `async def` endpoint blocks all other FastAPI requests for 30-120 seconds per Ollama call.
**Why it happens:** FastAPI runs `async def` endpoints on the main event loop. Sync I/O in async context blocks everything.
**How to avoid:** Either use `httpx.AsyncClient` (preferred) or wrap sync call with `asyncio.to_thread(call_ollama, prompt)`.
**Warning signs:** Other API calls hang while WTT is processing.

### Pitfall 2: DeepSeek R1 Unclosed Think Tags
**What goes wrong:** `re.sub(r"<think>.*?</think>", ...)` with `re.DOTALL` fails when `</think>` is never emitted, leaving the entire response as "think content" and returning empty string.
**Why it happens:** DeepSeek R1 14B sometimes starts a `<think>` block but transitions to the answer without closing it, especially on long prompts.
**How to avoid:** Multi-pass regex: first handle closed tags, then handle unclosed `<think>` (remove to end), then handle orphan `</think>`.
**Warning signs:** Empty or missing JSON in parsed output despite LLM returning content.

### Pitfall 3: Duplicate Claims from Overlapping Chunks
**What goes wrong:** The 500-char overlap between CrediSentiment chunks means the same claim text may appear in two consecutive chunks, leading to duplicate extracted claims.
**Why it happens:** Section-aware chunking with overlap is designed for embedding quality, not LLM extraction.
**How to avoid:** After Stage 1, deduplicate claims by: (1) exact claim text match, (2) same category + similar claimed_value within tolerance.
**Warning signs:** Multiple identical or near-identical claims in output.

### Pitfall 4: LLM Returns Non-JSON Despite Instructions
**What goes wrong:** DeepSeek R1 adds preamble text, markdown code fences, or trailing commentary around JSON.
**Why it happens:** Instruction following is imperfect, especially with the reasoning model that "thinks" before responding.
**How to avoid:** Use the existing pattern from `credibility/service.py` -- find first `{`/`[` and last `}`/`]`, extract that substring, parse with `json.loads`. Add a fallback that returns empty results rather than crashing.
**Warning signs:** `json.JSONDecodeError` in logs.

### Pitfall 5: Timeout on Large Documents
**What goes wrong:** Documents with 20+ chunks mean 20+ sequential Ollama calls in Stage 1, each taking 30-60 seconds. Total time: 10-20 minutes.
**Why it happens:** Processing every chunk sequentially with a local 14B model is slow.
**How to avoid:** (1) Increase httpx timeout to 180s per call. (2) Consider batching 2-3 small chunks into one prompt where total length stays under ~6000 chars. (3) Accept that WTT processing is inherently slow -- this is fine for an academic project.
**Warning signs:** Frontend timeout, user refreshes page losing results.

### Pitfall 6: Enum Mismatch Between Prompt and Validation
**What goes wrong:** Prompt says one set of category names, validation code expects different names, LLM returns a third variation.
**Why it happens:** Category names defined in three places: enum, prompt template, validation code.
**How to avoid:** Generate the category list in the prompt dynamically from `ClaimCategory` enum values. Validate LLM output against the same enum. Apply case-insensitive matching and normalize underscores/spaces.

## Code Examples

### Async Walk the Talk Service (high-level flow)
```python
async def walk_the_talk_async(
    session: Session,
    claims_document_id: int,
    actuals_document_id: int,
) -> WalkTheTalkResult | None:
    """Two-stage async claim extraction and verification."""
    claims_doc = session.get(Document, claims_document_id)
    actuals_doc = session.get(Document, actuals_document_id)
    if not claims_doc or not actuals_doc:
        return None

    # Guard: both must be CS-processed
    if claims_doc.cs_status != "indexed" or actuals_doc.cs_status != "indexed":
        return None

    # Load chunks from ComparisonChunk table
    claims_chunks = get_document_chunks(session, claims_document_id)
    actuals_chunks = get_document_chunks(session, actuals_document_id)
    if not claims_chunks or not actuals_chunks:
        return None

    # Stage 1: Extract claims from each claims chunk
    all_claims = []
    for chunk_text in claims_chunks:
        prompt = STAGE1_PROMPT.format(chunk_text=chunk_text)
        raw = await call_ollama_async(prompt, max_tokens=2048)
        clean = strip_think_tags(raw)
        parsed = parse_json_array(clean)
        all_claims.extend(parsed)

    # Deduplicate claims
    unique_claims = deduplicate_claims(all_claims)

    # Stage 2: Verify claims against actuals
    actuals_text = "\n\n---\n\n".join(actuals_chunks)
    # If actuals_text is very large, may need to chunk the verification too
    prompt = STAGE2_PROMPT.format(
        claims_json=json.dumps(unique_claims, indent=2),
        actuals_text=actuals_text,
    )
    raw = await call_ollama_async(prompt, max_tokens=4096)
    clean = strip_think_tags(raw)
    result = parse_json_object(clean)

    # Save to DB (same pattern as existing code)
    ...
    return row
```

### Robust JSON Extraction
```python
def parse_json_array(text: str) -> list:
    """Extract a JSON array from LLM output, handling markdown fences and preamble."""
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return []

def parse_json_object(text: str) -> dict:
    """Extract a JSON object from LLM output."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}
```

### Claim Deduplication
```python
def deduplicate_claims(claims: list[dict]) -> list[dict]:
    """Remove duplicate claims from overlapping chunk extraction."""
    seen = set()
    unique = []
    for c in claims:
        # Key on category + normalized claim text (first 80 chars)
        key = (
            c.get("category", "").lower(),
            c.get("claim", "")[:80].lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
```

## State of the Art

| Old Approach (Current) | New Approach (Phase 6) | Impact |
|------------------------|------------------------|--------|
| Single LLM pass with both docs | Two-stage: extract then verify | Better accuracy, handles large docs |
| `text_path[:8000]` truncation | All ComparisonChunk rows | Full document coverage |
| 4 claim categories | 10 claim categories | Comprehensive coverage |
| `httpx.Client` (sync) | `httpx.AsyncClient` (async) | Non-blocking event loop |
| Simple `<think>.*?</think>` regex | Multi-pass think tag stripping | Handles malformed output |
| All docs in picker | Only `cs_status == "indexed"` | Prevents errors on unprocessed docs |

## Open Questions

1. **Stage 2 context window limits**
   - What we know: DeepSeek R1 14B has ~32K token context. Actuals documents with 10+ chunks at 3500 chars each = 35K+ chars = potentially exceeding context.
   - What's unclear: Whether all actuals chunks can fit in a single Stage 2 prompt.
   - Recommendation: Concatenate actuals chunks and if total exceeds ~20K chars, summarize or use the most relevant chunks. For v1, concatenate all and let the model handle truncation internally -- most earnings reports are shorter than con-calls.

2. **Claim deduplication quality**
   - What we know: Simple text prefix + category matching catches exact duplicates from chunk overlap.
   - What's unclear: Whether semantically similar but differently worded claims from different sections should be merged.
   - Recommendation: Start with the simple approach. Semantic dedup is a v2 optimization.

3. **Prompt tuning for DeepSeek R1 14B**
   - What we know: The STATE.md notes "DeepSeek R1 prompt templates need empirical iteration in Phase 6."
   - What's unclear: Exact prompt phrasing that produces reliable JSON from DeepSeek R1 14B.
   - Recommendation: Start with the prompt templates above. The robust JSON parsing handles imperfect output. Prompt refinement happens during implementation testing.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed) |
| Config file | None (implicit, uses tests/ directory) |
| Quick run command | `python -m pytest tests/test_wtt_backend.py -x -v` |
| Full suite command | `python -m pytest tests/ -x -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WTT-01 | API accepts two doc IDs, returns comparison | unit | `python -m pytest tests/test_wtt_backend.py::test_walk_the_talk_accepts_two_docs -x` | No - Wave 0 |
| WTT-02 | WTT picker shows only cs_status=indexed docs | unit | `python -m pytest tests/test_wtt_backend.py::test_wtt_documents_filter -x` | No - Wave 0 |
| WTT-03 | Two-stage prompting (extract then verify) | unit | `python -m pytest tests/test_wtt_backend.py::test_two_stage_pipeline -x` | No - Wave 0 |
| WTT-04 | Full chunks used, no truncation | unit | `python -m pytest tests/test_wtt_backend.py::test_full_chunks_no_truncation -x` | No - Wave 0 |
| WTT-07 | 10 claim categories in enum | unit | `python -m pytest tests/test_wtt_backend.py::test_ten_categories -x` | No - Wave 0 |
| WTT-10 | Robust think-tag parsing | unit | `python -m pytest tests/test_wtt_backend.py::TestStripThinkTags -x` | No - Wave 0 |
| PERF-01 | Async Ollama calls | unit | `python -m pytest tests/test_wtt_backend.py::test_async_ollama -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_wtt_backend.py -x -v`
- **Per wave merge:** `python -m pytest tests/ -x -v`
- **Phase gate:** Full suite green before verify

### Wave 0 Gaps
- [ ] `tests/test_wtt_backend.py` -- covers WTT-01 through WTT-10, PERF-01
- [ ] Think-tag parsing tests with edge cases (unclosed, multiple, nested)
- [ ] Mock-based tests for async Ollama calls (no real model needed)
- [ ] Deduplication tests for overlapping chunk claims

## Sources

### Primary (HIGH confidence)
- **Project codebase** -- `finsight/credisentiment/service.py` (current walk_the_talk implementation), `finsight/rag/service.py` (call_ollama, _parse_deepseek_thinking), `finsight/credisentiment/pipeline.py` (ComparisonChunk creation), `finsight/config.py` (OLLAMA_MODEL_PRIMARY = deepseek-r1:14b)
- **httpx 0.28.1** -- Installed; `AsyncClient` API is stable and mirrors `Client` API with `async/await`
- **FastAPI 0.133.0** -- Installed; `async def` endpoints run on event loop, `def` endpoints run in threadpool

### Secondary (MEDIUM confidence)
- **DeepSeek R1 14B behavior** -- Think tag patterns based on existing `_parse_deepseek_thinking` function and common community observations of R1 output format

### Tertiary (LOW confidence)
- **Context window limits** -- DeepSeek R1 14B context window assumed ~32K tokens based on model card; actual effective limit with long financial text may be lower

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and used in codebase
- Architecture: HIGH -- two-stage pattern is well-understood; existing code provides clear refactoring target
- Pitfalls: HIGH -- all identified from examining current codebase issues and known DeepSeek R1 behaviors
- Prompt templates: MEDIUM -- templates will need empirical iteration during implementation

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- local model, no external API changes expected)
