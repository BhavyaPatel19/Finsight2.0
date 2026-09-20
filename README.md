# FinSight

**Grounded question-answering and claim verification over company filings — rebuilt around measurement.**

FinSight ingests earnings-call transcripts, press releases, fact sheets and annual reports (PDF or HTML), answers questions with page-level citations, and checks whether management *walked the talk*: it extracts forward-looking commitments from one quarter's call and grades them **MET / MISSED / PARTIAL / UNVERIFIABLE** against the next period's filings, with the evidence quote for every verdict. A React dashboard wraps it with market data, watchlists and FinBERT sentiment by division.

[![CI](https://github.com/BhavyaPatel19/Finsight2.0/actions/workflows/ci.yml/badge.svg?branch=experiment%2Faccuracy-redesign)](https://github.com/BhavyaPatel19/Finsight2.0/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)

> **Branches.** `main` is the original project as built. This branch, `experiment/accuracy-redesign`, is a from-scratch rebuild of the accuracy-critical core — ingestion, retrieval, verification — driven by an audit of every process ([docs/PIPELINE_AUDIT.md](docs/PIPELINE_AUDIT.md)) and measured at every step ([eval/results/HISTORY.md](eval/results/HISTORY.md)).

---

## In numbers

Eight public Infosys filings (SEC EDGAR 6-K exhibits: four earnings-call transcripts, two press releases, two fact sheets, Q4 FY25 → Q1 FY27), **rendered to real multi-page PDFs** because PDF is the product's primary input. 64 gold questions with verbatim evidence quotes; a retrieved chunk counts only if it contains the quote.

| retrieval, PDF corpus | hit@1 | hit@5 | MRR@8 | evidence within first 6k chars |
|---|---|---|---|---|
| original pipeline | 0.688 | 0.875 | 0.771 | 0.859 |
| **redesign (v2)** | **0.781** | **1.000** | **0.879** | **1.000** |

Same on the HTML originals: hit@5 0.859 → 0.984. Chunk coverage — the share of questions whose evidence exists in *any* chunk — went from 96.9% to 100%, because the original chunker silently dropped 11–35% of the text of several documents.

End-to-end answers (correctness vs human reference, faithfulness, abstention) and Walk-the-Talk agreement with 15 human-labelled claims: original pipeline **87.5% correct / faithfulness 0.947** and **κ 0.10** respectively (local `qwen3:14b`); the v2 runs are in progress and will replace this line.

---

## What the audit found

Reading every process end to end, on the PDFs the product actually ingests ([full audit](docs/PIPELINE_AUDIT.md)):

- **Transcript PDFs were never recognised as transcripts** — the speaker regex needed a colon that PDF text does not have — so they were cut into fixed 1,500-character windows mid-sentence. Fact sheets *were* misdetected as transcripts by the same regex and lost 18–35% of their text to a chunker that discarded everything before the first "speaker" on each page.
- **Tables were read as one cell per line.** `find_tables()` was never called; rows lost their headers; two gold facts did not survive extraction at all.
- **Three indexing routes for one document.** The Documents page's *Process* button ran a 512-character window chunker with no page numbers, and the Chat page then trusted its output.
- **The reranker was matching headers, not content**: `bge-reranker-base` scored an irrelevant paragraph 0.69–0.75 as long as it carried the document header, and the correct fact-sheet row 0.001 without one.
- **Claim verification retrieved "actuals" per *category*** with a dense-only search over one document; four of five wrong verdicts said "the actuals do not mention…" while the fact sat in the sibling press release or fact sheet.
- Ollama's default 2k context truncated the 4k-token RAG prompt from the front; `WTT_PARALLEL=4` deadlocked a single-slot local model into returning zero claims; `passlib` broke registration on fresh installs.

---

## Architecture (v2)

```mermaid
flowchart LR
  subgraph corpus [finsight/corpus — ingestion]
    A[PDF / HTML] --> B[typed elements<br/>paragraph · speaker turn · heading · table row with header]
    B --> C[lossless chunker<br/>sentence-bounded prose, one-sentence overlap<br/>row chunks + grouped tables]
  end
  subgraph retrieval [finsight/retrieval]
    C --> D[(chunks · sentences<br/>ChromaDB + number-aware BM25)]
    Q[question] --> E[dense + BM25 over sentences → parents<br/>+ table channel]
    D --> E
    E --> F[RRF × period prior]
    F --> G[bge-reranker-v2-m3<br/>on verbalised index text]
    G --> H[strict grounded prompt · Groq / Ollama]
  end
  subgraph verification [finsight/verification — Walk the Talk]
    C --> I[forward-looking sentences]
    I --> J[typed claims<br/>metric · period · target range · verbatim quote]
    J --> K[per-claim evidence<br/>all filings of the actuals period]
    K --> L[verdict + evidence quote<br/>numeric targets computed · UNVERIFIABLE allowed]
  end
```

Two texts per chunk: the **verbatim** source (what citations quote, what the user sees) and an **index text** carrying `company · document type · period · section · speaker`, with table rows verbalised as `title — label: column = value; …`. The embedder, BM25 and the reranker all see the same enriched text.

---

## Quickstart

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+. Optional: Ollama (local models), Chrome (to render the sample PDFs).

```bash
git clone -b experiment/accuracy-redesign https://github.com/BhavyaPatel19/Finsight2.0.git && cd Finsight2.0
make install                              # uv sync + npm ci

cp .env.example .env
#   SECRET_KEY=$(openssl rand -hex 32)                       required
#   GROQ_API_KEY=gsk_...                                     recommended (free at console.groq.com); else Ollama is used
#   EDGAR_USER_AGENT="FinSight research you@example.com"     only to download the sample corpus (SEC policy)

uv run python -m scripts.seed_demo --engine v2   # download 8 public Infosys filings from SEC EDGAR and index them
make dev                                          # API on http://127.0.0.1:8000 (Swagger at /docs)
cd frontend && npm run dev                        # UI on http://localhost:5173
```

Register a user, open **Chat**, select the seeded documents and ask *"What FY26 guidance did Infosys give in April 2025, and what did it deliver?"*. Open **CrediSentiment → Walk the Talk**, pick the Q4 FY25 call as claims and the Q4 FY26 call as actuals.

**Fully local:** install [Ollama](https://ollama.ai), `ollama pull qwen3:14b` (or any chat model), leave `GROQ_API_KEY` unset. The first run downloads `bge-base-en-v1.5` (embeddings) and `bge-reranker-v2-m3` (~2 GB); reranking costs ~1 s per query on Apple silicon.

---

## Evaluation

```bash
uv run python -m scripts.render_pdfs                                  # HTML exhibits → real PDFs (headless Chrome)
FINSIGHT_CORPUS=pdf uv run python -m scripts.seed_demo --format pdf --engine v2
FINSIGHT_CORPUS=pdf uv run python -m eval.retrieval --modes v2 v2_notables v2_noperiod   # hit@k, MRR, nDCG, evidence-within-6k-chars
FINSIGHT_CORPUS=pdf uv run python -m eval.generation                  # correctness / faithfulness (LLM judge) + deterministic checks
FINSIGHT_CORPUS=pdf uv run python -m eval.wtt --engine v2             # claim recall, verdict agreement, κ vs 15 human labels
```

`FINSIGHT_CORPUS=pdf` keeps the PDF corpus in its own database and vector store so the HTML and PDF paths can be compared side by side; `--engine v1` runs the original pipeline on the same gold set. The gold set is regenerated by an authoring script that **fails if any evidence quote is missing from the source text**. Methodology, definitions and what is not measured: [docs/EVALUATION.md](docs/EVALUATION.md). Every change that moved a number, with the number: [eval/results/HISTORY.md](eval/results/HISTORY.md).

---

## Design principles of the rebuild

1. **Lossless by construction.** Parsing produces typed elements; chunking is a total function over them with a tested invariant — every element's text is in some chunk.
2. **Structure is context.** Table rows carry title and header; transcript chunks carry the speaker and the analyst question they answer; every chunk carries company, document type and period.
3. **Retrieve small, return big.** Sentences are indexed for precision and mapped back to their parent chunk; a dedicated table channel guarantees numeric questions get row candidates into fusion.
4. **Numbers are checked, not trusted.** A verdict on a numeric target (a range, "above 100%") is computed from the extracted actual; the LLM extracts, code decides.
5. **Abstain explicitly.** RAG answers "Not found in the selected documents."; verification returns `UNVERIFIABLE`, and any MET/MISSED/PARTIAL must cite a quote that is verifiably in the retrieved text or it is downgraded.
6. **Every change is a row in the history file.** Nothing lands without a before/after on the same gold set.

---

## Configuration

| variable | default | purpose |
|---|---|---|
| `SECRET_KEY` | — (required) | JWT signing; startup fails without it |
| `LLM_PROVIDER` · `GROQ_API_KEY` · `GROQ_MODEL` | `auto` · — · `llama-3.3-70b-versatile` | hosted inference |
| `OLLAMA_BASE_URL` · `OLLAMA_MODEL` · `OLLAMA_NUM_CTX` · `OLLAMA_TIMEOUT_S` | `http://localhost:11434` · `llama3.1:8b` · `8192` · `300` | local inference |
| `WTT_MODEL` | provider default | model for claim extraction / verification |
| `EMBEDDING_MODEL` · `RERANKER_MODEL` | `BAAI/bge-base-en-v1.5` · `BAAI/bge-reranker-v2-m3` | retrieval models |
| `MARKET_DATA_PROVIDER` · `ZERODHA_*` | `auto` · — | yfinance by default; Zerodha Kite if configured and linked |
| `FINSIGHT_CORPUS` | — | `pdf` → separate DB/vector store for the PDF eval corpus |
| `EDGAR_USER_AGENT` | — | required by SEC to download the sample corpus |
| `ALLOWED_ORIGINS` · `DATABASE_URL` · `CHROMA_PERSIST_DIR` | dev server · SQLite file · `./chroma_db` | infrastructure |

---

## Repository map

```
finsight/corpus/        ingestion v2: elements.py · parse_pdf.py · parse_html.py · structure.py (transcript gate) · chunker.py
finsight/retrieval/     index.py (chunks + sentences) · search.py (fusion, table channel, rerank) · periods.py · text.py
finsight/verification/  claims.py · evidence.py · verdict.py · pipeline.py · sentiment.py
finsight/rag/           answer_question (grounded prompt), legacy v1 index kept for the eval comparison
finsight/llm/           provider layer (Groq, Ollama)
finsight/market/        providers (yfinance, Zerodha) · fundamentals · news
finsight/{auth,ingestion,credisentiment,watchlist,portfolio,zerodha}/   app modules
eval/                   gold sets · retrieval / generation / wtt harnesses · judge · results + HISTORY.md
scripts/                seed_demo.py (download + index) · render_pdfs.py
docs/                   PIPELINE_AUDIT.md · REDESIGN.md · EVALUATION.md
tests/                  177 tests; models and LLMs stubbed, runs in ~11 s
```

---

## Limitations

- The corpus is one company, four quarters, filings rendered from HTML. Real scanned or multi-column annual reports will stress the PDF parser in ways this corpus does not; the eval is built so that adding them is a manifest entry plus questions.
- Walk-the-Talk labels: 15 claims, one labeller. κ is reported but too small to lean on until the set is larger and a second labeller has graded it.
- The judge in the generation eval is a local 14B model; a hosted 70B run with a different judge is the planned cross-check.
- Reranking with v2-m3 costs ~1 s/query; latency work (candidate pruning, batching) is not done.
- Documents are per-user; the app is otherwise single-tenant in practice. Answers are not streamed.

---

## Data and licence

Sample corpus: Form 6-K exhibits filed with the U.S. SEC by Infosys Ltd, downloaded from EDGAR at seed time (SHA-256 pinned in `eval/gold/documents.json`, not redistributed). NIFTY 500 constituent list from NSE Indices. Prices via Yahoo Finance (delayed) or the user's own Zerodha account.

Code is MIT licensed — see [LICENSE](LICENSE).
