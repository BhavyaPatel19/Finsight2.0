# 0006 — Sample corpus only from sources that permit programmatic access

**Status:** accepted · **Date:** 2026-09-19

## Context

The original scraper rotated User-Agents to evade bot detection on Screener.in and BSE. Company IR sites (Infosys, TCS) return 403 to programmatic requests.

## Decision

The sample corpus is SEC EDGAR only (Form 6-K exhibits filed by Indian companies), downloaded at seed time with the declared User-Agent SEC requires (`EDGAR_USER_AGENT`) and SHA-256 pinned; nothing is redistributed. A 403 is treated as "no", not as an obstacle. The scraper stays in the repository as an opt-in tool and is not part of any measured or documented path.

## Consequences

The corpus is one company and four quarters of HTML (rendered to PDF for the PDF path, see 0002). Broadening it means finding more filers on EDGAR or asking a user to point at their own PDFs — both are manifest entries plus gold questions, not code.
