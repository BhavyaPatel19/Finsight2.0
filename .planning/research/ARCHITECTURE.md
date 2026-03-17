# Architecture Patterns

**Domain:** Dual-pipeline document analysis (RAG + CrediSentiment comparison)
**Researched:** 2026-03-17
**Overall confidence:** HIGH (based on existing codebase analysis, no external research needed -- this is an internal architecture decision)

## Current State Analysis

The existing system has a single document processing pipeline (RAG) that extracts text, chunks with page-aware/concall-aware strategies, embeds with BGE-base-en-v1.5, and stores in ChromaDB collection `finsight_docs`. The CrediSentiment service currently piggybacks on RAG processing -- it calls `process_for_rag()` internally when a document is not yet indexed. This tight coupling is the core problem to solve.

### What Exists Today

```
Document Upload (ingestion/)
        |
        v
  process_for_rag (rag/service.py)
        |
        +---> extract_structured_document (PyMuPDF)
        +---> chunk_smart (1500 chars, 200 overlap, concall-aware)
        +---> embed with BGE-base-en-v1.5
        +---> ChromaDB "finsight_docs" collection
        +---> DocumentChunk rows in SQLite
        +---> PageMetadata + DocumentSection rows
        |
        v
  CrediSentiment (credisentiment/service.py)
        |
        +---> FinBERT: reads PageMetadata/DocumentSection from RAG indexing
        +---> WTT: reads raw text_path files, truncates to 8000 chars
```

**Problems with current design:**
1. WTT truncates to 8000 chars -- loses most of the document content
2. No dedicated chunking for comparison -- just raw text truncation
3. FinBERT depends on RAG being run first (auto-triggers it)
4. Single `status` field on Document -- cannot track RAG vs CrediSentiment processing independently
5. No separate ChromaDB collection for comparison retrieval

---

## Recommended Architecture

### Pipeline Separation Strategy

Use **separate processing status fields** on the Document model and a **separate ChromaDB collection** for the CrediSentiment pipeline. Both pipelines share the same Document row and the same extracted text file, but diverge at the chunking stage.

```
                    Document Upload
                         |
                    PDF Extraction
                    (shared: PyMuPDF)
                         |
                    text_path on disk
                    (shared: raw .txt)
                         |
            +------------+------------+
            |                         |
     "Process for RAG"        "Process for CrediSentiment"
     (Documents tab btn)       (Documents tab btn)
            |                         |
            v                         v
   chunk_smart()              chunk_for_comparison()
   1500 chars, 200 overlap    Larger chunks: ~3000 chars
   concall-aware speaker      Section-boundary aware
   turns                      Preserves full claims/context
            |                         |
            v                         v
   BGE-base-en-v1.5           BGE-base-en-v1.5
   embed_documents()          embed_documents() (same model)
            |                         |
            v                         v
   ChromaDB                   ChromaDB
   "finsight_docs"            "finsight_comparison"
   (existing collection)      (new collection)
            |                         |
            v                         v
   DocumentChunk rows         ComparisonChunk rows (new table)
   (existing table)           (separate from RAG chunks)
            |                         |
            v                         v
   RAG Q&A pipeline           CrediSentiment pipeline
   (Chat tab)                 (CrediSentiment tab)
```

### Why This Design

1. **Same embedding model, different chunking.** RAG needs small chunks (1500 chars) for precise retrieval. Comparison needs larger chunks (~3000 chars) to preserve complete claims with surrounding context. Using the same BGE model means no additional model loading overhead.

2. **Separate ChromaDB collections, not separate databases.** ChromaDB PersistentClient can hold multiple collections in the same directory. No new infrastructure. Collections are isolated -- deleting/rebuilding one does not affect the other.

3. **Separate chunk tables.** `DocumentChunk` stays for RAG. New `ComparisonChunk` table stores chunks with comparison-specific metadata (claim density score, section type). Avoids polluting the RAG pipeline's data.

