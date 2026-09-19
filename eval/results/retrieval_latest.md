# Retrieval evaluation — 2026-09-19 (`572430d`, baseline)

Corpus: 8 documents, 145 chunks · gold: 64 answerable questions · chunk coverage 95.3% (evidence for 61/64 questions exists in some chunk)

Embeddings `BAAI/bge-base-en-v1.5` · reranker `BAAI/bge-reranker-base` · first stage top-30 → top-8

| mode | hit@1 | hit@3 | hit@5 | hit@8 | MRR@8 | nDCG@8 | P@5 | latency (ms) |
|---|---|---|---|---|---|---|---|---|
| dense | 0.156 | 0.359 | 0.438 | 0.516 | 0.271 | 0.326 | 0.125 | 9 |
| bm25 | 0.328 | 0.594 | 0.656 | 0.719 | 0.461 | 0.513 | 0.144 | 0 |
| hybrid | 0.203 | 0.516 | 0.609 | 0.672 | 0.373 | 0.439 | 0.156 | 9 |
| hybrid_rerank | 0.328 | 0.484 | 0.578 | 0.625 | 0.426 | 0.477 | 0.144 | 371 |

## By question type (hit@5 / MRR)

| type | n | dense | bm25 | hybrid | hybrid_rerank |
|---|---|---|---|---|---|
| cross_doc | 4 | 0.50 / 0.50 | 0.50 / 0.54 | 0.50 / 0.54 | 0.50 / 0.38 |
| explanatory | 2 | 0.50 / 0.12 | 1.00 / 0.67 | 1.00 / 0.42 | 0.50 / 0.50 |
| factual | 2 | 0.50 / 0.50 | 1.00 / 1.00 | 1.00 / 0.62 | 0.00 / 0.00 |
| guidance | 9 | 0.44 / 0.31 | 0.78 / 0.61 | 0.56 / 0.44 | 0.56 / 0.47 |
| numeric | 47 | 0.43 / 0.24 | 0.62 / 0.39 | 0.60 / 0.33 | 0.62 / 0.44 |

Uncovered by chunking (no chunk contains the evidence): r027, r030, r054

Relevance = retrieved chunk contains a gold evidence quote. Latency is mean per query on this machine, models warm.
