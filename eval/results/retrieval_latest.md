# Retrieval evaluation — 2026-09-19 (`3e4afec`, current)

Corpus: 8 documents, 145 chunks · gold: 64 answerable questions · chunk coverage 95.3% (evidence for 61/64 questions exists in some chunk)

Embeddings `BAAI/bge-base-en-v1.5` · reranker `BAAI/bge-reranker-base` · first stage top-20 → top-8

| mode | hit@1 | hit@3 | hit@5 | hit@8 | MRR@8 | nDCG@8 | P@5 | latency (ms) |
|---|---|---|---|---|---|---|---|---|
| dense | 0.328 | 0.531 | 0.578 | 0.734 | 0.450 | 0.513 | 0.128 | 32 |
| bm25 | 0.312 | 0.547 | 0.625 | 0.734 | 0.449 | 0.506 | 0.144 | 0 |
| hybrid | 0.422 | 0.656 | 0.766 | 0.797 | 0.556 | 0.606 | 0.181 | 16 |
| hybrid_rerank | 0.656 | 0.797 | 0.844 | 0.891 | 0.738 | 0.764 | 0.228 | 877 |

## By question type (hit@5 / MRR)

| type | n | dense | bm25 | hybrid | hybrid_rerank |
|---|---|---|---|---|---|
| cross_doc | 4 | 0.50 / 0.29 | 0.50 / 0.41 | 0.75 / 0.33 | 0.75 / 0.42 |
| explanatory | 2 | 1.00 / 0.75 | 0.50 / 0.32 | 1.00 / 1.00 | 1.00 / 1.00 |
| factual | 2 | 0.50 / 0.57 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.75 |
| guidance | 9 | 0.33 / 0.37 | 0.78 / 0.63 | 0.67 / 0.47 | 0.89 / 0.61 |
| numeric | 47 | 0.62 / 0.46 | 0.60 / 0.40 | 0.77 / 0.55 | 0.83 / 0.78 |

Uncovered by chunking (no chunk contains the evidence): r027, r030, r054

Relevance = retrieved chunk contains a gold evidence quote. Latency is mean per query on this machine, models warm.
