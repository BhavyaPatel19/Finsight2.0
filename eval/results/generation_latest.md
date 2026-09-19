# Generation evaluation — 2026-09-19 (`32fb09a`, ollama-qwen3-14b)

Generator `qwen3:14b` via `ollama` · judge `qwen3:14b` · top-8 hybrid+rerank
· 60 answerable + 4 unanswerable questions · 4 errors

| metric | value |
|---|---|
| correctness vs reference (judge) | correct 88.3% · partial 6.7% · incorrect 5.0% (n=60) |
| faithfulness (judge, claims supported by context) | 0.949 (n=56) |
| number recall (reference numbers present) | 0.765 |
| abstains on unanswerable | 100.0% |
| false abstain on answerable | 6.7% |
| answers with a page citation | 100.0% |
| cited pages ⊆ retrieved pages | 100.0% |
| mean latency | 53986 ms |

## By question type

| type | n | number recall | correct |
|---|---|---|---|
| cross_doc | 4 | 0.46 | 75% |
| explanatory | 2 | 0.50 | 100% |
| factual | 2 | 0.00 | 100% |
| guidance | 9 | 0.81 | 78% |
| numeric | 43 | 0.80 | 91% |

Number recall and abstention are deterministic; correctness and faithfulness are LLM-judged (prompts in eval/judge.py).
