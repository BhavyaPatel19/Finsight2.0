# Retrieval evaluation — 2026-09-19 (`629495a`, html-v1-m3)

Corpus: 8 documents, 145 chunks · gold: 64 answerable questions · chunk coverage 95.3% (evidence for 61/64 questions exists in some chunk)

Embeddings `BAAI/bge-base-en-v1.5` · reranker `BAAI/bge-reranker-v2-m3` · first stage top-20 → top-8

| mode | hit@1 | hit@3 | hit@5 | hit@8 | MRR@8 | nDCG@8 | hit@6k chars | hit@12k chars | ctx chars | latency (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_rerank | 0.734 | 0.828 | 0.859 | 0.891 | 0.792 | 0.806 | 0.828 | 0.891 | 14584 | 2123 |

## By question type (hit@5 / MRR)

| type | n | hybrid_rerank |
|---|---|---|
| cross_doc | 4 | 0.75 / 0.67 |
| explanatory | 2 | 1.00 / 1.00 |
| factual | 2 | 1.00 / 1.00 |
| guidance | 9 | 0.89 / 0.67 |
| numeric | 47 | 0.85 / 0.81 |

Uncovered by chunking (no chunk contains the evidence): r027, r030, r054

Relevance = retrieved chunk contains a gold evidence quote. Latency is mean per query on this machine, models warm.
