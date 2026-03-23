# Phase 4: Document Processing UI - Research

**Researched:** 2026-03-17
**Domain:** React frontend UI -- document processing controls, status indicators, API integration
**Confidence:** HIGH

## Summary

Phase 4 is a frontend-only phase that adds dual processing buttons ("Process for RAG" and "Process for CrediSentiment") to each document row on the Documents tab, with four-state status indicators (unprocessed/processing/processed/error) and spinners during active processing. It also removes all document processing controls from the CrediSentiment tab (the upload zone and document list's processing-related UI).

The backend infrastructure is already complete: the Document model has both `status` (RAG) and `cs_status` (CrediSentiment) fields. RAG processing uses `POST /api/ingestion/documents/{id}/process` and CrediSentiment processing uses `POST /api/credisentiment/process/{id}`. Both endpoints transition status from pending -> processing -> indexed/error. The frontend work is entirely about wiring these existing endpoints into the Documents.jsx table and cleaning up processing controls from CredibilitySentiment.jsx.

The current Documents.jsx already has a single "Process" button (Play icon) that only appears for `status === 'pending'` docs and calls `ingestionApi.process()`. This needs to be replaced with two always-visible status-aware buttons. The CredibilitySentiment.jsx has an upload zone and document picker that contain processing controls -- these must be removed per PROC-08.

**Primary recommendation:** Extend the existing Documents.jsx table with two inline processing buttons per row, each with independent status badges. Use polling (2-second interval) during active processing to update status. Remove the upload/processing UI from CredibilitySentiment.jsx entirely.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-04 | Documents tab shows "Process for RAG" button per document with visual status indicator | Existing `ingestionApi.process()` API + `status` field on Document model. Button replaces current Play icon. |
| PROC-05 | Documents tab shows "Process for CrediSentiment" button per document with visual status indicator | Existing `credisentimentApi` needs new `process()` method calling `POST /api/credisentiment/process/{id}`. Uses `cs_status` field. |
| PROC-06 | Processing status indicators show distinct states: unprocessed / processing / processed / error | Extend existing `STATUS_CONFIG` object in Documents.jsx with dual-status badge component. Map `pending` -> unprocessed, `processing` -> processing, `indexed` -> processed, `error` -> error. |
| PROC-07 | Processing progress indicator (spinner/percentage) visible during active processing | Use existing `.spinner` CSS class already used throughout the app. Poll document status at 2s intervals while any doc is in `processing` state. |
| PROC-08 | Processing controls removed from RAG tab and CrediSentiment tab | Remove upload zone, upload state, and upload handler from CredibilitySentiment.jsx. Chat.jsx "Prepare Selected" button is a RAG query preparation step (not document processing) -- it stays. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 18.3.1 | Component framework | Already in use |
| Lucide React | 0.395.0 | Icon library | Already in use -- Play, CheckCircle, AlertCircle, Loader icons available |
| Axios | 1.7.2 | HTTP client | Already in use via `api/client.js` |

### Supporting
No new libraries needed. All UI patterns use existing project infrastructure (inline styles, Lucide icons, `.spinner` CSS class).

### Alternatives Considered
None. This is purely wiring existing backend APIs to existing frontend patterns.

## Architecture Patterns

### Current Document Table Structure
```
Documents.jsx
  -> docs state (array from ingestionApi.list)
  -> Each row: Company | Type | Period | Status | Date | Size | Actions
  -> Actions column: View PDF | Chat | Process (Play) | Delete
```

### Target Document Table Structure
```
Documents.jsx
  -> docs state (array from ingestionApi.list -- needs cs_status, cs_chunk_count in response)
  -> Each row: Company | Type | Period | RAG Status | CS Status | Date | Actions
  -> Actions column: View PDF | Chat | Process RAG | Process CS | Delete
```

### Pattern 1: Dual Status Badges
**What:** Two independent status badges per document row, one for RAG (`status`) and one for CrediSentiment (`cs_status`).
**When to use:** Every document row in the table.
**Example:**
```jsx
// Reusable status badge with four states
const PIPELINE_STATUS = {
  pending:    { label: 'Unprocessed', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', icon: null },
  processing: { label: 'Processing', color: '#38bdf8', bg: 'rgba(56,189,248,0.12)', spin: true },
  indexed:    { label: 'Processed',  color: '#22d3a5', bg: 'rgba(34,211,165,0.12)', icon: CheckCircle },
  error:      { label: 'Error',      color: '#f43f5e', bg: 'rgba(244,63,94,0.12)', icon: AlertCircle },
}

function PipelineStatusBadge({ status, label }) {
  const cfg = PIPELINE_STATUS[status] || PIPELINE_STATUS.pending
  return (
    <span style={{ /* badge styles */ }}>
      {cfg.spin && <span className="spinner" />}
      {cfg.icon && <cfg.icon size={12} />}
      {label}: {cfg.label}
    </span>
  )
}
```

### Pattern 2: Processing Button with Status Awareness
**What:** A button that shows different states: "Process" when unprocessed, disabled spinner when processing, check when processed, retry on error.
**When to use:** Each pipeline column in the actions area.
**Example:**
```jsx
function ProcessButton({ status, onClick, label }) {
  if (status === 'processing') {
    return <button disabled className="btn btn-ghost btn-sm">
      <span className="spinner" style={{ width: 14, height: 14 }} />
    </button>
  }
  if (status === 'indexed') {
    return <button disabled className="btn btn-ghost btn-sm" title={`${label}: Processed`}>
      <CheckCircle size={14} style={{ color: 'var(--success)' }} />
    </button>
  }
  // pending or error -- allow (re-)processing
  return <button className="btn btn-ghost btn-sm" onClick={onClick} title={`Process for ${label}`}>
    <Play size={14} style={{ color: status === 'error' ? 'var(--danger)' : undefined }} />
  </button>
}
```

### Pattern 3: Polling During Processing
**What:** When a user triggers processing, poll the document list at 2-second intervals until no documents are in `processing` state.
**When to use:** After calling process endpoint for either pipeline.
**Example:**
```jsx
const [polling, setPolling] = useState(false)
const pollRef = useRef(null)

const startPolling = () => {
  if (pollRef.current) return
  setPolling(true)
  pollRef.current = setInterval(async () => {
    const r = await ingestionApi.list(filterSymbol || undefined)
    setDocs(r.data)
    const anyProcessing = r.data.some(d =>
      d.status === 'processing' || d.cs_status === 'processing'
    )
    if (!anyProcessing) {
      clearInterval(pollRef.current)
      pollRef.current = null
      setPolling(false)
    }
  }, 2000)
}
```

### Anti-Patterns to Avoid
- **Optimistic status update without polling:** Do not just set local state to "processing" and forget. The backend processing takes seconds to minutes. Must poll for completion.
- **Blocking the entire table during one document's processing:** Each document processes independently. Other documents remain interactive.
- **Adding a new page or modal for processing:** Processing buttons belong inline in the document row. No modal needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Spinner animation | Custom CSS spinner | Existing `.spinner` class | Already styled consistently across the app |
| Status badge styles | New color system | Existing `STATUS_CONFIG` pattern | Already defined in Documents.jsx, just needs expansion |
| API client methods | Raw axios calls | `ingestionApi` and `credisentimentApi` objects | Centralized in `api/client.js` with auth interceptor |

## Common Pitfalls

### Pitfall 1: Backend list endpoint not returning cs_status
**What goes wrong:** The `ingestionApi.list()` endpoint returns document data, but the frontend needs both `status` and `cs_status` fields. If the backend `list_documents` function only serializes some fields, `cs_status` may be missing.
**Why it happens:** The Document SQLModel has `cs_status` but the API response may not include it if the serialization is limited.
**How to avoid:** Verify that `GET /api/ingestion/documents` response includes `cs_status`, `cs_chunk_count`, and `cs_error_message` fields. SQLModel should auto-serialize all fields, but verify.
**Warning signs:** `doc.cs_status` is `undefined` in the frontend.

### Pitfall 2: Race condition when polling stops
**What goes wrong:** User triggers RAG processing, polling starts. While polling, user triggers CS processing on another doc. Polling sees no RAG processing docs and stops, missing the CS processing.
**Why it happens:** Polling checks `anyProcessing` across both pipelines, but timing matters.
**How to avoid:** Check BOTH `status === 'processing'` and `cs_status === 'processing'` in the polling condition. Start polling fresh on each process trigger.
**Warning signs:** Status gets stuck on "processing" visually but polling has stopped.

### Pitfall 3: Removing wrong controls from CredibilitySentiment.jsx
**What goes wrong:** PROC-08 says remove "processing controls" from CrediSentiment tab. But the document *picker* (for selecting which docs to analyze) must stay -- only the upload zone and processing triggers are removed.
**Why it happens:** Confusing "document selection for analysis" with "document processing".
**How to avoid:** Remove: (1) upload state/handlers/UI, (2) the `credisentimentApi.upload()` call. Keep: (1) document picker for selecting docs to analyze, (2) "Analyze Selected" button (that's analysis, not processing).
**Warning signs:** Users can no longer select documents for FinBERT analysis.

### Pitfall 4: Chat.jsx "Prepare Selected" misidentified as processing control
**What goes wrong:** PROC-08 could be misinterpreted to include Chat.jsx's "Prepare Selected" button, which calls `ragApi.prepare()`.
**Why it happens:** "Prepare" sounds like "process", but it is actually a RAG query preparation step that loads already-indexed documents into the query context.
**How to avoid:** Leave Chat.jsx completely untouched. The "Prepare Selected" button is not a document processing control -- it is a query setup step.
**Warning signs:** Chat page loses its prepare functionality.

### Pitfall 5: CrediSentiment process API not in client.js
**What goes wrong:** The `credisentimentApi` object in `api/client.js` does not have a `process()` method. The backend endpoint exists at `POST /api/credisentiment/process/{id}`, but no frontend method calls it.
**Why it happens:** The endpoint was added in Phase 3 but the API client was not updated.
**How to avoid:** Add `process: (documentId) => client.post(`/credisentiment/process/${documentId}`)` to `credisentimentApi` in `api/client.js`.
**Warning signs:** "Process for CrediSentiment" button has no API method to call.

## Code Examples

### Adding credisentimentApi.process() to client.js
```javascript
// In api/client.js, add to credisentimentApi object:
process: (documentId) =>
  client.post(`/credisentiment/process/${documentId}`),
```

### Modified Document Table Row (Documents.jsx)
```jsx
<tr key={doc.id}>
  <td>/* Company / Symbol - unchanged */</td>
  <td>/* Type - unchanged */</td>
  <td>/* Period - unchanged */</td>
  <td>
    <PipelineStatusBadge status={doc.status || 'pending'} label="RAG" />
  </td>
  <td>
    <PipelineStatusBadge status={doc.cs_status || 'pending'} label="CS" />
  </td>
  <td>/* Date - unchanged */</td>
  <td>/* Size - unchanged */</td>
  <td>
    <div className="flex gap-1" style={{ justifyContent: 'flex-end' }}>
      {/* View PDF button - unchanged */}
      {/* Chat button - unchanged */}
      <ProcessButton
        status={doc.status}
        onClick={() => handleProcessRAG(doc.id)}
        label="RAG"
      />
      <ProcessButton
        status={doc.cs_status}
        onClick={() => handleProcessCS(doc.id)}
        label="CrediSentiment"
      />
      {/* Delete button - unchanged */}
    </div>
  </td>
</tr>
```

### Processing Handlers
```javascript
const handleProcessRAG = async (docId) => {
  try {
    await ingestionApi.process(docId)
    startPolling()
  } catch { /* show error toast or inline */ }
}

const handleProcessCS = async (docId) => {
  try {
    await credisentimentApi.process(docId)
    startPolling()
  } catch { /* show error toast or inline */ }
}
```

### Items to Remove from CredibilitySentiment.jsx
```
REMOVE:
- Lines 116-123: Upload state variables (showUpload, uploadFile, uploadSymbol, etc.)
- Lines 123: fileRef
- Lines 187-204: handleUpload function
- Lines 236-239: Upload button in document panel header
- Lines 244-292: Entire upload zone conditional block
- Import: credisentimentApi.upload (no longer called)

KEEP:
- Document list/picker (for selecting docs for analysis)
- "Analyze Selected" button (triggers analysis, not processing)
- WTT document selectors (for selecting claims/actuals docs)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `status` field on Document | Dual `status` + `cs_status` fields | Phase 1/3 (already done) | Backend ready for dual processing UI |
| Processing controls scattered across tabs | Centralized on Documents tab | This phase (Phase 4) | Single entry point for all processing |
| Single "Process" button (RAG only) | Two pipeline-specific buttons | This phase (Phase 4) | Users can independently process for each pipeline |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) / no frontend test framework configured |
| Config file | `tests/conftest.py` exists |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROC-04 | RAG process button per document row | manual | Visual inspection of Documents tab | N/A (frontend) |
| PROC-05 | CS process button per document row | manual | Visual inspection of Documents tab | N/A (frontend) |
| PROC-06 | Four distinct status states displayed | manual | Visual inspection -- check each state | N/A (frontend) |
| PROC-07 | Spinner visible during processing | manual | Trigger processing, observe spinner | N/A (frontend) |
| PROC-08 | Processing controls removed from other tabs | manual | Navigate to CrediSentiment tab, verify no upload/process controls | N/A (frontend) |

### Sampling Rate
- **Per task commit:** Visual inspection of Documents tab and CrediSentiment tab
- **Per wave merge:** Full manual walkthrough: upload doc -> process for RAG -> process for CS -> verify statuses -> check CrediSentiment tab has no processing controls
- **Phase gate:** All five requirements manually verified

### Wave 0 Gaps
- No frontend test framework (Vitest/Jest) is configured -- all verification is manual
- Backend API integration can be verified with existing pytest if needed, but the phase is frontend-only

## Open Questions

1. **Backend document list response shape**
   - What we know: Document SQLModel has `cs_status`, `cs_chunk_count`, `cs_error_message` fields
   - What's unclear: Whether `list_documents()` in `ingestion/service.py` returns all fields or a subset
   - Recommendation: Check the function. SQLModel with `table=True` should auto-include all columns. If not, add them to the response.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `frontend/src/pages/Documents.jsx` (691 lines)
- Direct codebase analysis of `frontend/src/pages/CredibilitySentiment.jsx` (683 lines)
- Direct codebase analysis of `frontend/src/api/client.js` (151 lines)
- Direct codebase analysis of `finsight/models/document.py` (Document model with dual status fields)
- Direct codebase analysis of `finsight/credisentiment/router.py` (process endpoint at POST /credisentiment/process/{id})
- Direct codebase analysis of `finsight/ingestion/router.py` (process endpoint at POST /ingestion/documents/{id}/process)
- Direct codebase analysis of `finsight/ingestion/file_manager.py` (process_document function)
- Direct codebase analysis of `finsight/credisentiment/pipeline.py` (process_for_credisentiment function)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries, all existing project infrastructure
- Architecture: HIGH - Straightforward table modification and API wiring
- Pitfalls: HIGH - All identified from direct code inspection of existing components

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable -- frontend patterns, no external dependencies)
