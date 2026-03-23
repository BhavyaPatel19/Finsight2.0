# Phase 3: CrediSentiment Processing Pipeline - Research

**Researched:** 2026-03-17
**Domain:** Document chunking, ChromaDB multi-collection, FastAPI processing endpoint
**Confidence:** HIGH

## Summary

Phase 3 builds the CrediSentiment-specific document processing pipeline: section-aware chunking with 3500-char/500-overlap parameters, a separate ChromaDB collection (`credisentiment_docs`), and a processing endpoint that operates independently from RAG. The existing codebase already has most of the infrastructure in place from Phase 1 (expected): the `Document` model has `cs_status`/`cs_chunk_count`/`cs_error_message` fields, the `ComparisonChunk` table exists, and config constants `CREDISENTIMENT_CHUNK_SIZE` (3500) and `CREDISENTIMENT_CHUNK_OVERLAP` (500) are defined in `config.py`.

The work is primarily: (1) create `credisentiment/vectorstore.py` for the separate ChromaDB collection, (2) create `credisentiment/pipeline.py` with section-aware chunking and the `process_for_credisentiment()` orchestrator, and (3) add a `POST /credisentiment/process/{document_id}` endpoint in the router. The shared embedding model singleton from `rag/service.py` is reused -- no new model loading needed.

**Primary recommendation:** Follow the "shared infrastructure, separate data" pattern established in prior research. Mirror the `process_for_rag()` function's structure but use larger chunks, the `ComparisonChunk` table, and the `credisentiment_docs` ChromaDB collection. Never call `process_for_rag()` from the CrediSentiment pipeline.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-02 | CrediSentiment pipeline uses separate chunking parameters (3500 chars / 500 overlap, section-aware) from RAG pipeline (1500/200) | Config constants already exist. Section-aware chunking function needed in `pipeline.py`. See Architecture Patterns for implementation. |
| PROC-03 | CrediSentiment embeddings stored in a separate ChromaDB collection (`credisentiment_docs`) | New `credisentiment/vectorstore.py` module. Same PersistentClient, separate collection. See Standard Stack for ChromaDB multi-collection pattern. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chromadb | existing | Second collection `credisentiment_docs` in same PersistentClient | Already installed; multi-collection is a native ChromaDB pattern |
| sentence-transformers | existing | BGE-base-en-v1.5 shared embedding singleton | Already loaded for RAG; reuse avoids 440MB additional memory |
| sqlmodel | existing | ComparisonChunk CRUD operations | Already used throughout the codebase |
| PyMuPDF (fitz) | existing | Structured text extraction with TOC/sections | Already used in `parsers.py:extract_structured_document()` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | existing | Processing endpoint | Route handler for `POST /credisentiment/process/{document_id}` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom section-aware chunking | LangChain RecursiveCharacterTextSplitter | LangChain is overkill; adds a dependency for one function. Custom is ~50 lines. |
| Same `finsight_docs` collection with metadata filter | Separate `credisentiment_docs` collection | Metadata filter would work but risks cross-contamination and complicates cleanup. Separate collection is cleaner. |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure

```
finsight/
  credisentiment/
    __init__.py          # existing
    router.py            # existing - add process endpoint
    schemas.py           # existing - add process response schema
    service.py           # existing - no changes in this phase
    vectorstore.py       # NEW - credisentiment_docs ChromaDB collection
    pipeline.py          # NEW - section-aware chunking + process orchestrator
```

### Pattern 1: Section-Aware Chunking

**What:** Chunk documents at section boundaries (from PyMuPDF TOC), using 3500-char target size with 500-char overlap. When a section boundary is encountered and the buffer has accumulated at least 30% of target size, flush the buffer as a chunk.

**When to use:** Always for CrediSentiment processing. This preserves complete claims with their surrounding context (figures, targets, timelines).

