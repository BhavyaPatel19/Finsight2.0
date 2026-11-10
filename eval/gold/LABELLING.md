# Walk the Talk: labelling guide

This guide defines how gold labels for Walk the Talk are written and checked: what counts as a claim, what each verdict means, what evidence a label needs, and how the label set is kept honest. Every gold file (`wtt_claims*.jsonl`) follows it.

## 1. Splits, and what may touch them

| Split | Companies | Gold file | Use |
|---|---|---|---|
| dev | Infosys | `wtt_claims.jsonl` | Tune prompts and code freely. |
| dev | Tata Steel | `wtt_claims_tatasteel.jsonl` | Was held out until commit `18f602b`, which copied examples from this set into the extraction and verdict prompts. Results from `fda9545`/`ecc0a2a` (v2.4, v2.5) are held-out numbers; results from `18f602b` onward are dev numbers. |
| **test** | Larsen & Toubro, Bajaj Finance, UltraTech Cement | `wtt_claims_multi.jsonl` (corpus `documents_multi.json`) | Held out. See the rules below. |

Test-set rules:

1. **No test content in prompts or code.** No example, wording, figure or project name from a test company may appear in a prompt, rule or test. Generic rules are fine.
2. **No system output before freezing.** Nobody looks at what Walk the Talk produces for a test company until the gold file is frozen (section 6). Drafting labels does not use the system.
3. **One test run per change.** A change is tuned on dev and measured on test once it is final. If it fails on test, it is not re-tuned against the test result; the result is recorded as is.

## 2. What counts as a claim

A claim is a **forward-looking statement by the company** (management speaking on the call, in prepared remarks or answers) about a **future period**, with an **outcome a later filing could confirm or refute**: a figure, a range, a date, a start/close/commissioning, or a level to reach.

| Include | Exclude |
|---|---|
| "We expect FY26 revenue growth of 0% to 3% in constant currency." | Statements about what already happened ("revenue grew 4% this quarter"). |
| "Capacity will reach 200 MTPA by the end of FY26." | Intentions with no checkable outcome ("we remain committed to growth", "we will keep you updated"). |
| "Credit costs for the year should be in the range of 1.85% to 1.95%." | Anything said by an analyst, even if management agrees with "yes". Use management's own words, or skip it. |
| A restated earlier commitment ("as we said, we expect…"). | Generic macro views ("demand should stay strong in India") with no company outcome. |
| A commitment relayed about a partner or regulator, if the company reports on it later. | Statements whose period can't be determined. |

A sentence with two measurable parts (a volume and a date; a revenue range and a margin range) is two claims.

## 3. Pairing a claim with an actuals document

`claims_doc` is the transcript the claim was made in. `actuals_doc` is the **earliest later transcript in the corpus that reports the result for the claim's period**: for a full-year FY25 target, usually the Q4 FY25 call. If no transcript in the corpus covers the period's result, the claim is UNVERIFIABLE (section 4); still pair it with the latest transcript that could have reported it.

## 4. Verdicts

Judge against **reported results only**: figures that were achieved, events that happened. A later statement of guidance or intent is never an outcome. Read periods carefully: a result for a different period is not evidence.

| Verdict | When |
|---|---|
| **MET** | The reported result achieves the commitment. A range is met when the actual is inside it, ends included. "Above X" is met at ≥ X, "below X" at ≤ X. A project commitment is met when it happened by the promised time. |
| **PARTIAL** | Achieved in part or in direction only: the margin improved but less than promised; one of two plants commissioned; delivered, but one quarter late. |
| **MISSED** | The reported result shows it was not achieved: outside the range in the wrong direction, project not done by the deadline, loss where breakeven was promised (a halved loss is still MISSED). |
| **UNVERIFIABLE** | The corpus does not contain the reported result needed: the period hasn't ended in the available documents, or the outcome is never reported. Use it whenever the number or fact is not there. Do not infer. |

Tie-break rules, so two labellers reach the same answer:

- **Approximate targets.** "About / around / ~X" is MET when the actual rounds to X at the precision X was stated (≈ 12% is met by 11.6–12.4%), PARTIAL when it moved toward X but fell outside that, MISSED otherwise.
- **Directional claims** ("improve", "lower than last year", "maintain") are judged against the figure at the time the claim was made, which must be quoted as baseline evidence. Better in the promised direction is MET; unchanged is PARTIAL for an improvement promise and MET for "maintain"; worse is MISSED. No baseline figure in the corpus means UNVERIFIABLE.
- **Units.** Never convert between currencies or between different measures (per-ton vs total, old vs new segment basis) to make a match: a target in $/t with a result only in Rs/t is UNVERIFIABLE. A change of scale within one currency is fine (Rs 3,566 billion = Rs 3,56,600 crore).
- **Beating a target in the good direction.** For a quantity with a good direction (growth up, working capital or credit cost down), a result better than an "around X" or point target is MET; the approximate-target rule above applies to quantities with no good direction.
- **Secured / signed / approved** is met when the agreement, approval or order is reported, even if the money has not arrived.
- **Overshooting a range** in the good direction (growth above the top of the range) is MET; in the bad direction it is MISSED.

