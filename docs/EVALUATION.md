# Evaluation methodology

Everything measured in this repo runs against the same code path the app serves. There are three harnesses, all under `eval/`, all writing JSON + Markdown to `eval/results/`.

## Corpus and gold set

- **Corpus**: 8 public SEC EDGAR Form 6-K exhibits filed by Infosys Ltd — earnings-call transcripts, results press releases and fact sheets for Q4 FY25, Q1 FY26, Q4 FY26 and Q1 FY27 (`eval/gold/documents.json`, SHA-256 pinned, downloaded by `scripts/seed_demo.py`). Chosen because EDGAR permits programmatic access; company IR sites and BSE do not.
- **Retrieval gold** (`eval/gold/retrieval.jsonl`, 68 items): questions written from the filings with a reference answer, the document(s) that state the fact, and verbatim evidence quotes. `eval/gold/_author_retrieval.py` regenerates the file and **fails if any quote is not found in the extracted text**, so the gold set cannot drift from its sources. 64 items are answerable; 4 are deliberately unanswerable from this corpus. 20 items list evidence in more than one filing because press releases restate call headlines and fact sheets restate press numbers — listing only one source under-counted correct retrievals in the first run.
- **Walk-the-Talk gold** (`eval/gold/wtt_claims.jsonl`, 15 items): forward-looking claims from the April 2025 and July 2025 calls, each labelled MET / MISSED / PARTIAL against the April 2026 filings with an actuals quote. Labels were written by one person; treat κ as agreement with that labeller, not with a panel.

## 1. Retrieval (`python -m eval.retrieval`)

Runs four modes over the same index — `dense` (BGE-base), `bm25`, `hybrid` (RRF, k=60) and `hybrid_rerank` (bge-reranker-base; the production path) — and reports hit@1/3/5/8, MRR@8, nDCG@8, P@5 and per-stage latency.

A retrieved chunk is **relevant iff it contains a gold evidence quote** (whitespace- and quote-normalised). Page overlap is reported as a diagnostic only. **Chunk coverage** — the share of questions whose evidence exists in *some* chunk — is an upper bound and a chunking-quality signal (95.3%: three questions have evidence that spans a chunk boundary).

Cross-document questions count as a hit when any one gold document is retrieved; `cross_doc_docs_covered` reports how many of the gold documents made it into the top-k.

## 2. Generation (`python -m eval.generation`)

Runs `answer_question()` (hybrid_rerank, top-8, strict grounding prompt) on every gold question.

Deterministic, no judge:
- **number recall** — share of the reference answer's numeric tokens present in the answer (units normalised: `$4,730 million` ≡ `4730mn`). It cannot equate `$19,277 million` with `$19.3 bn`; the judge can.
- **abstention** — unanswerable questions answered with the prompt's abstain string; **false abstention** — answerable questions that abstained.
- **citations** — answers containing a `[… Page N]` citation, and whether every cited page belongs to a retrieved chunk.

Judged (`eval/judge.py`, prompts in the repo, any provider):
- **faithfulness** — the answer is decomposed into atomic claims; each is verified against the retrieved context only; score = supported / total.
- **correctness** — correct / partial / incorrect against the human reference; numbers must match to be "correct".

Caveat: when the judge is the same model as the generator (the local `qwen3:14b` run), self-preference bias is possible. Cross-check with a different judge (`--judge-model`) before quoting a single number.

## 3. Walk the Talk (`python -m eval.wtt`)

Runs the production `walk_the_talk()` pipeline for each labelled claims→actuals pair, matches each labelled claim to the closest system claim (overlap of content stems blended with overlap of numbers, threshold 0.45), and reports **claim recall**, **verdict accuracy**, **Cohen's κ** and the confusion matrix. Precision is *not* reported: the system extracts more claims than are labelled and only labelled claims have ground truth.

## What is not measured

- Answer quality on documents outside this corpus (annual reports, other companies, PDFs with real page numbers).
- Latency under concurrency; all timings are single-query, models warm, on one Apple M-series machine.
- FinBERT division sentiment: no labelled data yet.
- Judge reliability against a human panel.