4. **Shared text extraction.** Both pipelines use the same `text_path` file. No redundant PDF parsing. The extraction step (PyMuPDF structured extraction) only runs once.

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `ingestion/` | PDF upload, text extraction, file management | Shared by both pipelines |
| `rag/service.py` | RAG chunking, embedding, ChromaDB `finsight_docs`, hybrid retrieval, LLM Q&A | `rag/vectorstore.py` (existing) |
| `rag/vectorstore.py` | ChromaDB `finsight_docs` collection CRUD | ChromaDB |
| `credisentiment/vectorstore.py` | **NEW** -- ChromaDB `finsight_comparison` collection CRUD | ChromaDB |
| `credisentiment/pipeline.py` | **NEW** -- Comparison-specific chunking, embedding, processing | `credisentiment/vectorstore.py`, `ingestion/parsers.py` |
| `credisentiment/service.py` | FinBERT division sentiment, Walk the Talk comparison logic | `credisentiment/pipeline.py`, `rag/service.py` (for `call_ollama` only) |
| `credisentiment/router.py` | API endpoints for CrediSentiment features | `credisentiment/service.py` |
| `models/document.py` | Document model with dual status tracking | All services |
| `models/comparison_chunk.py` | **NEW** -- ComparisonChunk model | `credisentiment/pipeline.py` |
| Frontend `CredibilitySentiment.jsx` | Sub-tabbed UI with persistent state | `credisentimentApi` in `client.js` |
| Frontend `Documents.jsx` | Processing controls with dual pipeline buttons | `ragApi`, `credisentimentApi` |

---

## Data Flow: Walking the Talk (Full Pipeline)

### Step 1: Document Upload (Already Exists)
```
User uploads PDF via Documents tab
  --> POST /documents/upload (or /credisentiment/upload)
  --> Save PDF to documents/ directory
  --> Create Document row: status="pending", cs_status="pending"
```

### Step 2: Process for CrediSentiment (New)
```
User clicks "Process for CrediSentiment" on Documents tab
  --> POST /credisentiment/process/{document_id}
  --> pipeline.py: process_for_comparison(session, document_id)
      |
      1. Read text_path (if exists) or extract from PDF
      2. extract_structured_document() for section boundaries
      3. chunk_for_comparison(pages, chunk_size=3000, overlap=300)
         - Larger chunks to preserve claim context
         - Section-boundary respecting (don't split mid-section)
         - Tag each chunk: page_number, section, sub_section
      4. embed_documents(texts) using same BGE model
      5. Store in ChromaDB "finsight_comparison" collection
      6. Save ComparisonChunk rows in SQLite
      7. Update Document: cs_status="indexed", cs_chunk_count=N
```

### Step 3: Select Documents for Comparison
```
User navigates to CrediSentiment tab > Walking the Talk sub-tab
  --> GET /credisentiment/available-documents?cs_status=indexed
      (only shows documents processed for CrediSentiment)
  --> User selects Claims doc (older concall) and Actuals doc (newer earnings)
```

### Step 4: Compare and Analyze
```
User clicks "Compare & Analyze"
  --> POST /credisentiment/walk-the-talk
      {claims_document_id, actuals_document_id}
      |
      1. Retrieve ALL ComparisonChunks for claims doc (ordered by chunk_index)
      2. Retrieve ALL ComparisonChunks for actuals doc (ordered by chunk_index)
      3. Build structured prompt with full document content:
         - Claims text: concatenate all comparison chunks (up to ~24000 chars)
         - Actuals text: concatenate all comparison chunks (up to ~24000 chars)
         - FinBERT sentiment context (if available)
      4. Call DeepSeek R1 14B via Ollama:
         - Model: deepseek-r1:14b
         - Context window: ~32K tokens (enough for both docs)
         - max_tokens: 4096 (structured JSON output)
         - Timeout: 300 seconds (large context = slow)
      5. Parse response:
         - Strip <think>...</think> reasoning trace
         - Extract JSON: {overall_score, claims[], narrative_summary}
      6. Save WalkTheTalkResult row
      7. Return structured response to frontend
```

### Step 5: Display Results
```
Frontend receives WalkTheTalkResponse:
  - ScoreDial: overall credibility score (0-100)
  - AI Assessment: narrative summary
  - Claim cards: claim, claimed_value, actual_value, met/missed/unclear, explanation
  - Category badges: revenue_growth, margin, debt, expansion, guidance
```

---

## Data Flow: FinBERT Sentiment (Adjusted)

FinBERT continues to use RAG-processed documents (the section/page structure from RAG indexing is what it needs for division-level breakdown). No separate pipeline needed.

