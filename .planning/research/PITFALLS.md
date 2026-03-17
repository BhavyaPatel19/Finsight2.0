# Domain Pitfalls

**Domain:** Financial document comparison with local LLMs (FinBERT + DeepSeek R1 14B)
**Project:** FinSight CrediSentiment pipeline
**Researched:** 2026-03-17

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or unusable features.

### Pitfall 1: DeepSeek R1 Think Tags Break JSON Parsing

**What goes wrong:** DeepSeek R1 models emit `<think>...</think>` reasoning traces before the actual answer. The thinking section frequently contains partial JSON, curly braces, code snippets, and even fragments that look like the requested output format. A naive `re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)` regex fails when:
- The model emits multiple `<think>` blocks (common in longer reasoning chains)
- The model forgets to close the `</think>` tag entirely (happens ~5-15% of the time with complex prompts)
- The thinking trace contains literal `</think>` strings when reasoning about XML/HTML

**Why it happens:** The current code (line 333 of `credisentiment/service.py`) uses a single non-greedy regex that assumes exactly one well-formed think block. DeepSeek R1 does not guarantee well-formed XML in its reasoning traces.

**Consequences:** JSON parsing fails, the user gets "LLM response could not be parsed" with a raw dump. The `overall_score` defaults to 50.0 and `narrative` shows garbage. Since this is the core feature output, a 5-15% failure rate makes the feature feel unreliable.

**Prevention:**
1. Parse from the end: find the last `</think>` tag and take everything after it, rather than trying to strip think blocks
2. If no `</think>` is found, scan for the first `{` that starts valid JSON and parse from there
3. Add a fallback: if JSON parsing fails, retry the Ollama call with a simpler prompt asking only for the JSON (no reasoning)
4. Log the raw response on parse failure for debugging

**Detection:** Monitor the ratio of successful JSON parses to total WTT calls. If it drops below 85%, the prompt or parsing logic needs adjustment.

---

### Pitfall 2: DeepSeek R1 14B Context Window Overflow with Financial Documents

**What goes wrong:** The current code truncates both documents to 8,000 characters each (lines 288-290 of `credisentiment/service.py`). Combined with the prompt template (~800 chars), sentiment context (~200 chars), and the model's own think trace generation, the effective input is ~17K characters (~4-5K tokens). DeepSeek R1 14B has a 32K token context window, but effective quality degrades significantly after ~12K tokens of input on a 14B parameter model. More critically, the 8,000 character truncation cuts off the most important data -- financial claims and results are often in the middle or end of documents, not the first 8,000 characters.

**Why it happens:** Financial documents (concalls, annual reports) are 20-80 pages. Taking the first 8K characters captures the disclaimer, table of contents, and boilerplate -- not the actual claims or results.

**Consequences:** The LLM hallucinates claims that don't exist in the document, misses the actual important claims buried deeper in the text, and produces misleading credibility scores. Users who read the source document will immediately see the AI analysis doesn't match.

**Prevention:**
1. Use chunk-based extraction instead of raw truncation: query the document's indexed chunks for relevant sections (e.g., "Management Discussion", "Guidance", "Financial Results")
2. Use the existing RAG pipeline to retrieve the most relevant chunks from each document, rather than blindly truncating
3. If using raw text, implement smart truncation: skip the first ~2 pages (boilerplate), then take the most information-dense sections based on keyword density (revenue, growth, margin, target, guidance, outlook)
4. Set a token budget per document (~4K tokens each) and use tiktoken or a similar tokenizer to measure accurately rather than guessing with character counts

**Detection:** Check if extracted claims reference content that exists in the truncated text. If claims mention figures not present in the 8K truncation, the model is hallucinating from the think trace.

---

### Pitfall 3: FinBERT Model Reload on Every Call (~500MB)

**What goes wrong:** `get_finbert_model()` in `sentiment/service.py` calls `AutoTokenizer.from_pretrained()` and `AutoModelForSequenceClassification.from_pretrained()` every invocation. Each call loads ~500MB of model weights from disk (or downloads if not cached). When `credisentiment/service.py` calls `_run_finbert_on_text()` per division (5-10 divisions per document), the model is loaded 5-10 times per analysis request.

