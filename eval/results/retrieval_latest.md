# Retrieval evaluation — 2026-09-20 (`6d6ed03`, pdf-v2-k8-final)

Corpus: 8 documents, 821 chunks · gold: 64 answerable questions · chunk coverage 100.0% (evidence for 64/64 questions exists in some chunk)

Embeddings `BAAI/bge-base-en-v1.5` · reranker `BAAI/bge-reranker-v2-m3` · first stage top-20 → top-8

| mode | hit@1 | hit@3 | hit@5 | hit@8 | MRR@8 | nDCG@8 | hit@6k chars | hit@12k chars | ctx chars | latency (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| v2 | 0.797 | 0.969 | 1.000 | 1.000 | 0.891 | 0.899 | 1.000 | 1.000 | 5559 | 1590 |

## By question type (hit@5 / MRR)

| type | n | v2 |
|---|---|---|
| cross_doc | 4 | 1.00 / 0.62 |
| explanatory | 2 | 1.00 / 1.00 |
| factual | 2 | 1.00 / 1.00 |
| guidance | 9 | 1.00 / 0.89 |
| numeric | 47 | 1.00 / 0.90 |

Relevance = retrieved chunk contains a gold evidence quote. Latency is mean per query on this machine, models warm.
