# Pipeline audit — every process, what it does, where accuracy is lost

Scope: the path a document takes from acquisition to an answer or a verdict, on the branch `experiment/accuracy-redesign`. Measurements are on the 8-filing Infosys corpus in two forms: the EDGAR HTML exhibits and **the same filings rendered to real PDFs** (`documents/pdf/`, 5–18 pages each, no bookmarks) — the PDF path is the product's primary path (uploads and BSE/Screener downloads are PDFs).

Legend: **defect** = wrong/lossy behaviour, measured where possible · **opt** = the change this branch makes.

---

## A. Acquisition

| process | how it works | findings |
|---|---|---|
| A1 upload (`/ingestion/documents/upload`, `/credisentiment/upload`) | PDF/HTML/TXT saved under `documents/`, `Document` row `status=pending` | Hardened on this branch (types, size, sniff, sanitised names). Two endpoints create rows with different defaults. **opt**: one endpoint. |
| A2 scraper (`scraper/screener_scraper.py`, `bse_scraper.py`) | Scrapes Screener.in company pages for BSE attachment links (annual reports, concall transcripts) and downloads PDFs; rotates User-Agents | TOS/blocking risk; not part of the measured path. Documents it yields are Word→PDF exports (transcripts) and large bookmarked PDFs (annual reports). Kept out of the eval; **opt**: leave as opt-in, never the default source. |
| A3 sample corpus (`scripts/seed_demo.py`) | SEC EDGAR 6-K exhibits (HTML) | Added on this branch. **opt**: also render to PDF (`scripts/render_pdfs.py`, headless Chrome) so the PDF path is measured on the same gold set. |

## B. Text extraction

| process | how it works | findings |
|---|---|---|
| B1 `extract_text_from_pdf` | whole-document `page.get_text()` concatenated; used by the legacy process route and by sentiment/credibility via `text_path` | No pages, no structure. |
| B2 `_extract_structured_pdf` | per-page `get_text("text")`; sections from PDF bookmarks only | **defect**: tables become one cell per line (`Reported\nCC\nQoQ growth (%)\n-4.2%…`) — row structure is gone, so "Gross Profit 1,428 1,345" is unrecoverable as a fact (2 of 64 gold facts not present in extracted text). `find_tables()` is never used. No header/footer stripping (BSE PDFs carry "Page 3 of 18"), no hyphenation repair, no reading-order handling for multi-column annual reports. Transcripts and fact sheets have no bookmarks → no sections at all. |
| B3 HTML (`html_parser.py`, added on branch) | paragraphs; bold-only lines → `Speaker:`; 2-col bullet tables; synthetic 3,000-char pages | Tables flattened to `a \| b \| c` rows without their header rows; layout tables (numbered remarks) misread as data. |

**opt (B)**: one parser producing typed elements — paragraph, speaker turn, heading, **table row with its header row and table title** — from both PDF (`find_tables` + text blocks outside table boxes + bookmark sections + header/footer removal) and HTML. Real page numbers for PDFs, synthetic segments for HTML.

## C. Structure detection

| process | how it works | findings |
|---|---|---|
| C1 `is_concall_transcript` | ≥5 matches of `_SPEAKER_RE` (`Name:`/`Moderator:`/`[…]`) in the first 5 pages | **defect (PDF)**: transcript PDFs put the speaker name on its own line *without a colon* → 0 matches → **all 4 transcript PDFs treated as plain documents**. **defect (both)**: any "Capitalised Words:" line matches → **both fact sheets misdetected as transcripts** and chunked lossily (71% and 82% of text survive). |
| C2 sections | only from PDF bookmarks | Absent for transcripts, press releases, fact sheets → the "section" in every citation is empty for those. |

**opt (C)**: detect speakers structurally (bold-only short line in HTML; a short Title-Case line on its own, followed by prose, in PDF), not by a colon regex; sections from bookmarks *or* heading elements.