**Why it happens:** The function has no singleton pattern -- no module-level cache. The RAG service already demonstrates the correct pattern with `_embedding_model` (line 24 of `rag/service.py`).

**Consequences:** A single document analysis takes 3-10 minutes instead of 10-30 seconds. Memory spikes to multiple GB as old model instances haven't been garbage collected while new ones load. On machines with 16GB RAM running both FinBERT and DeepSeek R1, this causes OOM crashes.

**Prevention:**
```python
_finbert_tokenizer = None
_finbert_model = None

def get_finbert_model():
    global _finbert_tokenizer, _finbert_model
    if _finbert_tokenizer is None:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        _finbert_tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        _finbert_model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        _finbert_model.eval()  # Set eval mode once
    return _finbert_tokenizer, _finbert_model
```

**Detection:** If sentiment analysis takes more than 60 seconds for a single document, the model is being reloaded.

---

### Pitfall 4: Synchronous Ollama Calls Block FastAPI Event Loop

**What goes wrong:** `call_ollama()` (line 276 of `rag/service.py`) uses synchronous `httpx.Client` with a 120-second timeout. DeepSeek R1 14B inference for the WTT comparison prompt (8K+ input tokens, 2K output tokens with think traces) takes 60-180 seconds on consumer hardware. During this time, the FastAPI event loop is completely blocked -- no other HTTP requests can be served.

**Why it happens:** FastAPI async endpoints that call synchronous blocking I/O without `asyncio.to_thread()` or `run_in_executor()` block the single event loop thread. The 120-second timeout means the entire server is unresponsive for up to 2 minutes per WTT request.

**Consequences:** If a user triggers WTT analysis and then switches to another tab (RAG chat, portfolio), those requests hang until the Ollama call completes. Multiple users triggering WTT simultaneously cause cascading timeouts.

**Prevention:**
1. Wrap the Ollama call in `asyncio.to_thread()`:
   ```python
   async def call_ollama_async(prompt, model=None, max_tokens=2048):
       return await asyncio.to_thread(call_ollama, prompt, model, max_tokens)
   ```
2. Alternatively, use `httpx.AsyncClient` with streaming for the Ollama call
3. Add a task queue (even a simple `asyncio.Queue` with a background worker) for long-running LLM calls
4. Return a task ID immediately and poll for completion from the frontend

**Detection:** During a WTT analysis, try loading any other page in the app. If it hangs, the event loop is blocked.

---

### Pitfall 5: Dual Pipeline Data Integrity -- Document Processed for One Pipeline but Not the Other

**What goes wrong:** The project has two separate processing pipelines (RAG vs CrediSentiment) that share some infrastructure. A document can be "indexed" for RAG (status = "indexed") but not have FinBERT sentiment computed. The current `analyze_division_sentiment()` function (line 162 of `credisentiment/service.py`) auto-triggers `process_for_rag()` if the document isn't indexed, coupling the pipelines. But the reverse isn't true -- RAG processing doesn't trigger sentiment. This creates inconsistent states where:
- A document shows as "indexed" but has no sentiment data
- Re-running sentiment auto-triggers RAG re-indexing, corrupting the existing RAG chunks if different parameters are used
- The `status` field on the Document model is a single string shared by both pipelines

**Why it happens:** Single `status` field conflates two independent processing states. The code was originally built for one pipeline and the second was grafted on.

**Consequences:** Users see confusing status indicators. Documents appear ready but produce errors. Worse, if CrediSentiment uses different chunking parameters (as PROJECT.md specifies), auto-triggering RAG indexing from the sentiment path would overwrite the RAG-optimized chunks.

**Prevention:**
1. Add separate status fields: `rag_status` and `credisentiment_status` on the Document model
2. Never auto-trigger one pipeline from the other -- make processing explicit from the UI
3. Use separate ChromaDB collections for RAG vs CrediSentiment embeddings
4. The Documents page should show both statuses independently with separate "Process for RAG" / "Process for CrediSentiment" buttons

**Detection:** Query for documents where `status = "indexed"` but no `DivisionSentiment` rows exist, or vice versa.

---

## Moderate Pitfalls

### Pitfall 6: FinBERT Batching -- Padding Inflates Memory, Truncation Loses Context

