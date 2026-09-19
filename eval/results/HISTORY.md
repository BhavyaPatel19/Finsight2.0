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
