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

---

# Generation (answers, not just retrieval)

`python -m eval.generation` — production pipeline (hybrid_rerank, top-8, strict grounding prompt), 64 gold questions (60 answerable + 4 unanswerable).

| run | generator | judge | correct | partial | incorrect | faithfulness | number recall | abstain (unans.) | false abstain | cited | cited pages ⊆ retrieved | p50 latency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `generation_ollama-qwen3-14b.json` | qwen3:14b (local, thinking on) | qwen3:14b | 87.5% | 7.8% | 4.7% | 0.947 (n=57) | 0.720 | 100% | 6.2% | 95% | 100% | 47 s |

What the first generation run changed:

- **Ollama's default context window was truncating the RAG prompt.** The prompt is ~4,100 tokens; Ollama defaulted to 2,048 and drops tokens from the *front*, so the model saw neither the grounding rules nor the first chunks and fabricated figures ("$10.3 billion" for a $19.3 bn revenue). `OLLAMA_NUM_CTX` (default 8192) is now sent on every call. Before the fix, 0/3 smoke-test answers were correct; after, 3/3.
- Every remaining "incorrect" answer is an **abstention** on a question whose evidence retrieval did not surface (two are the chunk-boundary cases from the retrieval coverage report, one is a cross-document headcount comparison). The model does not hallucinate when retrieval fails; it says "Not found in the selected documents."
- Four questions exceeded the 120 s request timeout on long reasoning traces (p90 latency 80 s); providers now carry their own default timeout (Ollama 300 s) and those four were re-run and merged (`reruns` in the JSON records provenance). Three were correct, one partial.
- Number recall (0.72) undercounts: it cannot equate `$19,277 million` with `$19.3 bn` or `Rs 43.00` with `₹43`; the judge can, hence correctness > number recall.

Caveat: generator and judge are the same model here. A Groq run (Llama 3.3 70B generating, a different model judging) is the cross-check to do before quoting a single headline number.

---

# Walk the Talk (claim verification)

`python -m eval.wtt` — production `walk_the_talk()` per labelled claims→actuals pair, 15 human-labelled claims (`eval/gold/wtt_claims.jsonl`), matched to system claims by content+number overlap (≥ 0.45).

| run | model | claim recall | verdict accuracy (3-way) | κ (3-way) | accuracy (MET vs not) | κ (binary) | system claims / pair |
|---|---|---|---|---|---|---|---|
| `wtt_ollama-qwen3-14b.json` | qwen3:14b (local) | 0.80 (12/15) | 0.58 (7/12) | 0.10 | 0.75 | 0.40 | 35 (capped) |

Confusion (human → system): MET→{MET 7, PARTIAL 1, MISSED 1} · PARTIAL→{MISSED 2} · MISSED→{MET 1}.

What the run says, reading the system's own explanations:

- **Most disagreements are missing actuals, not bad judgement.** Four of five wrong verdicts say "the actual results do not mention …" — the 70 bps acquisition contribution and the third-party-cost reduction are in the Q4 FY26 call but the per-claim retrieval (top-3 of 3,500-char chunks) did not surface them; the FY26 tax rate is not stated in any call at all (the label was derived from the fact sheet). The verdict scheme has no way to say so, so the model guesses MISSED. **Next change: an `UNVERIFIABLE` verdict**, the same abstention principle the RAG prompt already follows.
- **PARTIAL is a policy question.** Both human-PARTIAL claims (guided range not hit, but *favourably*: tax rate 26% vs 29–30% guided) were graded MISSED. Reasonable people differ; the label guide should say which.
- **Recall losses look structural.** Three labelled claims were never extracted: a wage-hike timing statement buried in Q&A, the Project Maximus margin remark (matched at 0.444, just under the threshold), and the FY25 dividend proposal. Stage 2 also caps at 35 claims (`WTT_MAX_CLAIMS`, now configurable), which silently drops candidates from the later batches.
- The run first returned **no claims at all**: `WTT_PARALLEL=4` against a single-slot local Ollama queued requests until they timed out. Concurrency now follows the provider. Worth remembering that a pipeline can "work" on a hosted API and fail silently on a local one.

