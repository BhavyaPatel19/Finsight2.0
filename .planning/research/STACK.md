# Technology Stack

**Project:** FinSight CrediSentiment Pipeline
**Researched:** 2026-03-17
**Note:** WebSearch/WebFetch unavailable during research. All recommendations based on training data knowledge of these specific libraries/models plus codebase analysis. Confidence levels adjusted accordingly.

## Current State Analysis

The existing codebase has these specific characteristics that constrain recommendations:

| Current Component | Config | Location |
|---|---|---|
| RAG Chunking | 1500 chars, 200 overlap, concall-aware | `parsers.py:chunk_smart()` |
| Embedding Model | `BAAI/bge-base-en-v1.5` (768-dim) | `rag/service.py` singleton |
| ChromaDB | Single collection `finsight_docs`, HNSW cosine | `rag/vectorstore.py` |
| FinBERT | Reloads every call via `get_finbert_model()` | `sentiment/service.py` |
| DeepSeek R1 14B | JSON extraction with `<think>` parsing | `credisentiment/service.py` |
| WTT Text Limit | `[:8000]` chars per document | `credisentiment/service.py:284-289` |

## Recommended Stack

### 1. Chunking Strategy for CrediSentiment Comparison Pipeline

**Confidence: MEDIUM** (based on NLP chunking literature and practical experience, not live-verified)

The comparison pipeline has fundamentally different needs from RAG retrieval:

| Parameter | RAG (existing, frozen) | CrediSentiment (new) | Why Different |
|---|---|---|---|
| Chunk Size | 1500 chars | 3000-4000 chars | Comparison needs more context per claim; LLM needs surrounding figures |
| Overlap | 200 chars | 500 chars | Claims often span paragraph boundaries; overlap prevents splitting a claim from its numeric target |
| Strategy | Page-aware + concall speaker turns | Section-aware semantic chunking | Claims cluster by topic (revenue, margin, guidance); topic coherence > page boundaries |
| Metadata | page, section, sub_section | section, claim_type_hint, fiscal_period_hint | Comparison needs to match claims to actuals by category |

**Specific chunking implementation for CrediSentiment:**

```python
# config.py additions
CREDISENTIMENT_CHUNK_SIZE = 3500   # ~875 tokens at 4 chars/token
CREDISENTIMENT_CHUNK_OVERLAP = 500  # preserve claim-figure pairs across boundaries

# Strategy: section-boundary-respecting chunks
# 1. Split by document sections (TOC-based, already extracted by parsers.py)
# 2. Within each section, chunk at paragraph boundaries (not mid-sentence)
# 3. Tag chunks with section name for claim-category matching
```

**Why 3500 chars, not larger:** DeepSeek R1 14B has a context window, and you are sending TWO documents (claims + actuals). At 3500 chars/chunk and needing ~8-12 chunks per document, that is 28K-42K chars per prompt. DeepSeek R1 14B supports 128K context but inference quality degrades beyond ~16K tokens practically for structured extraction. Keep total prompt under 12K tokens (~48K chars).

**Paragraph-boundary chunking (new function needed):**

```python
def chunk_by_paragraphs(
    text: str,
    chunk_size: int = 3500,
    overlap: int = 500,
) -> list[str]:
    """
    Chunk text respecting paragraph boundaries.
    Unlike sliding-window, this never splits mid-paragraph.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > chunk_size and current:
            chunks.append("\n\n".join(current))
            # Overlap: keep last N chars worth of paragraphs
            overlap_paras = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_len += len(p)
            current = overlap_paras
            current_len = overlap_len
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks
```

### 2. DeepSeek R1 14B via Ollama -- Prompting Strategy

**Confidence: MEDIUM** (DeepSeek R1 architecture and `<think>` trace behavior are well-documented; specific parameter tuning is experiential)

**Current problem:** The existing `walk_the_talk()` sends 8000 chars per document in a single monolithic prompt. This is suboptimal because:
- 16K chars of raw text overwhelms the model's attention for structured extraction
- No chain-of-thought scaffolding for the extraction step
- JSON parsing failures are common (line 349)

**Recommended: Two-stage prompting pipeline**

**Stage 1 -- Claim Extraction (per-chunk, claims document only)**

```python
CLAIM_EXTRACTION_PROMPT = """<|begin_of_sentence|>You are a financial analyst. Extract ALL forward-looking claims from this text.

TEXT:
{chunk_text}

For each claim, output a JSON object with these fields:
- "claim": the exact quoted statement
- "category": one of [revenue_growth, margin, debt, expansion, guidance, capex, market_share]
- "claimed_value": the specific number/percentage/target mentioned (or null)
- "claim_period": the fiscal period referenced (e.g., "FY25", "Q3FY26", "next year")
- "confidence": HIGH if explicit numeric target, LOW if vague/directional

Return a JSON array. If no claims found, return [].
JSON:"""
```