```
User selects documents in CrediSentiment tab > FinBERT sub-tab
  --> Documents must have status="indexed" (RAG processed)
  --> POST /credisentiment/analyze-sentiment {document_ids: [...]}
      |
      1. For each document:
         a. Read PageMetadata + DocumentSection from RAG indexing
         b. Group text by top-level sections (divisions)
         c. Run FinBERT sentence-by-sentence per division
         d. Save DivisionSentiment rows
      2. Return division-level scores
```

**Key point:** FinBERT reads from RAG-processed data (PageMetadata, DocumentSection). It does NOT need CrediSentiment processing. The document picker for FinBERT should filter by `status="indexed"` (RAG status).

---

## Database Schema Changes

### Document Model (Modified)

```python
class Document(SQLModel, table=True):
    # ... existing fields ...

    # Existing RAG status (unchanged)
    status: str = Field(default="pending")  # pending|processing|indexed|error
    chunk_count: int = Field(default=0)

    # NEW: CrediSentiment pipeline status
    cs_status: str = Field(default="pending")  # pending|processing|indexed|error
    cs_chunk_count: int = Field(default=0)
    cs_error_message: str | None = None
```

### ComparisonChunk Model (New)

```python
class ComparisonChunk(SQLModel, table=True):
    __tablename__ = "comparison_chunks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    chunk_index: int = Field(default=0)
    text: str
    page_number: int | None = None
    section: str | None = None
    sub_section: str | None = None
    chroma_id: str | None = None  # ID in "finsight_comparison" collection
```

### ChromaDB Collections

```
chroma_db/
  finsight_docs/        <-- existing RAG collection (FROZEN, do not modify)
  finsight_comparison/  <-- NEW comparison collection
```

Both collections use the same embedding model (BGE-base-en-v1.5) and cosine similarity. The comparison collection uses a different naming scheme for IDs: `comp_{document_id}_chunk_{chunk_index}`.

---

## New Module: credisentiment/vectorstore.py

```python
"""
ChromaDB collection for CrediSentiment comparison pipeline.
Separate from RAG's finsight_docs collection.
"""

_collection = None

def get_comparison_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from finsight.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    _collection = client.get_or_create_collection(
        name="finsight_comparison",
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": EMBEDDING_MODEL,
        },
    )
    return _collection

def add_comparison_chunks(ids, texts, metadatas, embeddings):
    coll = get_comparison_collection()
    coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

def get_chunks_by_document_id(document_id):
    coll = get_comparison_collection()
    results = coll.get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    # Return sorted by chunk_index
    items = []
    for i, doc_id in enumerate(results["ids"]):
        items.append({
            "id": doc_id,
            "text": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    items.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
    return items

def delete_comparison_by_document_id(document_id):
    coll = get_comparison_collection()
    results = coll.get(where={"document_id": document_id}, include=[])
    ids = results.get("ids", [])
    if ids:
        coll.delete(ids=ids)
    return len(ids)
```

---

## New Module: credisentiment/pipeline.py

