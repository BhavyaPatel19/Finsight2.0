# Architecture decision records

One file per decision that shaped the accuracy core. Each records the context, the options, the decision, and the measurement that justified it (numbers reference `eval/results/HISTORY.md`).

| # | decision |
|---|---|
| [0001](0001-lossless-structured-ingestion.md) | Rebuild ingestion as typed elements + a lossless chunker instead of patching three chunkers |
| [0002](0002-measure-on-rendered-pdfs.md) | Measure the PDF path on the same filings rendered to PDF, with a separate corpus store |
| [0003](0003-reranker-and-verbalised-rows.md) | `bge-reranker-v2-m3` on enriched index text; table rows verbalised as header:value pairs |
| [0004](0004-verdicts-need-evidence.md) | Verification verdicts must cite a verifiable quote; numeric targets are computed; `UNVERIFIABLE` exists |
| [0005](0005-provider-layers.md) | LLM and market data behind provider interfaces; hosted by default, local optional |
| [0006](0006-public-data-only.md) | Sample corpus from sources that permit programmatic access; no scraping around 403s |