**Example:**
```python
# Source: adapted from .planning/research/ARCHITECTURE.md pipeline.py reference
from finsight.config import CREDISENTIMENT_CHUNK_SIZE, CREDISENTIMENT_CHUNK_OVERLAP

def chunk_for_credisentiment(
    pages: list[dict],
    chunk_size: int = CREDISENTIMENT_CHUNK_SIZE,
    overlap: int = CREDISENTIMENT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Section-aware chunking for CrediSentiment pipeline.
    - Prefers to break at section boundaries
    - Falls back to paragraph boundaries within sections
    - Never splits mid-paragraph
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

        # Section boundary: flush if buffer is non-trivial
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
        while len(buffer) >= chunk_size:
            # Find paragraph boundary near chunk_size
            cut_point = _find_paragraph_break(buffer, chunk_size)
            chunk_text = buffer[:cut_point].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page_number": buffer_page,
                    "section": buffer_section or current_section,
                    "sub_section": buffer_sub,
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1
            # Keep overlap from end of flushed content
            buffer = buffer[cut_point - overlap:] if overlap else buffer[cut_point:]
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


def _find_paragraph_break(text: str, target: int) -> int:
    """Find nearest paragraph break (double newline) near target position."""
    # Search backward from target for a paragraph boundary
    search_start = max(0, target - 200)
    pos = text.rfind("\n\n", search_start, target + 200)
    if pos > search_start:
        return pos + 2  # include the newlines
    # Fallback: break at target
    return target
```

### Pattern 2: Separate ChromaDB Collection with Embedding Model Check

**What:** A vectorstore module that mirrors `rag/vectorstore.py` but targets the `credisentiment_docs` collection. Includes the same embedding model mismatch check.

**When to use:** All CrediSentiment embedding storage and retrieval.

**Example:**
```python
# Source: adapted from finsight/rag/vectorstore.py pattern
_collection = None

def get_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from finsight.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    existing = client.list_collections()
    if any(c.name == "credisentiment_docs" for c in existing):
        coll = client.get_collection("credisentiment_docs")
        stored_model = (coll.metadata or {}).get("embedding_model", "")
        if stored_model and stored_model != EMBEDDING_MODEL:
            client.delete_collection("credisentiment_docs")

    _collection = client.get_or_create_collection(
        name="credisentiment_docs",
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": EMBEDDING_MODEL,
        },
    )
    return _collection
```

### Pattern 3: Process Orchestrator (Mirror of process_for_rag)

**What:** `process_for_credisentiment()` follows the exact same structure as `process_for_rag()` in `rag/service.py` but uses CS-specific chunking, ComparisonChunk table, `credisentiment_docs` collection, and `cs_status`/`cs_chunk_count` fields.

**When to use:** When the user clicks "Process for CrediSentiment" on the Documents tab (Phase 4), or when called from the API endpoint.

**Key structural elements:**
1. Guard: check `cs_status == "indexed"` -> return early
2. Set `cs_status = "processing"` and commit
3. Extract structured document (reuse `extract_structured_document`)
4. Save `text_path` if not already set (may have been set by RAG)
5. Chunk with `chunk_for_credisentiment()`
6. Delete old ComparisonChunks + old ChromaDB entries
7. Save new ComparisonChunk rows
8. Embed with shared `embed_documents()` from `rag/service.py`
9. Store in `credisentiment_docs` collection
10. Set `cs_status = "indexed"`, `cs_chunk_count = len(chunks)`
11. Wrap in try/except -> set `cs_status = "error"` on failure

### Anti-Patterns to Avoid