```python
"""
CrediSentiment document processing pipeline.
Separate chunking/embedding from RAG -- optimized for claim comparison.
"""

def chunk_for_comparison(pages, chunk_size=3000, overlap=300):
    """
    Larger chunks than RAG to preserve complete claims with context.
    Respects section boundaries -- prefers to break at section changes.
    """
    chunks = []
    chunk_idx = 0
    buffer = ""
    buffer_page = pages[0]["page"] if pages else 1
    buffer_section = pages[0].get("section") if pages else None
    buffer_sub = pages[0].get("sub_section") if pages else None

    for page in pages:
        text = page.get("text", "").strip()
        if not text:
            continue

        current_section = page.get("section")

        # Section boundary: flush buffer if switching sections and buffer is non-trivial
        if current_section != buffer_section and len(buffer) > chunk_size * 0.3:
            if buffer.strip():
                chunks.append({
                    "text": buffer.strip(),
                    "page_number": buffer_page,
                    "section": buffer_section,
                    "sub_section": buffer_sub,
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1
            buffer = ""
            buffer_page = page["page"]
            buffer_section = current_section
            buffer_sub = page.get("sub_section")

        buffer += "\n\n" + text

        # Size-based flush
        if len(buffer) >= chunk_size:
            chunks.append({
                "text": buffer.strip(),
                "page_number": buffer_page,
                "section": buffer_section or current_section,
                "sub_section": buffer_sub,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1
            # Overlap: keep last N chars
            buffer = buffer[-overlap:] if overlap else ""
            buffer_page = page["page"]
            buffer_section = current_section
            buffer_sub = page.get("sub_section")

    # Flush remaining
    if buffer.strip():
        chunks.append({
            "text": buffer.strip(),
            "page_number": buffer_page,
            "section": buffer_section,
            "sub_section": buffer_sub,
            "chunk_index": chunk_idx,
        })

    return chunks


def process_for_comparison(session, document_id):
    """
    Process a document for the CrediSentiment comparison pipeline.
    Separate from RAG processing -- uses larger chunks, separate ChromaDB collection.
    """
    from finsight.models import Document
    from finsight.models.comparison_chunk import ComparisonChunk
    from finsight.ingestion.parsers import extract_structured_document
    from finsight.rag.service import embed_documents
    from finsight.credisentiment.vectorstore import (
        add_comparison_chunks,
        delete_comparison_by_document_id,
    )
    from sqlmodel import select
    from pathlib import Path

    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        return {"status": "error", "message": "Document or PDF not found"}

    if doc.cs_status == "indexed":
        return {"status": "already_indexed", "document_id": document_id}

    doc.cs_status = "processing"
    session.add(doc)
    session.commit()

    try:
        # Extract structure (may already exist from RAG processing)
        structured = extract_structured_document(doc.pdf_path)
        pages = structured["pages"]

        if not pages:
            doc.cs_status = "error"
            doc.cs_error_message = "No text extracted from PDF"
            session.add(doc)
            session.commit()
            return {"status": "error", "message": "No text extracted"}

        # Save text_path if not already done by RAG
        if not doc.text_path:
            full_text = "\n\n".join(p["text"] for p in pages if p["text"])
            text_path = Path(doc.pdf_path).with_suffix(".txt")
            text_path.write_text(full_text, encoding="utf-8")
            doc.text_path = str(text_path)

        # Comparison-specific chunking (larger chunks)
        chunks = chunk_for_comparison(pages, chunk_size=3000, overlap=300)

        # Delete old comparison chunks
        old = session.exec(
            select(ComparisonChunk).where(ComparisonChunk.document_id == document_id)
        ).all()
        for o in old:
            session.delete(o)
        delete_comparison_by_document_id(document_id)

        # Save new ComparisonChunk rows
        for chunk in chunks:
            cc = ComparisonChunk(
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                page_number=chunk.get("page_number"),
                section=chunk.get("section"),
                sub_section=chunk.get("sub_section"),
            )
            session.add(cc)
        session.commit()

        # Embed and store in comparison collection
        texts = [c["text"] for c in chunks]
        embeddings = embed_documents(texts)
        ids = [f"comp_{document_id}_chunk_{c['chunk_index']}" for c in chunks]
        metadatas = [{
            "document_id": document_id,
            "chunk_index": c["chunk_index"],
            "page_number": c.get("page_number", 0),
            "section": c.get("section") or "",
            "sub_section": c.get("sub_section") or "",
            "symbol": doc.symbol or "",
            "doc_type": doc.doc_type or "",
        } for c in chunks]
        add_comparison_chunks(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)

        doc.cs_status = "indexed"
        doc.cs_chunk_count = len(chunks)
        doc.cs_error_message = None
        session.add(doc)
        session.commit()

        return {
            "status": "indexed",
            "document_id": document_id,
            "chunks": len(chunks),
        }

    except Exception as e:
        doc.cs_status = "error"
        doc.cs_error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return {"status": "error", "message": str(e)[:500]}
```

---

## Frontend Architecture: Sub-Tabs with Persistent State

### Problem
The current `CredibilitySentiment.jsx` uses conditional rendering (`{tab === 'sentiment' && ...}`) which destroys component state when switching tabs. Sentiment results and WTT results vanish when the user switches between sub-tabs.

### Solution: CSS Display Toggle (Not Conditional Rendering)

