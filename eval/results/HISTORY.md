# What the retrieval eval changed

Production path = `hybrid_rerank` (BGE dense + BM25 → RRF → bge-reranker-base → top-8).
Gold: 64 answerable questions over 8 Infosys filings (`eval/gold/retrieval.jsonl`).
Relevance = retrieved chunk contains a gold evidence quote.

| step | change | hit@1 | hit@5 | MRR@8 | nDCG@8 | ms/query | run |
|---|---|---|---|---|---|---|---|
| baseline | as found | 0.328 | 0.578 | 0.426 | 0.477 | 371 | `retrieval_baseline.json` |
| fix 1 | reranker scored `text[:512]` — 512 *characters*, not tokens; pass full chunk | 0.438 | 0.641 | 0.534 | 0.572 | 940 | `retrieval_fix1-rerank-fulltext-bm25-meta.json` |
| fix 2 | BM25 corpus built from ChromaDB, so BM25 hits carry page/section metadata (were `page_number: 0`) | – | – | – | – | – | same run as fix 1 (no ranking change; fixes citations) |
| fix 3 | contextual header (`company · doc type · period`) prepended to the text that is embedded and BM25-tokenised; stored text unchanged | 0.453 | 0.656 | 0.540 | 0.578 | 943 | `retrieval_fix3-context-headers.json` |
| fix 4 | same header shown to the cross-encoder | 0.656 | 0.828 | 0.732 | 0.753 | 947 | – |
| tune | first-stage candidates 30 → 20 (15: hit@5 0.812; 20: 0.844; 30: 0.828) | **0.656** | **0.844** | **0.738** | **0.764** | 641–877 | `retrieval_current.json` |

Observations worth keeping:

- At baseline, BM25 alone (hit@5 0.656) beat the full pipeline (0.578). The hybrid design was right; two implementation details (fixes 1 and 4) were hiding it.
- Fix 3 mostly helped *dense* (hit@5 0.438 → 0.578): the corpus has near-identical filings from four quarters and the embedding could not tell them apart. It slightly hurt BM25 alone (0.656 → 0.625) because every chunk of a document now shares the header tokens.
- The reranker was demoting fact-sheet table rows (`Total employees | 328,594 | …`) until it could see the period header; those rows are where most of the fix-4 gain came from.
- Remaining misses cluster on questions whose evidence spans two chunks (coverage 95.3%: r027, r030, r054 are not in any single chunk) and on cross-document questions, where hit@5 counts any one document.

Gold-set fix along the way: 20 questions had their fact stated in more than one filing (press release ↔ call ↔ fact sheet). Only listing one source under-counted correct retrievals; every restatement is now listed as evidence.