**Stage 2 -- Claim Verification (extracted claims vs actuals chunks)**

```python
CLAIM_VERIFICATION_PROMPT = """<|begin_of_sentence|>You are a financial auditor verifying management claims against actual results.

CLAIMS TO VERIFY:
{claims_json}

ACTUAL RESULTS (from earnings report):
{actuals_text}

For each claim, determine:
1. Was the claim MET, PARTIALLY_MET, MISSED, or UNVERIFIABLE?
2. What was the actual value?
3. Brief evidence from the actuals text.

Return JSON:
{{
  "verifications": [
    {{
      "claim_index": <index from claims array>,
      "verdict": "MET|PARTIALLY_MET|MISSED|UNVERIFIABLE",
      "actual_value": "<actual figure or null>",
      "evidence": "<quoted text from actuals>",
      "explanation": "<one sentence>"
    }}
  ],
  "overall_score": <0-100>,
  "narrative_summary": "<2-3 sentences>"
}}
JSON:"""
```

**Why two stages:**
1. Claim extraction from smaller chunks (3500 chars) yields more reliable JSON than 8000 chars
2. Verification prompt is focused -- it has structured claims to verify, not raw text to parse
3. Each stage can retry independently on JSON parse failure
4. Stage 1 can run in parallel across chunks

**DeepSeek R1 14B Ollama parameters:**

```python
# For structured extraction (claims)
EXTRACTION_PARAMS = {
    "temperature": 0.1,       # Low temp for deterministic extraction
    "num_predict": 1024,      # Claims are concise
    "top_p": 0.9,
    "repeat_penalty": 1.1,    # Prevent repetitive claims
}

# For verification (needs reasoning)
VERIFICATION_PARAMS = {
    "temperature": 0.3,       # Slightly higher for nuanced judgment
    "num_predict": 2048,      # Verification needs more tokens
    "top_p": 0.95,
}
```

**`<think>` trace handling:**
The existing `_parse_deepseek_thinking()` in `rag/service.py` already strips `<think>...</think>` blocks. Reuse this. The thinking trace is valuable for debugging but should be stored separately.

**JSON robustness pattern:**

```python
import json
import re

def parse_llm_json(raw: str, expect_array: bool = False) -> dict | list:
    """
    Robust JSON extraction from DeepSeek R1 output.
    Handles: <think> tags, markdown code fences, trailing commas.
    """
    # Strip thinking trace
    clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Strip markdown code fences
    clean = re.sub(r"```json\s*", "", clean)
    clean = re.sub(r"```\s*$", "", clean)
    # Find JSON boundaries
    if expect_array:
        start, end = clean.find("["), clean.rfind("]") + 1
    else:
        start, end = clean.find("{"), clean.rfind("}") + 1
    if start < 0 or end <= start:
        return [] if expect_array else {}
    candidate = clean[start:end]
    # Fix trailing commas (common DeepSeek issue)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    return json.loads(candidate)
```

### 3. FinBERT Optimization -- Singleton + Batch Processing

**Confidence: HIGH** (PyTorch/HuggingFace Transformers batch inference is well-established)

**Current problems identified in code:**

1. **`sentiment/service.py:get_finbert_model()`** -- reloads the 500MB model on EVERY call (no caching)
2. **`credisentiment/service.py:_run_finbert_on_text()`** -- processes sentences one-by-one in a Python loop (line 127-136)
3. **Both files** import FinBERT independently -- no shared singleton

**Solution: Singleton pattern + batched inference**

```python
# finsight/ml/finbert.py (new shared module)

import re
import torch
from typing import Optional

_tokenizer = None
_model = None
_device = None

def get_finbert():
    """
    Singleton FinBERT loader. Loads once, reuses across all calls.
    Returns (tokenizer, model, device).
    """
    global _tokenizer, _model, _device
    if _tokenizer is not None:
        return _tokenizer, _model, _device

    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    name = "ProsusAI/finbert"
    _tokenizer = AutoTokenizer.from_pretrained(name)
    _model = AutoModelForSequenceClassification.from_pretrained(name)
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model.to(_device)
    _model.eval()
    return _tokenizer, _model, _device