Render BOTH tab panels always; hide the inactive one with `display: none`. This preserves all state (results, selections, scroll position) across tab switches with zero React complexity.

```jsx
// CURRENT (breaks state):
{tab === 'sentiment' && <SentimentPanel />}
{tab === 'wtt' && <WTTPanel />}

// RECOMMENDED (preserves state):
<div style={{ display: tab === 'sentiment' ? 'block' : 'none' }}>
    <SentimentPanel />
</div>
<div style={{ display: tab === 'wtt' ? 'block' : 'none' }}>
    <WTTPanel />
</div>
```

**Why not useRef/state persistence?** Overkill for this use case. The CSS approach is simpler, has zero serialization cost, preserves scroll position and focus state, and requires no refactoring of the existing component structure.

**Why not React Context or Zustand?** The state is page-local (only used within CredibilitySentiment). No other page needs access to sentiment results or WTT results. Adding a state management library for one page is unnecessary complexity.

### Frontend Component Structure

```
CredibilitySentiment.jsx (page component)
  |
  +-- State (all at page level, shared across sub-tabs):
  |     documents[], selectedIds, sentimentResults[],
  |     claimsDocId, actualsDocId, wttResult,
  |     loading flags, error messages
  |
  +-- Left Panel: Document Picker (shared across sub-tabs)
  |     - Checkbox list of documents
  |     - Status badges showing BOTH rag status and cs_status
  |     - Upload zone (existing)
  |
  +-- Right Panel: Tab Bar + Content
        |
        +-- Tab Bar: [FinBERT Sentiment] [Walking the Talk]
        |
        +-- Tab Content (BOTH rendered, one hidden via display:none):
              |
              +-- SentimentPanel (display when tab=sentiment):
              |     - "Analyze Selected" button
              |     - Division bar charts + table per document
              |     - Filters by status="indexed" (RAG-processed docs only)
              |
              +-- WTTPanel (display when tab=wtt):
                    - Claims doc dropdown (cs_status="indexed" only)
                    - Actuals doc dropdown (cs_status="indexed" only)
                    - "Compare & Analyze" button
                    - ScoreDial + AI Assessment + Claim cards
```

### Document Picker Filtering

The document picker must filter differently per sub-tab:

```jsx
// FinBERT sub-tab: show RAG-processed documents
const sentimentDocs = documents.filter(d => d.status === 'indexed')

// WTT sub-tab: show CrediSentiment-processed documents
const comparisonDocs = documents.filter(d => d.cs_status === 'indexed')
```

The left panel document list shows ALL documents with dual status badges. The dropdowns/checkboxes within each sub-tab filter appropriately.

---

## Documents Tab: Dual Processing Controls

The Documents page needs new processing buttons for each document:

```
[Document Card]
  INFY - Annual Report FY25
  Status: RAG: indexed (45 chunks) | CS: pending

  [Process for RAG]  [Process for CrediSentiment]
```

### API Endpoints

```
POST /rag/prepare       {document_id}   --> existing, sets status field
POST /credisentiment/process  {document_id}   --> NEW, sets cs_status field
```

### Status Display

Each document card shows two status indicators:
- RAG status: pending/processing/indexed/error (existing)
- CS status: pending/processing/indexed/error (new)

Color-coded badges:
- Gray (pending) / Blue (processing) / Green (indexed) / Red (error)

---

## Patterns to Follow

### Pattern 1: Service Function Isolation
**What:** Each pipeline's processing function is self-contained. `process_for_rag` and `process_for_comparison` do not call each other.
**When:** Always -- pipeline independence is critical.
**Why:** Modifying one pipeline's parameters should never affect the other. The RAG pipeline is explicitly frozen.

### Pattern 2: Shared Infrastructure, Separate Data Stores
**What:** Both pipelines use the same embedding model instance (singleton), same ChromaDB PersistentClient, same SQLite database. But data is stored in separate collections and tables.
**When:** When two pipelines need the same tools but different tuning.
**Why:** Minimizes memory usage (one BGE model in RAM) while preventing data contamination.

### Pattern 3: Ollama Call Reuse
**What:** `call_ollama()` in `rag/service.py` is a utility function used by both RAG Q&A and WTT comparison. Import it, don't duplicate it.
**When:** Any LLM call from any module.
**Why:** Single timeout config, single error handling pattern, single httpx client setup.