**What goes wrong:** When converting the sentence-by-sentence loop to batched inference, two things commonly go wrong:
1. **Padding explosion:** Financial sentences vary wildly in length (10 tokens to 400+ tokens). Padding a batch to the longest sentence wastes massive amounts of memory. A batch of 32 sentences where one is 400 tokens forces all 32 to be padded to 400 tokens -- 12,800 tokens of mostly padding.
2. **Silent truncation:** FinBERT's max sequence length is 512 tokens. Financial sentences with tables, numbers, and legal disclaimers often exceed this. `truncation=True` silently drops the end of sentences, which in financial text is where the key qualifier or number often appears ("revenue grew 15% **excluding one-time items**").

**Prevention:**
1. Use dynamic padding (`padding=True` pads to the longest in the batch, not the model max) but also sort sentences by length and batch similar-length sentences together
2. Set `max_length=512` explicitly with `truncation=True` (already done in the current code, good)
3. For very long sentences, split at clause boundaries rather than hard-truncating
4. Monitor actual token counts: `inputs["input_ids"].shape` should be logged during development to understand the memory profile
5. Use batch size 16-32 for CPU, 64-128 for GPU. Start with 16 and increase until memory becomes an issue.

**Memory quantification:** FinBERT is ~500MB. A batch of 32 at max_length=512 adds ~32 x 512 x 768 x 4 bytes = ~50MB of tensor memory. On CPU with 16GB RAM this is fine. The risk is if batch_size * max_length is set too high while DeepSeek R1 is also loaded.

---

### Pitfall 7: FinBERT Label Order Assumption

**What goes wrong:** The code assumes FinBERT's output logits are ordered `[positive, negative, neutral]` (lines 132-134 of `credisentiment/service.py`). This is correct for `ProsusAI/finbert`, but:
1. If someone switches to a different sentiment model (e.g., `yiyanghkust/finbert-tone`), the label order may be different
2. The Hugging Face `config.json` for ProsusAI/finbert defines `id2label: {0: "positive", 1: "negative", 2: "neutral"}`, confirming the current order. But this is fragile -- relying on positional indexing rather than label lookup.

**Prevention:**
```python
# Safe approach: use model.config.id2label
id2label = model.config.id2label
label_scores = {id2label[i]: probs[i].item() for i in range(len(probs))}
pos = label_scores.get("positive", 0)
neg = label_scores.get("negative", 0)
neu = label_scores.get("neutral", 0)
```

---

### Pitfall 8: Ollama Memory Pressure with DeepSeek R1 14B + FinBERT + Embeddings

**What goes wrong:** DeepSeek R1 14B requires ~8-10GB of RAM (or VRAM) when loaded in Ollama. FinBERT requires ~500MB. The BGE embedding model requires ~400MB. The cross-encoder reranker requires ~275MB. Total: ~9-11GB minimum just for models. On a 16GB machine, this leaves ~5-7GB for the OS, Python process, ChromaDB, and SQLite.

**Why it happens:** Ollama keeps models loaded in memory for 5 minutes by default after the last request. If a user runs RAG (loads Llama 3 / DeepSeek), then runs FinBERT sentiment, then runs WTT (loads DeepSeek R1 14B), multiple models may be resident simultaneously.

**Consequences:** OOM kills, system freeze, or Ollama silently failing with cryptic errors like "unexpected EOF" or empty responses. On GPU, the model may partially offload to CPU, causing 10-20x slowdown.

**Prevention:**
1. Configure Ollama's `OLLAMA_KEEP_ALIVE` to a shorter duration (e.g., `1m` instead of `5m`) to free model memory faster
2. Sequence operations: don't run FinBERT while DeepSeek is processing. Use a lock or queue.
3. In the UI, disable the "Analyze Sentiment" button while WTT is running, and vice versa
4. Log available system memory before starting heavy operations. Warn the user if RAM is below 4GB free.
5. Consider using quantized models: `deepseek-r1:14b-q4_K_M` uses ~5GB instead of ~10GB with minimal quality loss for this use case

---

### Pitfall 9: Frontend State Loss on Tab Switch

**What goes wrong:** The current `CredibilitySentiment.jsx` uses conditional rendering for tabs (`{tab === 'sentiment' && (...)}` on line 369, `{tab === 'wtt' && (...)}` on line 479). When the user switches tabs, the previous tab's DOM is unmounted. Since all state is in `useState` hooks at the component level, the data itself persists -- but any in-progress analysis loading indicators, scroll positions, and expanded/collapsed sections are lost.