## D. Chunking — three chunkers, three routes for the same document

| process | how it works | findings |
|---|---|---|
| D1 `chunk_text` 512/64 | character sliding window over B1 text | **Used by the Documents page "Process" button** (`/ingestion/documents/{id}/process` → `process_document`). No page numbers (citations show page 0), cuts mid-word. After it runs, `/rag/prepare` sees `status=indexed` and **skips** the page-aware pass — so a user who processes from the Documents page chats over 512-char windows. |
| D2 `chunk_pages` 1500/200 | fixed windows within each page | Cuts mid-sentence and mid-row; never crosses a page, so a sentence spanning pages is split. This is what transcript PDFs get (because of C1). |
| D3 `chunk_by_speaker` 1500 | per page: speaker-regex boundaries, turns packed to 1,500 chars | **defect**: `boundaries` start at the first regex match on the page, so any text before it — every turn continuing from the previous page — is **discarded**. Measured on HTML: Q1 FY26 call 66% of text indexed (147/435 sentences lost), Q4 FY25 call 89%. A single long turn is not split (2,900-char chunks). |
| D4 `chunk_for_credisentiment` 3500/500 | section-aware windows for Walk the Talk, separate `ComparisonChunk` rows + separate Chroma collection | Same B2/C1 inputs, so the same losses; duplicates every embedding. |
| D5 routes | D1 via Documents page, D2/D3 via Chat "prepare", D4 via CrediSentiment | `status` and `cs_status` are independent; the Chat route silently trusts D1's output. |

Gold-evidence coverage of the old chunkers: HTML 61/64, **PDF 60/64**. Lossless structured chunking (this branch, HTML): **64/64**.