## 5. What each label records

One JSON object per line:

```json
{"id": "lt07", "claims_doc": "LT_concall_Q4FY25", "actuals_doc": "LT_concall_Q4FY26",
 "category": "revenue", "claim": "<management's sentence, verbatim>",
 "human_verdict": "MET", "actual": "<one sentence: what was reported, with figure and period>",
 "evidence": [{"doc": "LT_concall_Q4FY26", "page": 3, "quote": "<verbatim sentence from the actuals doc>"}],
 "claim_page": 5, "drafted_by": "claude", "review": "accepted", "flag": null, "note": null}
```

- `claim` and every evidence `quote` are **verbatim**. Exception: when one sentence holds two measurable parts (section 2), each part is its own label, `claim` restates that part in one sentence ("L&T expects group revenues to grow 15% in FY26."), and the verbatim sentence goes in `quote`. Identical `claim` texts would let the eval's text matching pair a label with the wrong part.
- Pages are **physical PDF pages**, 1-based (a cover letter counts), not the printed page numbers. A script checks each one against the PDF text; any that doesn't match exactly is rejected before review.
- `category` is one of: revenue, growth, margin, cost, capex, capacity, cash_flow, debt, credit_quality, order_book, product, hiring, dividend, tax, other.
- `drafted_by`: `claude` or `human`. `review`: `draft`, `accepted`, `fixed`, `rejected`, `expert`. `flag`: `unsure` when the verdict is a judgment call, with the reason in `note`.
- UNVERIFIABLE labels have an empty `evidence` list and say in `actual` why the result isn't available.

## 6. Drafting, audit and freezing

1. **Enumerate, then sample.** `eval/gold/enumerate_claims.py` lists every management sentence with a forward-looking cue; a labeller keeps the ones that meet section 2. Label all of them or a random sample of at most 12 per transcript (seeded, stated in the commit). Do not pick claims by how hard or easy they look. A restatement of a commitment already labelled from an earlier call is skipped unless its figure or deadline changed.
2. **Draft.** Claude drafts each label from the source PDFs, quotes verified by script, and flags judgment calls.
3. **Blind audit, in two parts.**
   - **Random sample (project owner).** The owner labels a seeded random 30 of the unflagged drafts **without seeing the drafted verdict**, then compares. Report raw agreement and Cohen's κ. If agreement is below 85%, the drafts are not reliable enough: tighten section 4 and redraft before going further.
   - **Flagged labels (external reviewer).** Every label with `flag: "unsure"` goes to an independent certified investment professional, who gives a verdict blind, then sees the draft and its note. Their verdict is final for those labels. Record it with `review: "expert"` and their reasoning in `note`; credit them as "external reviewer (certified investment professional)" unless they ask to be named.
4. **Resolve.** On disagreement in the random sample the owner decides; on flagged labels the external reviewer decides. If disagreements share a pattern ("partial delivery marked MET"), relabel that pattern across the whole file, not just the audited rows.
5. **Freeze.** Commit the file and record its SHA-256 in the commit message. After that, a label changes only to fix a clear factual error, with the reason in `note` and in the commit. Never change a label because the system disagrees with it.

## 7. Held-out RAG questions (`retrieval_multi.jsonl`)

46 questions on the test companies, in the format of `retrieval.jsonl`: 27 numeric, 4 guidance, 4 cross-document, 5 factual and 6 unanswerable. Every evidence quote is verbatim and machine-checked (`check_quotes.py`). An unanswerable question is included only after a search of every transcript in the corpus finds no passage that answers it. `required` lists the numbers the question itself asks for, when the reference answer adds context beyond them (see `docs/EVALUATION.md`, number recall). The test-set rules in section 1 apply: no system run on these questions until the owner has spot-checked them and the file is frozen.

Review, 2026-11-10: every question was re-read against the text around each quote (period, referent, units, completeness), and every unanswerable question re-searched with synonyms. This was done by the author of the questions, so it is a careful re-check, not an independent one. It changed three items: m026 was not unanswerable (the Q2 FY25 call reports Bajaj Finance's S&P and Moody's ratings) and became a factual question, with m046 added as its unanswerable replacement; m043's answer lost a gloss ("wet lease") that the source does not state; m010's answer gained the evidence sentence for its net 20% figure.

