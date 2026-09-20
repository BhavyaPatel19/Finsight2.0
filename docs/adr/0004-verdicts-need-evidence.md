# 0004 — Verification verdicts must cite a verifiable quote; numeric targets are computed

**Status:** accepted · **Date:** 2026-09-19

## Context

The original Walk-the-Talk asked an LLM for MET/MISSED/PARTIAL over 4,000 characters of "actuals" retrieved per *category* from one document. Against 15 human-labelled claims: verdict agreement 0.58, κ 0.10. Four of the five wrong verdicts explained that "the actual results do not mention…" — the fact was in a sibling filing — and the scheme gave the model no way to say so, so it guessed MISSED.

## Decision

- Claims are typed (metric, period, target as range/point/min/max with unit) and must quote their source sentence verbatim; quotes not found in the batch are dropped.
- Evidence is retrieved per claim with the measured v2 engine over every indexed document of the actuals period.
- Verdicts are MET / MISSED / PARTIAL / **UNVERIFIABLE**. A non-UNVERIFIABLE verdict must cite an evidence quote that is a normalised substring of a retrieved chunk, or it is downgraded.
- When target and actual are both numeric, the verdict is computed with direction awareness (beating a growth range is MET; a tax rate below its range is MET), overriding the model.
- The credibility score averages verifiable claims only; unverifiable ones are reported as a count.

## Consequences

The system can no longer fabricate a verdict from a fact it did not retrieve; abstentions are visible and measured. First run found the symmetric-range bug (3.1% vs 1–3% growth guidance graded PARTIAL) and fixed it before the numbers were quoted.
