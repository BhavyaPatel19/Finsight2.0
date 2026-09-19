# Generation evaluation — 2026-09-19 (`32fb09a`, ollama-qwen3-14b)

Generator `qwen3:14b` via `ollama` · judge `qwen3:14b` · top-8 hybrid+rerank
· 64 answerable + 4 unanswerable questions · 0 errors

| metric | value |
|---|---|
| correctness vs reference (judge) | correct 87.5% · partial 7.8% · incorrect 4.7% (n=64) |
| faithfulness (judge, claims supported by context) | 0.947 (n=57) |
| number recall (reference numbers present) | 0.720 |
| abstains on unanswerable | 100.0% |
| false abstain on answerable | 6.2% |
| answers with a page citation | 95.0% |
| cited pages ⊆ retrieved pages | 100.0% |
| mean latency | 61429 ms |

## By question type

| type | n | number recall | correct |
|---|---|---|---|
| cross_doc | 4 | 0.46 | 75% |
| explanatory | 2 | 0.50 | 100% |
| factual | 2 | 0.00 | 100% |
| guidance | 9 | 0.81 | 78% |
| numeric | 47 | 0.74 | 89% |

Number recall and abstention are deterministic; correctness and faithfulness are LLM-judged (prompts in eval/judge.py).