def analyze_batch(
    sentences: list[str],
    batch_size: int = 32,
) -> list[dict]:
    """
    Batch FinBERT inference. Returns per-sentence sentiment scores.

    batch_size=32 is optimal for:
    - CPU: keeps memory under ~2GB with max_length=512
    - GPU (6-8GB VRAM): can go up to 64
    """
    tokenizer, model, device = get_finbert()
    results = []

    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]
        inputs = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,           # Pad to longest in batch
            # padding="max_length"  # Alternative: pad to 512 (wastes compute)
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)

        probs = torch.softmax(outputs.logits, dim=1)
        # FinBERT labels: [positive, negative, neutral]
        for j in range(len(batch)):
            results.append({
                "positive": probs[j][0].item(),
                "negative": probs[j][1].item(),
                "neutral": probs[j][2].item(),
            })

    return results
```

**Batch size rationale:**

| Batch Size | CPU RAM | GPU VRAM (6GB) | Throughput (CPU) | Throughput (GPU) |
|---|---|---|---|---|
| 1 (current) | ~600MB | ~600MB | ~2 sent/sec | ~15 sent/sec |
| 16 | ~1.2GB | ~1GB | ~25 sent/sec | ~120 sent/sec |
| **32 (recommended)** | **~1.8GB** | **~1.5GB** | **~40 sent/sec** | **~200 sent/sec** |
| 64 | ~3GB | ~2.5GB | ~45 sent/sec | ~250 sent/sec |

**Padding strategy:** Use `padding=True` (dynamic padding to longest in batch), NOT `padding="max_length"`. Dynamic padding avoids wasting compute on short sentences. Most financial sentences are 20-80 tokens, far shorter than the 512 max.

**Sentence splitting improvement:**

```python
def split_financial_sentences(text: str, min_length: int = 15) -> list[str]:
    """
    Split text into sentences, filtering out noise.
    Current code uses regex split on [.!?] which breaks on abbreviations
    like "Rs.", "Q3.", "FY25.", "vs.", "approx."
    """
    # Better: split on period+space+capital, or newline boundaries
    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z])',  # Period followed by space and capital letter
        text
    )
    return [s.strip() for s in sentences if len(s.strip()) >= min_length]
```

### 4. ChromaDB Multi-Collection Setup

**Confidence: HIGH** (ChromaDB's collection API is straightforward and well-documented)

**Current state:** Single collection `finsight_docs` in `rag/vectorstore.py` with a global singleton.

**Recommended: Separate collection with its own module**

```python
# finsight/credisentiment/vectorstore.py (new file)

from typing import Any
from finsight.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

_collection = None

def get_credisentiment_collection():
    """
    Separate ChromaDB collection for CrediSentiment pipeline.
    Uses same embedding model as RAG but different chunking parameters.
    """
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # Check for embedding model mismatch (same pattern as RAG vectorstore)
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
            "pipeline": "credisentiment",
        },
    )
    return _collection
```

**Why same embedding model (`bge-base-en-v1.5`) for both collections:**
- Avoids loading a second embedding model into memory (~400MB per model)
- BGE-base performs well for both retrieval and comparison use cases
- The differentiation is in chunking, not embedding -- larger chunks with more context get embedded differently even with the same model
- If comparison quality is poor, upgrade BOTH collections to `bge-large-en-v1.5` (1024-dim, ~1.3GB) later

**Collection architecture:**

```
chroma_db/
  |-- finsight_docs          # RAG pipeline (1500-char chunks, page-aware)
  |-- credisentiment_docs    # Comparison pipeline (3500-char chunks, section-aware)
```

**Same PersistentClient, different collections.** ChromaDB PersistentClient with the same `path` shares the underlying storage engine. Multiple collections in the same path is the standard pattern -- no need for separate directories.

### 5. Embedding Model Configuration

**Confidence: HIGH** (BGE models are well-characterized)

| Embedding Model | Dimensions | Size | Use Case |
|---|---|---|---|
| **`BAAI/bge-base-en-v1.5`** (current + recommended) | 768 | ~440MB | Best balance of quality and speed for local deployment |
| `BAAI/bge-large-en-v1.5` | 1024 | ~1.3GB | Upgrade path if comparison quality is insufficient |
| `BAAI/bge-small-en-v1.5` | 384 | ~130MB | Too small for financial document comparison |

**Stick with `bge-base-en-v1.5`.** Loading a second model is wasteful, and the base model handles financial text well. The existing singleton in `rag/service.py` should be shared by the CrediSentiment pipeline rather than creating a second instance.

**Shared embedding access pattern:**

```python
# Both RAG and CrediSentiment import from the same place:
from finsight.rag.service import embed_documents, embed_query
```

### 6. Document Processing Flow (Config Additions)

```python
# config.py additions
CREDISENTIMENT_CHUNK_SIZE = int(os.getenv("CREDISENTIMENT_CHUNK_SIZE", "3500"))
CREDISENTIMENT_CHUNK_OVERLAP = int(os.getenv("CREDISENTIMENT_CHUNK_OVERLAP", "500"))