n=12 matched claims is too few to quote κ with confidence; the number is here so the next run (Groq 70B, higher claim cap, UNVERIFIABLE verdict) has something to be compared against.

---

# Redesign branch: ingestion v2 + retrieval v2 (PDF corpus is primary)

Same 64 gold questions; the filings rendered to real PDFs (`documents/pdf/`, `FINSIGHT_CORPUS=pdf`) and the original HTML. "≤6k chars" = evidence inside the first 6,000 characters handed to the LLM (chunk-size-neutral).

| corpus | engine | hit@1 | hit@5 | MRR@8 | nDCG@8 | ≤6k chars | chunk coverage | ms/query | run |
|---|---|---|---|---|---|---|---|---|---|
| PDF | old pipeline (v1, base reranker) | 0.688 | 0.875 | 0.771 | 0.788 | 0.859 | 96.9% | 600 | `retrieval_pdf-v1-baseline.json` |
| PDF | v2, first cut (structured chunks + sentences, base reranker) | 0.672 | 0.859 | 0.746 | 0.760 | 0.875 | 100% | 452 | `retrieval_pdf-v2.json` |
| PDF | + table titles from page geometry, Q&A context on answer chunks | 0.656 | 0.906 | 0.758 | 0.782 | 0.906 | 100% | 463 | – |
| PDF | + `bge-reranker-v2-m3`, verbalised rows, table channel | **0.781** | **1.000** | **0.879** | **0.892** | **1.000** | 100% | 1,527 | `retrieval_pdf-v2-k8.json` |
| PDF | ablation: no table channel | 0.766 | 0.953 | 0.849 | 0.864 | 0.953 | | | same run |
| PDF | ablation: no period prior | 0.812 | 0.984 | 0.886 | 0.893 | 0.984 | | | same run |
| PDF | ablation: 15 candidates instead of 20 | 0.781 | 0.984 | 0.871 | 0.882 | | | 1,129 | `retrieval_pdf-v2-pf125-c15.json` |
| HTML | old pipeline (v1) with m3 reranker | 0.734 | 0.859 | 0.792 | 0.806 | | | 2,123 | `retrieval_html-v1-m3.json` |
| HTML | v2 | 0.750 | 0.984 | 0.856 | 0.868 | | 100% | 1,520 | `retrieval_html-v2.json` |

What moved the numbers, in order of size:

1. **The reranker was the bottleneck, not the index.** `bge-reranker-base` scored an irrelevant transcript paragraph at 0.69–0.75 as long as it carried the document header, and the correct fact-sheet row at 0.001 without one — it was matching the header, not the content. `bge-reranker-v2-m3` scores the same irrelevant paragraph 0.03 and the row 0.98. Per-question cost ~1 s for 20 candidates on Apple silicon.
2. **Verbalised table rows.** A row is indexed as `Revenues by Business Segments (in %) — Financial services: Quarter ended Mar 31, 2025 = 28.4; Dec 31, 2024 = 27.8; …` (header:value pairs) instead of `Financial services | 28.4 | 27.8 | …`. The verbatim row is still what the user sees and citations quote.
3. **A table channel in first-stage retrieval** (dense + BM25 restricted to row/table chunks, 10 each): prose that merely *mentions* "financial services" otherwise crowds every row out of the top-20 before the reranker sees it. +0.047 hit@5.
4. **Lossless structured ingestion** made the rest possible (chunk coverage 96.9% → 100%) but by itself was a wash on ranking — a fair comparison needs the context-budget view, because the old 1,500-char windows contained more text per hit.
5. Table titles from page geometry (the two short lines above a table: title + units), and the preceding analyst question attached to an answer chunk's index text (the question carries the vocabulary the answer lacks).
6. The period prior from the question is small on this corpus (hit@5 0.984 → 1.000, hit@1 −0.03); kept at ×1.25.

Not done / next: embedding-model ablation (bge-base → bge-large / bge-m3), latency work on the reranker (batching, candidate pruning), and the same measurement on a bookmarked 200-page annual report, which this corpus does not contain.

---

# Redesign branch: Walk the Talk v2 (PDF corpus, `qwen3:14b` local)