**opt (D)**: one chunker over elements with a tested invariant (every element's text is in some chunk): sentence-bounded prose with one-sentence overlap, speaker turns never merged across speakers, each table row its own chunk *with title + header*, plus grouped table chunks; one route, one index, one status.

## E. Indexing

| process | how it works | findings |
|---|---|---|
| E1 embeddings | `BAAI/bge-base-en-v1.5`, query instruction prefix, normalised | Document text embedded raw in the original; with a `company · doc type · period` header on this branch (dense hit@5 0.438 → 0.578 — the corpus is near-identical filings from four periods). |
| E2 vector store | ChromaDB `finsight_docs` (cosine) + `credisentiment_docs` | Fine. Model-change auto-reset works. |
| E3 BM25 | rank-bm25 in memory, `\w+` tokenizer | Original built from SQL rows → `page_number: 0` on every BM25 hit (fixed on branch: built from Chroma). **defect**: tokenizer splits `4,730` into `4` and `730`, drops `%`/`$`, no stemming — numbers are the strongest lexical signal in filings. |

**opt (E)**: index two granularities (sentence → parent chunk) with the same enriched text; number-aware tokenizer (`4,730`→`4730`, `21.1%`→`21.1%`, `$4.1bn`); light stemming.

## F. Retrieval

| process | how it works | findings |
|---|---|---|
| F1 dense top-30, BM25 top-30, RRF (k=60), cross-encoder `bge-reranker-base`, top-8 | `rag/retrieval.py` (factored on branch) | Original **defect**: reranker scored `text[:512]` *characters* (≈120 tokens). Fixed. Measured (HTML): hit@5 0.578 → 0.844, MRR 0.426 → 0.738 after four fixes (see `eval/results/HISTORY.md`). Remaining: no use of periods named in the question; no table awareness; `where` filters exist for symbol/fiscal_year but the UI never sets them. |

**opt (F)**: small-to-big (sentence hits → parent chunks), period parsing from the question as a document prior, candidates 20, stronger reranker ablation (v2-m3), header-aware rerank input.

## G. Generation

| process | how it works | findings |
|---|---|---|
| G1 prompt + LLM | strict grounding prompt with per-chunk headers, `[Section > Page N]` citations, provider layer (branch), temperature 0 (branch; was model default) | Original **defect**: Ollama's default 2,048-token window truncated the ~4,100-token prompt from the front (fixed: `OLLAMA_NUM_CTX`). Measured: 87.5% correct, faithfulness 0.947, 100% abstention on unanswerable; every wrong answer was an abstention on a retrieval miss. |

**opt (G)**: quote-then-answer format (extract supporting quotes, then answer), citation check against retrieved pages, number formatting kept verbatim.

## H. Walk the Talk

| process | how it works | findings |
|---|---|---|
| H1 stage 1 extraction | keyword-density prefilter → top-40 chunks → batches of 5 → JSON claims → dedupe by (category, first 80 chars) → **cap 35** | Q&A commitments without the keyword list are never seen; the cap silently drops later batches (3/15 labelled claims never extracted). |
| H2 stage 2 verification | for each batch of 7 claims: **one dense query per category** built from 3 concatenated claims, top-3 chunks from **one** actuals document, 4,000 chars → LLM verdict MET/MISSED/PARTIAL | Measured: recall 0.80, verdict agreement 0.58, κ 0.10. Four of five wrong verdicts say "the actuals do not mention…": the evidence was in the call/press/fact sheet but not in the 3 chunks retrieved per *category*. No `UNVERIFIABLE`; no quote required; numeric comparisons left to the LLM. |
| H3 concurrency | `WTT_PARALLEL=4` | Deadlocked single-slot Ollama into zero claims (fixed on branch: provider-aware). |

**opt (H)**: extract over every transcript chunk (cheap with the sentence index: forward-looking sentence filter, then LLM structuring); per-claim hybrid+rerank retrieval over **all** documents of the actuals period; deterministic verdicts when target and actual are both numeric; `UNVERIFIABLE`; mandatory evidence quote verified as a substring of retrieved text; no silent cap.

## I. Sentiment (FinBERT)

| process | how it works | findings |
|---|---|---|
| I1 document level (`sentiment/service.py`) | split on `[.!?]+`, **first 500 sentences only**, one sentence per forward pass, score = mean(pos − neg) | `[.!?]+` breaks "Rs. 43", "Q4.", "vs."; anything after sentence 500 is ignored; unbatched. |
| I2 division level (`credisentiment/service.py`) | groups by bookmark sections, else by page section, else **whole document truncated to 15,000 chars as "Full Document"** | For transcripts/fact sheets (no bookmarks) it is always the truncated single bucket. Batched FinBERT is fine. |

**opt (I)**: divisions = sections or speakers from elements; all sentences via the chunker's splitter; batched.

## J. Credibility (fundamentals)

`credibility/service.py` extracts claims from the **first 8,000 characters** of the text; `fundamentals.py` scores yfinance ratios against fixed thresholds and calls it a "credibility score" — it is a fundamentals-quality heuristic, unmeasured. **opt**: rename to what it is; claim extraction moves to Walk the Talk v2.

## K. Retrieval/eval instrumentation

Eval relevance normalises whitespace/quotes but not `|` — on PDFs a table fact reads `Total employees 328,594 …` with no pipes. **opt**: pipe-insensitive normalisation so the same gold set scores both corpora.

---

## Order of work (each step measured on the PDF corpus first, HTML second)

1. B+C+D: one parser (PDF `find_tables` + blocks + speakers + header/footer), one lossless chunker, one route. Gate: element coverage 100%, gold evidence coverage 64/64 on PDF.
2. E+F: sentence+chunk index, number-aware BM25, period prior, rerank. Gate: hit@1 / hit@5 / MRR vs the current 0.656 / 0.844 / 0.738 (HTML) and a fresh PDF baseline.
3. G: quote-then-answer. Gate: correctness / faithfulness / citation validity.
4. H: verification v2. Gate: recall / agreement / κ on an expanded gold set.
5. I: sentiment v2 on elements. Gate: no truncation; per-division output for transcripts.