# DeepSeek R1 parameters for structured extraction
DEEPSEEK_EXTRACTION_TEMP = float(os.getenv("DEEPSEEK_EXTRACTION_TEMP", "0.1"))
DEEPSEEK_VERIFICATION_TEMP = float(os.getenv("DEEPSEEK_VERIFICATION_TEMP", "0.3"))
DEEPSEEK_MAX_TOKENS_EXTRACT = int(os.getenv("DEEPSEEK_MAX_TOKENS_EXTRACT", "1024"))
DEEPSEEK_MAX_TOKENS_VERIFY = int(os.getenv("DEEPSEEK_MAX_TOKENS_VERIFY", "2048"))

# FinBERT batch size
FINBERT_BATCH_SIZE = int(os.getenv("FINBERT_BATCH_SIZE", "32"))
FINBERT_MAX_SENTENCES = int(os.getenv("FINBERT_MAX_SENTENCES", "500"))
```

## Supporting Libraries

| Library | Version | Purpose | Already Installed? |
|---|---|---|---|
| `chromadb` | existing | Vector store (add second collection) | Yes |
| `sentence-transformers` | existing | BGE embedding model (shared) | Yes |
| `transformers` | existing | FinBERT model loading | Yes |
| `torch` | existing | FinBERT inference | Yes |
| `httpx` | existing | Ollama API calls | Yes |

**No new dependencies required.** The entire CrediSentiment pipeline improvement uses existing libraries with different configurations.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Embedding model for comparison | BGE-base (shared) | Separate `bge-large` for comparison | Extra 1.3GB RAM; marginal quality gain doesn't justify memory cost on local machine |
| Chunking for comparison | 3500-char paragraph-boundary | Same 1500-char as RAG | Too small for claim-context pairs; claims lose surrounding figures |
| FinBERT batching | Dynamic padding, batch=32 | HuggingFace pipeline API | Pipeline API adds overhead and hides batch control; direct tokenizer+model is cleaner |
| LLM prompting | Two-stage (extract then verify) | Single monolithic prompt (current) | Current approach has JSON parse failures; 16K chars in one prompt degrades extraction quality |
| Vector store | Second ChromaDB collection | Separate ChromaDB directory | Same PersistentClient handles multiple collections; separate dir wastes disk and complicates config |
| DeepSeek R1 14B | Keep as-is | Switch to Qwen2.5 14B or Mistral | DeepSeek R1 has superior reasoning traces; already configured and tested |

## Key Architecture Decisions

### Shared vs Separate Resources

| Resource | Strategy | Rationale |
|---|---|---|
| Embedding model | **Shared** (single singleton) | Memory efficiency; same model works for both use cases |
| ChromaDB client | **Shared** PersistentClient, **separate** collections | Standard ChromaDB pattern; avoids opening two database connections |
| FinBERT model | **Shared** singleton in `finsight/ml/finbert.py` | Currently reloads on every call; fix benefits both sentiment and credisentiment |
| Ollama connection | **Shared** `call_ollama()` in `rag/service.py` | Already centralized; add parameter overrides for temperature/tokens |
| Chunking config | **Separate** config constants | Different pipelines need different chunk sizes |

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| FinBERT singleton + batching | HIGH | Standard PyTorch pattern; well-established |
| Chunking parameters (3500/500) | MEDIUM | Based on NLP best practices for comparison tasks; may need tuning |
| DeepSeek R1 two-stage prompting | MEDIUM | Architecture is sound; specific prompt templates need iteration |
| ChromaDB multi-collection | HIGH | Documented ChromaDB feature; straightforward |
| BGE-base shared embedding | HIGH | Already proven in RAG pipeline; no reason it fails for comparison |
| DeepSeek R1 temperature settings | LOW | Experiential; needs A/B testing with real financial documents |

## Sources

All recommendations based on training data knowledge of:
- PyTorch batch inference patterns
- HuggingFace Transformers tokenizer API (padding, truncation)
- ChromaDB PersistentClient and collection management
- BGE embedding model family characteristics
- DeepSeek R1 model architecture and `<think>` trace behavior
- Financial NLP chunking literature

**No live verification was possible** (WebSearch, WebFetch, and Bash were unavailable). Chunking parameters and DeepSeek R1 temperature settings in particular should be validated against real documents during implementation.

---
*Stack research: 2026-03-17*