Gold grew from 15 to 25 labelled claims (16 MET, 3 PARTIAL, 1 MISSED, **5 UNVERIFIABLE** — FY27 commitments from the April 2026 call graded after one reported quarter). Numbers below are therefore not directly comparable with the 15-claim v1 row; the confusion matrices are.

| run | claim recall | verdict acc. (4-way) | acc. on answered | abstain recall / precision | κ | confusion (human → system) |
|---|---|---|---|---|---|---|
| v1 (old pipeline, 15 claims) | 0.80 | 0.58 | 0.58 | – | 0.10 | MET→{MET 7, PARTIAL 1, MISSED 1} · PARTIAL→{MISSED 2} · MISSED→{MET 1} |
| v2.0 — typed claims, per-claim evidence over all filings of the period, quote-checked verdicts, direction-aware numeric rule, outcome-oriented evidence query, dedupe (`wtt_pdf-v2.0-qwen3-14b.json`) | 0.84 (21/25) | 0.48 (10/21) | 0.67 (10/15) | **0.0** / 0.0 | −0.03 | MET→{MET 10, MISSED 3} · PARTIAL→{MISSED 1, UNVERIFIABLE 1} · MISSED→{MET 1} · UNVERIFIABLE→{MET 5} |

Reading v2.0's own explanations, one failure explains 8 of the 11 disagreements: **a promise restated in the actuals period was taken as an outcome.** The July 2026 call restates FY27 guidance, so all five FY27 claims were graded MET ("the company reiterated…"); "we expect FY27 third-party cost to remain at similar levels" was read as contradicting "FY26 third-party cost will be lower than FY25"; and "we expect H1 to be stronger than H2" was graded as contradicting the *equivalent* claim "H2 weaker than H1". The three fixes measured next as v2.1: evidence re-ranked by an outcome weight (reported-result verbs and table rows over forward-looking sentences), the verdict prompt stating that a promise is never an outcome and different-period evidence does not count, and a token-overlap fallback for quote matching (two claims were dropped because the model lightly rephrased its quote).

| v2.1 — + outcome-weighted evidence, "a promise is never an outcome" rule, token-overlap quote matching (`wtt_pdf-v2.1-qwen3-14b.json`) | 0.84 | 0.52 | 0.77 (10/13) | 0.2 / 0.25 | 0.06 | MET→{MET 10, MISSED 2, UNVERIFIABLE 1} · PARTIAL→{UNVERIFIABLE 2} · MISSED→{MET 1} · UNVERIFIABLE→{MET 4, UNVERIFIABLE 1} |
| **v2.2** — + period-completeness guard and promise-as-evidence downgrade *in code* (`wtt_pdf-v2.2-qwen3-14b.json`) | 0.84 | **0.71** | **0.83** (10/12) | **1.0** / 0.56 | **0.50** | MET→{MET 10, UNVERIFIABLE 2, MISSED 1} · PARTIAL→{UNVERIFIABLE 2} · MISSED→{MET 1} · UNVERIFIABLE→{UNVERIFIABLE 5} |

v2.1 showed the limit of prompting a 14B judge: told that a promise is never an outcome, it still graded four FY27 claims MET from Q1 FY27 numbers ("FY27 margin was reported as 21.1%") and from restated guidance. v2.2 moved both rules into code — a claim's period must have ended by the latest reported period of the actuals documents, and a cited evidence sentence that is itself forward-looking cannot support a verdict — and abstention recall went from 0.2 to 1.0 with κ from 0.06 to 0.50.

What v2.2 still gets wrong, and what would fix it: it abstains on two claims a person would compute (free cash flow ÷ net profit; tax ÷ profit before tax — the numbers are in the fact sheet) → a derived-metrics step; it grades "the endeavour is to improve margins" MET when the margin was flat → a qualitative-claim rule (direction words vs a flat outcome); four soft, conversational commitments are never extracted → the claim detector (`finsight/ml/claims`). n = 21 matched claims: the κ is a direction, not a measurement.

What already works in v2.0 and did not in v1: the FY26 growth beat (3.1% vs 1–3%) is MET by the direction-aware rule; the margin actual is found in the fact sheet rather than "not mentioned"; a claim whose quote is not in the source cannot exist; a verdict whose quote is not in the evidence cannot stand.
