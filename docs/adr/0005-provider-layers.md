# 0005 — LLM and market data behind provider interfaces

**Status:** accepted · **Date:** 2026-09-19

## Context

Five code paths called Ollama or Groq directly with different timeouts, no retries, and `"[LLM error: …]"` strings that downstream code parsed as answers. Every market page returned 400 unless the user had a paid Zerodha subscription and an ngrok tunnel, so a fresh clone could not be used.

## Decision

`finsight/llm/` exposes `generate()`/`agenerate()`; Groq (hosted, free tier) is used when a key is set, Ollama otherwise; responses carry model, tokens and latency; failures raise `LLMError` (503 at the API). `finsight/market/providers/` exposes one `MarketDataProvider`; yfinance is the default and Zerodha an opt-in upgrade for users who link an account.

## Consequences

The app runs on a fresh clone with one secret. The evaluation harness runs against any provider, which is how the local-model runs and the planned hosted-model cross-check share one code path. Two provider-specific behaviours had to be encoded: Ollama's context window (`OLLAMA_NUM_CTX`) and its single request slot (verification concurrency = 1 on Ollama).
