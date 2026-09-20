# 0003 — `bge-reranker-v2-m3` on enriched index text; rows verbalised

**Status:** accepted · **Date:** 2026-09-19

## Context

After lossless ingestion, v2 retrieval still missed five fact-sheet rows that were in the index. A probe showed `bge-reranker-base` scoring an irrelevant transcript paragraph at 0.69–0.75 whenever it carried the document header, and the correct row at 0.001 without one — it was matching the header, not the content. Rows indexed as `label | v1 | v2` also lacked the vocabulary of the questions ("share of revenue").

## Options

- Keep the base reranker and drop the header (loses period disambiguation, which had lifted dense hit@5 from 0.44 to 0.58).
- Stronger reranker; keep the header; verbalise rows so the header:value pairing is explicit.

## Decision

`BAAI/bge-reranker-v2-m3` (config `RERANKER_MODEL`); rows are indexed as `title — label: column = value; …` while the verbatim row remains the citable text; a dedicated table channel (dense + BM25 restricted to row/table chunks) guarantees numeric questions get table candidates into fusion.

## Consequences

PDF corpus: hit@5 0.906 → 1.000, hit@1 0.656 → 0.781, MRR 0.758 → 0.879; the same irrelevant paragraph now scores 0.03. Cost: ~1 s per query for 20 candidates on Apple silicon (was ~0.45 s) and a 2 GB model download on first run.