- **Calling `process_for_rag()` from CrediSentiment pipeline:** Pipelines must be independent. CrediSentiment processing must never trigger RAG processing as a side effect.
- **Sharing chunk IDs between collections:** Use `cs_{document_id}_chunk_{chunk_index}` for CrediSentiment (not `doc_` prefix which is used by RAG).
- **Skipping the embedding model mismatch check:** If the embedding model changes (e.g., from bge-base to bge-large), stale embeddings with wrong dimensions will cause errors. Always check.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text extraction from PDF | Custom PDF parser | `extract_structured_document()` from `parsers.py` | Already handles PyMuPDF TOC, page structure, section hierarchy |
| Embedding generation | New embedding model loader | `embed_documents()` from `rag/service.py` | Shared singleton already loaded; avoids 440MB duplicate |
| ChromaDB client creation | New PersistentClient instance | Same `CHROMA_PERSIST_DIR` path | ChromaDB shares the underlying storage engine |

## Common Pitfalls

### Pitfall 1: Processing a Document That Has No PDF
**What goes wrong:** `extract_structured_document()` fails with a file-not-found error if `pdf_path` is None or the file was deleted.
**Why it happens:** Documents scraped from BSE may have `source_url` but no downloaded PDF yet.
**How to avoid:** Guard with `if not doc or not doc.pdf_path` at the top of `process_for_credisentiment()`. Return a clear error message.
**Warning signs:** `cs_status` stuck at "error" with a cryptic traceback.

### Pitfall 2: Duplicate ChromaDB Entries on Re-processing
**What goes wrong:** If a document is processed twice, old embeddings remain in the collection alongside new ones.
**Why it happens:** ChromaDB `add()` does not deduplicate by document_id; it deduplicates by vector ID.
**How to avoid:** Delete old entries by document_id before adding new ones: `delete_by_document_id()` then `add_chunks()`. The RAG pipeline already does this -- mirror the pattern.
**Warning signs:** Chunk count in ChromaDB exceeds `cs_chunk_count` on the Document model.

### Pitfall 3: text_path Race Condition Between Pipelines
**What goes wrong:** If RAG and CrediSentiment are processed concurrently for the same document, both try to write `text_path`.
**Why it happens:** Both pipelines check `if not doc.text_path` and then write the file.
**How to avoid:** The file content is deterministic (same PDF extraction), so concurrent writes produce the same result. The `text_path` field assignment is also idempotent. This is a theoretical concern, not a practical one in the current synchronous FastAPI setup.
**Warning signs:** None expected in practice.

### Pitfall 4: Section-Aware Chunking Produces One Giant Chunk for Documents Without TOC
**What goes wrong:** PDFs without a table of contents have empty `sections` list. All pages get the same `section=None`, so the section-boundary flush never triggers. The entire document becomes one chunk.
**Why it happens:** `extract_structured_document()` returns empty TOC for many financial PDFs.
**How to avoid:** The size-based flush (`while len(buffer) >= chunk_size`) handles this case -- chunks are still bounded by `chunk_size`. The section-aware logic is an optimization, not a requirement.
**Warning signs:** Very few chunks (1-3) for a long document. Monitor `cs_chunk_count`.

### Pitfall 5: ChromaDB Integer Metadata Filtering
**What goes wrong:** ChromaDB metadata values must be consistent types. If `document_id` is stored as string in some entries and int in others, `where={"document_id": 5}` misses string entries.
**Why it happens:** Python int vs str coercion in metadata dicts.
**How to avoid:** Always pass `document_id` as `int` in metadata dicts. The RAG vectorstore already does this correctly -- follow the same pattern.
**Warning signs:** `get(where={"document_id": X})` returns empty results despite data existing.

## Code Examples

### Processing Endpoint

```python
# Source: mirrors pattern from finsight/ingestion/router.py POST /documents/{id}/process
@router.post("/process/{document_id}")
def process_for_credisentiment_endpoint(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Process a document for the CrediSentiment pipeline (separate from RAG)."""
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.pdf_path:
        raise HTTPException(status_code=400, detail="Document has no PDF file")

    from finsight.credisentiment.pipeline import process_for_credisentiment
    result = process_for_credisentiment(session, document_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Processing failed"))

    return result
```

### Vectorstore CRUD Operations