**More insidiously:** If a user starts a WTT analysis (60-180 seconds), switches to the Sentiment tab while waiting, the `analyzingW` state is still true but the loading UI is unmounted. When they switch back, they see the loading state correctly. However, if the component were to be unmounted entirely (e.g., navigating away and back), the state would be lost along with the in-flight request.

**Why it happens:** React's conditional rendering (`&&` pattern) mounts/unmounts components. The state lives in the parent, so it survives tab switches. But if the parent is unmounted (route change), everything is lost.

**Prevention:**
1. For tab switching: the current approach is actually fine for state preservation since state is in the parent. Use CSS `display: none` instead of conditional rendering only if scroll position preservation is needed.
2. For route-level persistence: store WTT results and sentiment results in a React context or a lightweight state manager (zustand) so they survive navigation
3. For in-flight requests: the axios call will complete but the state setter will warn about setting state on unmounted component. Use an AbortController to cancel the request on unmount, and persist results to the database (already done via `WalkTheTalkResult` model) so they can be reloaded.
4. Add a "last analysis" section that loads persisted results from the backend on component mount, so users don't need to re-run expensive analyses.

---

### Pitfall 10: DeepSeek R1 Structured Output Unreliability

**What goes wrong:** DeepSeek R1 is a reasoning model, not an instruction-following model. Its strength is chain-of-thought reasoning, not strict format compliance. When asked to output "ONLY this JSON format," it will:
1. Sometimes wrap the JSON in markdown code blocks (```json ... ```)
2. Sometimes add explanatory text after the JSON
3. Sometimes produce valid JSON with extra fields not in the schema
4. Sometimes produce JSON with `null` where strings are expected, or strings where numbers are expected
5. Sometimes emit the JSON inside the think block and only a summary after it

**Consequences:** The current `json.loads(clean[start:end])` approach (line 345) handles case 1-2 by finding the first `{` and last `}`, but fails on case 5 (the actual JSON is stripped with the think block). Cases 3-4 produce parsed results with wrong types, causing frontend rendering errors (e.g., `c.met.toFixed is not a function`).

**Prevention:**
1. After stripping think tags, if no JSON is found, also search inside the stripped think content for JSON as a fallback
2. Validate the parsed JSON against an expected schema:
   ```python
   def validate_wtt_response(parsed):
       if not isinstance(parsed.get("overall_score"), (int, float)):
           parsed["overall_score"] = 50.0
       if not isinstance(parsed.get("claims"), list):
           parsed["claims"] = []
       for claim in parsed["claims"]:
           claim["met"] = None if claim.get("met") not in (True, False) else claim["met"]
           claim["claimed_value"] = str(claim.get("claimed_value", "N/A"))
           claim["actual_value"] = str(claim.get("actual_value", "N/A"))
       return parsed
   ```
3. Use `temperature=0` in the Ollama call options to reduce output variability
4. Consider a two-pass approach: first pass for reasoning, second pass with a faster model (Llama 3 8B) to format the output as JSON

---

## Minor Pitfalls

### Pitfall 11: Sentence Splitting Regex Mishandles Financial Text

**What goes wrong:** The regex `re.split(r"[.!?]+", text)` (line 119 of `credisentiment/service.py`) splits on periods, exclamation marks, and question marks. Financial text is full of periods that don't end sentences: "Rs. 15,000 Cr.", "Q3 FY24", "Dr. Reddy's", "approx. 15%", "Rs.1,500", decimal numbers like "3.14". This creates hundreds of micro-fragments like "Rs", "15,000 Cr", "Q3 FY24" that FinBERT scores as neutral (garbage in, garbage out).

**Prevention:**
1. Use a proper sentence tokenizer: `nltk.sent_tokenize()` or `spacy` sentence segmentation
2. At minimum, improve the regex to avoid splitting on common abbreviations: `re.split(r'(?<!\b(?:Rs|Dr|Mr|Mrs|vs|approx|Ltd|Inc|Corp|No|Sr|Jr))\.\s+', text)`
3. Filter out fragments shorter than 20 characters after splitting (currently 15, which is too short)

---

