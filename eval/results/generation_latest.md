# Generation evaluation — 2026-09-20 (`9fb3edb`, pdf-v2.1-cerebras-gpt-oss-120b)

Generator `gpt-oss-120b` via `cerebras` · judge `qwen-3.8-27b` · top-8 hybrid+rerank
· 64 answerable + 12 unanswerable questions · 0 errors

| metric | value |
|---|---|
| correctness vs reference (judge) | correct 78.1% · partial 20.3% · incorrect 1.6% (n=64) |
| faithfulness (judge, claims supported by context) | 0.926 (n=64) |
| number recall (reference numbers present) | 0.762 |
| abstains on unanswerable | 100.0% |
| false abstain on answerable | 0.0% |
| answers with a page citation | 100.0% |
| cited pages ⊆ retrieved pages | 100.0% |
| mean latency | 9058 ms |

## By question type

| type | n | number recall | correct |
|---|---|---|---|
| cross_doc | 4 | 0.71 | 75% |
| explanatory | 2 | 0.50 | 50% |
| factual | 2 | 0.00 | 100% |
| guidance | 9 | 0.81 | 78% |
| numeric | 47 | 0.77 | 79% |

Number recall and abstention are deterministic; correctness and faithfulness are LLM-judged (prompts in eval/judge.py).
