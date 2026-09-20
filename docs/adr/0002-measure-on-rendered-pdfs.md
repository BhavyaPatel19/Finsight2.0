# 0002 — Measure the PDF path on the same filings rendered to PDF

**Status:** accepted · **Date:** 2026-09-19

## Context

The product ingests PDFs (uploads, BSE attachments). The only public, programmatically accessible copies of Indian filings found were SEC EDGAR 6-K exhibits in HTML; company IR sites and BSE return 403 to programmatic requests and are out of bounds (0006). The first evaluation therefore measured only the HTML path — not the path users take.

## Decision

Render the HTML exhibits to real multi-page PDFs with headless Chrome (`scripts/render_pdfs.py`) and treat the PDF corpus as primary. `FINSIGHT_CORPUS=pdf` gives it its own SQLite file and vector store so both corpora coexist and every eval can run on either with the same gold set (relevance is pipe- and glyph-insensitive so table rows match across formats).

## Consequences

The audit's PDF-specific defects (no speakers detected, tables flattened, fact sheets misrouted) became measurable, and the redesign was validated on PDFs first. Limitation: rendered PDFs are text-based and single-column; scanned or multi-column annual reports are not represented and remain the next corpus to add.
