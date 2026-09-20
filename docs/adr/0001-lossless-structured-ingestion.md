# 0001 — Rebuild ingestion as typed elements + a lossless chunker

**Status:** accepted · **Date:** 2026-09-19

## Context

The original pipeline had three chunkers (`chunk_text` 512-char windows, `chunk_pages` 1,500-char windows, `chunk_by_speaker`) selected by a speaker regex, and a fourth for claim verification. Measured on the sample filings, `chunk_by_speaker` discarded every turn continuing from the previous page (Q1 FY26 call: 34% of sentences never indexed) and the regex misrouted fact sheets into it (up to 35% lost) while failing to recognise transcript PDFs at all. Tables were read as one cell per line; two gold facts did not survive extraction.

## Options

1. Patch each chunker (fix the boundary bug, tighten the regex, add `find_tables`).
2. One parser producing typed elements (paragraph, speaker turn, heading, table row with header) and one chunker with a tested lossless invariant.

## Decision

Option 2 (`finsight/corpus/`). Speaker detection is structural (bold short name-like lines, a document-level dialogue gate) rather than a colon regex; tables keep title, header and group; prose is split at sentence boundaries with one-sentence overlap and never across speakers; each element's text is asserted to be in some chunk.

## Consequences

Element coverage 100% on both formats (was 65–89% on several documents); gold-evidence chunk coverage 60–61/64 → 64/64. On its own this was a wash on ranking metrics — a fair comparison needs a context-budget view — but it is what made the retrieval gains in 0003 possible. Cost: ~3.5× more chunks (rows are their own chunks) and a heavier first-stage list.
