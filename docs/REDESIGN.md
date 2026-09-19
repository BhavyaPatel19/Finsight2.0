# Accuracy redesign (branch `experiment/accuracy-redesign`)

`main` is the original project, untouched. This branch rebuilds the accuracy-critical core from first principles and measures every step with the harness in `eval/`. Baseline numbers (old pipeline, same gold sets): retrieval hit@5 0.844 / MRR 0.738; generation 87.5% correct; Walk-the-Talk κ 0.10.

## Why rebuild rather than tune

Measured on the sample corpus before any redesign:

| document | text that reached the index |
|---|---|
| Q1 FY26 call transcript | **66%** (147 of 435 sentences never indexed) |
| Q4 FY26 fact sheet | **65%** |
| Q4 FY25 fact sheet | 80% |
| Q4 FY25 call transcript | 89% |

The old chunker dropped text silently, table rows were indexed without their header row (a fact-sheet line reads `Total employees | 328,594 | 337,034 | 323,578` with no dates attached), and claim verification retrieved "actuals" per *category* from one document with a dense-only search that was never measured. Retrieval tuning cannot recover text that is not indexed.

## Principles

1. **Lossless by construction.** Ingestion produces typed elements; chunking is a total function over them with a tested invariant: every element's text appears in at least one chunk.
2. **Structure is context.** Table rows carry their table title and header row; transcript chunks carry the speaker; every chunk carries `company · document type · period · section`. What the embedder, BM25 and the reranker see is the same enriched text; what the user sees (and what citations quote) is the verbatim source.
3. **Retrieve small, return big.** Sentences are indexed for precision and mapped back to their parent chunk for context (small-to-big). Hybrid BM25 + dense over sentences and chunks, fused with RRF, then a cross-encoder over the parent chunks.
4. **Use what the question says.** A question that names a period ("Q4 FY25", "April 2026", "FY26") is filtered/boosted to matching documents; the corpus is dominated by near-identical filings from different periods, so this prior is worth a lot and costs nothing.
5. **Numbers are checked, not trusted.** In claim verification, when a target and an actual are both numeric, the verdict is computed (range containment, direction), not generated. The LLM extracts; code decides.
6. **Abstain explicitly.** RAG already answers "Not found in the selected documents." Verification gains an `UNVERIFIABLE` verdict, and any MET/MISSED/PARTIAL verdict must cite a quote that is verifiably present in the retrieved actuals, or it is downgraded.
7. **Every change is a row in `eval/results/HISTORY.md`.** Nothing lands without a before/after on the same gold set.

## Architecture

```
finsight/corpus/        ingestion v2
  elements.py           Element(kind, text, page, section, speaker, table_title, table_header)
  parse_html.py         EDGAR/IR HTML → elements (paragraphs, speaker turns, table rows with headers)
  parse_pdf.py          PyMuPDF → elements (blocks, headings from TOC, tables via find_tables)
  chunker.py            lossless chunking: speaker turns → sentence-bounded chunks with overlap;
                        tables → row chunks (title + header + row) plus grouped table chunks;
                        paragraphs → merged chunks with sentence overlap. Invariant tested.
finsight/retrieval/     retrieval v2
  index.py              chunk + sentence records → ChromaDB (finsight_v2) and BM25; context header
  periods.py            period parsing from questions (FY, quarter, month-year) → document filter/boost
  search.py             retrieve(question, mode) : sentence+chunk hybrid → RRF → parent expansion → rerank
finsight/verification/  Walk the Talk v2
  claims.py             claim schema (metric, target value/range, period, category, source quote); extraction
  evidence.py           per-claim actuals retrieval over all documents of the target period (retrieval v2)
  verdict.py            deterministic numeric verdicts; LLM verdicts with mandatory quote; UNVERIFIABLE
  pipeline.py           orchestration + persistence
```

The old `finsight/rag/` and `finsight/credisentiment/` stay until v2 beats them on the same gold; the eval harness can run either engine so the comparison is like-for-like.

## Measurement plan

| step | change | metric that must move |
|---|---|---|
| 1 | lossless ingestion + structured chunks | text coverage → 100%; gold chunk coverage 95.3% → 100% |
| 2 | retrieval v2 (small-to-big, period prior, header-aware rerank) | hit@1 0.656, hit@5 0.844, MRR 0.738 |
| 3 | embedding / reranker ablation (bge-base → bge-large / bge-m3; reranker-base → v2-m3) | same |
| 4 | generation v2 (quote-then-answer, verified citations) | correctness 87.5%, faithfulness 0.947, citation validity |
| 5 | verification v2 | claim recall 0.80, verdict agreement 0.58, κ 0.10; expanded gold |
| 6 | Groq 70B runs with a different judge | cross-check of 4–5 |