### Pitfall 12: No Request Timeout Feedback in Frontend

**What goes wrong:** The WTT analysis takes 60-180 seconds. The frontend shows a spinner with "DeepSeek R1 is analyzing documents... This may take 1-3 minutes." but has no progress indicator, elapsed time counter, or way to cancel. Users click the button again, triggering a second concurrent request.

**Prevention:**
1. Disable the analyze button while loading (already done with `disabled={analyzingW}`)
2. Add an elapsed time counter: `const [elapsed, setElapsed] = useState(0)` with a `setInterval`
3. Add a cancel button that calls `AbortController.abort()` on the axios request
4. Show the Ollama streaming response in real-time instead of waiting for the full response (use `stream: true` in the Ollama API call and SSE/websockets to the frontend)

---

### Pitfall 13: Open File Handles in Service Layer

**What goes wrong:** Lines 86, 175, 288-290 of `credisentiment/service.py` use `open(doc.text_path, encoding="utf-8").read()` without a `with` block. If an exception occurs or the file path is invalid, the file descriptor leaks. Under load (many documents analyzed), this exhausts the OS file descriptor limit.

**Prevention:** Use `Path(doc.text_path).read_text(encoding="utf-8")` or `with open(...) as f: text = f.read()`.

---

### Pitfall 14: SQLite Write Contention During Concurrent Analysis

**What goes wrong:** If a user triggers FinBERT sentiment analysis on multiple documents while simultaneously running WTT (which also writes to the database), SQLite's single-writer lock causes `OperationalError: database is locked`. The current code does `session.commit()` multiple times during analysis (delete old results, insert new results), creating multiple write transactions.

**Prevention:**
1. Batch all writes into a single transaction: accumulate results in memory, then commit once at the end
2. Add `connect_args={"timeout": 30}` to the SQLAlchemy engine to increase the SQLite lock wait timeout (default is 5 seconds)
3. Use WAL mode for SQLite: `PRAGMA journal_mode=WAL` which allows concurrent reads during writes
4. Long-term: migrate to PostgreSQL (already noted in project constraints as deferred)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| FinBERT singleton refactor | Forgetting `model.eval()` after singleton init | Set eval mode in the singleton initializer, not per-call |
| FinBERT batching | OOM on large documents with GPU offload | Start with batch_size=16, test with largest expected document first |
| DeepSeek R1 integration | Think tag parsing failures on ~10% of calls | Implement robust fallback parsing before going to production |
| Document truncation rework | Losing critical financial data in truncation | Use section-based extraction, not character-based truncation |
| Dual pipeline status | Database migration breaks existing data | Add new status columns with defaults, don't rename existing `status` |
| Frontend state persistence | Race condition on unmount during in-flight request | Use AbortController, persist results via backend DB |
| Ollama async migration | Forgetting to handle the "Ollama not running" case in async | `asyncio.to_thread` still raises httpx exceptions -- wrap in try/except |
| Walking the Talk prompt | DeepSeek R1 inventing claims not in the source text | Add explicit instruction: "Only extract claims that appear verbatim or near-verbatim in the Claims Document" |
| Memory management | Multiple models loaded simultaneously | Add a model loading lock; unload FinBERT before calling DeepSeek R1 |
| ChromaDB separation | Accidentally querying the wrong collection | Use clearly distinct collection names: `finsight_rag_docs` vs `finsight_credisentiment_docs` |

---

## Sources

- Direct codebase analysis of `finsight/credisentiment/service.py`, `finsight/sentiment/service.py`, `finsight/rag/service.py`, `finsight/config.py`
- Codebase concerns audit at `.planning/codebase/CONCERNS.md`
- Project requirements at `.planning/PROJECT.md`
- Frontend component analysis of `frontend/src/pages/CredibilitySentiment.jsx`
- Training knowledge of PyTorch/Transformers batching, Ollama API behavior, DeepSeek R1 output patterns, FastAPI async patterns (MEDIUM confidence -- verify specific DeepSeek R1 behavior empirically)

**Confidence note:** DeepSeek R1 think-tag failure rates (5-15%) and context window degradation thresholds are estimates based on training data for similar-sized reasoning models. These should be validated empirically with the project's actual document corpus before finalizing prompt engineering decisions.

---

*Pitfalls research: 2026-03-17*
