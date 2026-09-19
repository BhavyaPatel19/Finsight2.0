# Generation evaluation — 2026-09-19 (`fb2c231`, smoke)

Generator `qwen3:14b` via `ollama` · judge `qwen3:14b` · top-8 hybrid+rerank
· 3 answerable + 0 unanswerable questions · 0 errors

| metric | value |
|---|---|
| correctness vs reference (judge) | correct 100.0% · partial 0.0% · incorrect 0.0% (n=3) |
| faithfulness (judge, claims supported by context) | 1.000 (n=3) |
| number recall (reference numbers present) | 0.833 |
| abstains on unanswerable | – |
| false abstain on answerable | 0.0% |
| answers with a page citation | 100.0% |
| cited pages ⊆ retrieved pages | 100.0% |
| mean latency | 111225 ms |

## By question type

| type | n | number recall | correct |
|---|---|---|---|
| guidance | 2 | 1.00 | 100% |
| numeric | 1 | 0.67 | 100% |

Number recall and abstention are deterministic; correctness and faithfulness are LLM-judged (prompts in eval/judge.py).
