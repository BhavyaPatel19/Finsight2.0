# Evaluation methodology

Everything measured in this repo runs against the same code path the app serves. There are three harnesses, all under `eval/`, all writing JSON + Markdown to `eval/results/`.

## Corpus and gold set

- **Corpus**: 8 public SEC EDGAR Form 6-K exhibits filed by Infosys Ltd — earnings-call transcripts, results press releases and fact sheets for Q4 FY25, Q1 FY26, Q4 FY26 and Q1 FY27 (`eval/gold/documents.json`, SHA-256 pinned, downloaded by `scripts/seed_demo.py`). Chosen because EDGAR permits programmatic access; company IR sites and BSE do not.
- **Retrieval gold** (`eval/gold/retrieval.jsonl`, 76 items): questions written from the filings with a reference answer, the document(s) that state the fact, and verbatim evidence quotes. `eval/gold/_author_retrieval.py` regenerates the file and **fails if any quote is not found in the extracted text**, so the gold set cannot drift from its sources. 64 items are answerable; 12 are deliberately unanswerable from this corpus — four generic and eight *near misses* (adjacent quarters not in the corpus, facts the filings do not state), each verified absent from the text. 20 items list evidence in more than one filing because press releases restate call headlines and fact sheets restate press numbers — listing only one source under-counted correct retrievals in the first run.
- **Walk-the-Talk gold** (`eval/gold/wtt_claims.jsonl`, 25 items): forward-looking claims from the April 2025, July 2025 and April 2026 calls, each labelled MET / MISSED / PARTIAL / UNVERIFIABLE with an actuals quote where one exists. Labels were written by one person; treat κ as agreement with that labeller, not with a panel.

## Corpora and engines

Two copies of the same filings: the EDGAR HTML exhibits (default store) and the same filings **rendered to real PDFs** (`scripts/render_pdfs.py`; `FINSIGHT_CORPUS=pdf` selects a separate SQLite file and vector store). PDF is the product's primary input, so PDF numbers are the ones quoted first. `--engine v1` runs the original pipeline and `v2` the rebuilt one (`finsight/corpus` + `finsight/retrieval` + `finsight/verification`) on the same gold set. Relevance normalisation ignores whitespace, quotes and table pipes, and the ₹ glyph that renders as `(ru)`/`(Rupee Symbol)` in PDF and `( )` in HTML, so a table fact scores identically on both.

## 1. Retrieval (`python -m eval.retrieval`)

Modes: `dense`, `bm25`, `hybrid`, `hybrid_rerank` (the original path) and `v2` with ablations `v2_chunks` (no sentence index, no period prior), `v2_nosent`, `v2_noperiod`, `v2_norerank`, `v2_notables`. Reports hit@1/3/5/8, MRR@8, nDCG@8, P@5, per-stage latency and two **context-budget** metrics — *evidence within the first 6k / 12k characters returned* — because hit@k rewards big chunks: the original 1,500-character windows contain more text per hit than v2's sentence-bounded chunks and rows, and what matters for generation is whether the evidence is inside what the LLM reads.

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

## 3. Walk the Talk (`python -m eval.wtt --engine v2`)

Runs the verification pipeline for each labelled claims→actuals pair, matches each labelled claim to the closest system claim (overlap of content stems blended with overlap of numbers, threshold 0.45), and reports **claim recall**, **verdict accuracy** (four-way, `UNVERIFIABLE` included), **accuracy on answered claims** (both sides gave a verdict), **abstention recall/precision** (did the system say `UNVERIFIABLE` where the human did, and only there), **Cohen's κ** and the confusion matrix. Precision over all system claims is *not* reported: the system extracts more claims than are labelled and only labelled claims have ground truth.

The gold set (`eval/gold/wtt_claims.jsonl`, 25 claims) mixes outcomes that are known (April 2025 and July 2025 commitments graded against April 2026 filings) with five FY27 commitments from the April 2026 call whose outcome cannot be known after one reported quarter — labelled `UNVERIFIABLE` on purpose, so abstention is measured rather than assumed. Labels were written by one person.

## 4. Latency and cost (`python -m eval.bench`)

`retrieval` reports p50/p95 wall time and per-stage time (embed, dense, BM25, fuse, rerank) over the gold questions with warm models; `generation <results.json>` reports prompt/completion tokens, latency percentiles and USD per answer from a Groq price table (local models: n/a).

## CI gate

`.github/workflows/eval-gate.yml` seeds the HTML corpus, runs `eval.retrieval --modes v2` and fails the build below `eval/thresholds.json` (hit@1 0.70, hit@5 0.95, MRR 0.82, chunk coverage 1.0 — a few points under the measured values so a real regression fails and noise does not). PDF thresholds are recorded for local runs.

## What is not measured

- Answer quality on documents outside this corpus (bookmarked annual reports, scanned or multi-column PDFs, other companies).
- Latency under concurrency; all timings are single-query, models warm, on one Apple M-series machine.
- FinBERT division sentiment: no labelled data yet.
- Judge reliability against a human panel.