```python
# Source: mirrors finsight/rag/vectorstore.py

def add_chunks(ids, texts, metadatas, embeddings):
    coll = get_collection()
    coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

def get_chunks_by_document_id(document_id: int) -> list[dict]:
    """Retrieve all CrediSentiment chunks for a document, sorted by chunk_index."""
    coll = get_collection()
    results = coll.get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    items = []
    for i, vid in enumerate(results["ids"]):
        items.append({
            "id": vid,
            "text": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    items.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
    return items

def delete_by_document_id(document_id: int) -> int:
    coll = get_collection()
    results = coll.get(where={"document_id": document_id}, include=[])
    ids = results.get("ids", [])
    if ids:
        coll.delete(ids=ids)
    return len(ids)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single ChromaDB collection for all embeddings | Multiple collections per pipeline | ChromaDB 0.4+ | Clean pipeline separation |
| Raw text truncation for LLM context | Chunked documents with section awareness | N/A (this phase) | Full document content preserved |
| Single `status` field | Dual `status`/`cs_status` fields | Phase 1 (model change) | Independent pipeline tracking |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not currently installed -- Wave 0 gap) |
| Config file | none -- see Wave 0 |
| Quick run command | `python -m pytest tests/test_credisentiment_pipeline.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROC-02 | CrediSentiment chunks use 3500-char/500-overlap with section-aware boundaries | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_chunk_size_and_overlap -x` | No -- Wave 0 |
| PROC-02 | Section boundaries trigger chunk flush | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_section_boundary_chunking -x` | No -- Wave 0 |
| PROC-03 | Embeddings stored in `credisentiment_docs` collection, not `finsight_docs` | unit | `python -m pytest tests/test_credisentiment_pipeline.py::test_separate_collection -x` | No -- Wave 0 |
| PROC-02+03 | Processing a document does not affect RAG status or chunks | integration | `python -m pytest tests/test_credisentiment_pipeline.py::test_pipeline_independence -x` | No -- Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_credisentiment_pipeline.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_credisentiment_pipeline.py` -- covers PROC-02, PROC-03
- [ ] `tests/conftest.py` -- shared fixtures (test DB session, temp ChromaDB dir)
- [ ] Framework install: `pip install pytest` -- if not already in requirements

## Open Questions

1. **Re-processing behavior**
   - What we know: The guard `if doc.cs_status == "indexed": return early` prevents re-processing.
   - What's unclear: Should there be a "force re-process" option that resets `cs_status` to "pending" first?
   - Recommendation: For Phase 3, keep the guard. Add force re-process in Phase 4 when the UI button is added (the button can call a reset endpoint first).

2. **Documents without TOC (no section boundaries)**
   - What we know: Many PDFs lack TOC metadata. The chunking falls back to size-based flushing.
   - What's unclear: Should we add heuristic section detection (ALL CAPS lines as headings)?
   - Recommendation: Skip heuristic detection for now. Size-based fallback produces valid chunks. The existing `parsers.py` heading regex could be a future enhancement.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `finsight/rag/vectorstore.py`, `finsight/rag/service.py`, `finsight/ingestion/parsers.py` -- established patterns to mirror
- `finsight/models/document.py` -- `cs_status`, `cs_chunk_count`, `cs_error_message` fields already exist
- `finsight/models/comparison_chunk.py` -- `ComparisonChunk` table already defined
- `finsight/config.py` -- `CREDISENTIMENT_CHUNK_SIZE=3500`, `CREDISENTIMENT_CHUNK_OVERLAP=500` already defined

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` -- pipeline separation design, code examples for `pipeline.py` and `vectorstore.py`
- `.planning/research/STACK.md` -- chunking parameter rationale, ChromaDB multi-collection pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies; all patterns mirrored from existing RAG pipeline code
- Architecture: HIGH - pipeline separation design is well-documented in prior research and aligns with existing codebase structure
- Pitfalls: HIGH - identified from direct codebase analysis of RAG pipeline edge cases

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable -- no external dependencies changing)