### Pattern 4: Model Singleton
**What:** FinBERT and BGE models are loaded once and cached in module-level globals.
**When:** Any ML model that takes >1 second to load.
**Why:** FinBERT is ~500MB, BGE is ~400MB. Reloading per-request is unacceptable.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Auto-triggering Cross-Pipeline Processing
**What:** The current code auto-triggers `process_for_rag()` inside CrediSentiment when a document is not indexed.
**Why bad:** Creates hidden coupling. User doesn't know RAG processing is happening. Processing takes time and may fail, blocking the CrediSentiment operation.
**Instead:** Require documents to be explicitly processed for each pipeline from the Documents tab. Show clear status indicators. CrediSentiment endpoints should return a 400 error with a message like "Document not processed for CrediSentiment. Process it from the Documents tab."

### Anti-Pattern 2: Raw Text Truncation for Comparison
**What:** The current WTT code reads `text_path` and truncates to 8000 chars.
**Why bad:** Loses 80%+ of document content. Claims near the end of a concall are missed entirely.
**Instead:** Use the full ComparisonChunk data (all chunks concatenated). With DeepSeek R1 14B's ~32K token context window, both documents can fit with ~24K chars each.

### Anti-Pattern 3: Shared Status Field for Dual Pipelines
**What:** Using a single `status` field and overloading its meaning.
**Why bad:** Cannot independently track RAG vs CrediSentiment processing. A document might be RAG-indexed but not comparison-indexed, or vice versa.
**Instead:** Separate fields: `status` (RAG) and `cs_status` (CrediSentiment).

### Anti-Pattern 4: Conditional Rendering for Tab Content
**What:** Using `{tab === 'x' && <Component />}` to show/hide tab panels.
**Why bad:** Destroys component state, including analysis results that took minutes to compute. User switches tabs and loses their WTT results.
**Instead:** Render both panels; toggle visibility with `display: none/block`.

---

## Scalability Considerations

| Concern | Current (10 docs) | At 100 docs | At 500 docs |
|---------|-------------------|-------------|-------------|
| ChromaDB size | Negligible | ~50MB per collection | ~250MB per collection, still fine |
| Processing time | 5-15s per doc | Same per doc, no batch concern | Consider async processing with progress |
| LLM context (WTT) | 2 docs fit in 32K | Same -- always 2 docs | Same -- always 2 docs |
| SQLite queries | Instant | Instant | Add index on cs_status if slow |
| Document picker UI | Scrollable list fine | Scrollable list fine | Add search/filter by symbol |
| FinBERT per doc | 30-60s | Same per doc | Consider batching, progress bar |

The system is inherently document-pair scoped (WTT compares exactly 2 documents at a time), so it does not face scaling concerns from document volume on the analysis side. The main scaling concern is the document picker UX when hundreds of documents exist.

---

## DeepSeek R1 14B Integration Notes

**Context window:** ~32K tokens (~24K usable after system prompt and output reservation)
**Output format:** JSON with `<think>...</think>` reasoning traces that must be stripped
**Timeout:** Set to 300 seconds (5 minutes) for large context comparisons
**Model name in Ollama:** `deepseek-r1:14b`

The existing `call_ollama()` function handles DeepSeek R1 already. The WTT prompt should be updated to:
1. Use `model="deepseek-r1:14b"` explicitly (not rely on OLLAMA_MODEL_PRIMARY which may change)
2. Increase `max_tokens` from 2048 to 4096 for the structured comparison output
3. Increase timeout from 120s to 300s for larger context

```python
raw = call_ollama(
    prompt,
    model="deepseek-r1:14b",
    max_tokens=4096,
)
```

The `call_ollama` function currently has a hardcoded 120s timeout. This should be made configurable per call:

```python
def call_ollama(prompt, model=None, max_tokens=2048, timeout=120.0):
    # ... existing code but with configurable timeout
```

---

## Sources

- Existing codebase analysis (HIGH confidence -- direct code inspection)
- ChromaDB documentation: multiple collections in single PersistentClient is standard usage
- DeepSeek R1 14B: ~32K context window confirmed from Ollama model registry
- BGE-base-en-v1.5: same model works for both pipelines, no dimension mismatch risk
