"""
Groq backend — hosted, OpenAI-compatible chat completions.

Free tier at https://console.groq.com; no card required. Fast enough for
interactive RAG (Llama 3.3 70B at several hundred tokens/s).
"""
from __future__ import annotations

import logging
import time

import httpx

from finsight.llm._retry import apost_with_retry, post_with_retry
from finsight.llm.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Shown in the UI when the models endpoint is unreachable. Kept short and current.
_FALLBACK_MODELS = [
    {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (Groq)"},
    {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (Groq, fast)"},
]


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str,
        default_model: str = "llama-3.3-70b-versatile",
        base_url: str = GROQ_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._async_transport = async_transport

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # -- request/response plumbing -------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, prompt, model, max_tokens, temperature, json_mode, system) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _parse(self, data: dict, started: float) -> LLMResponse:
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"unexpected Groq response shape: {str(data)[:200]}") from e
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text.strip(),
            model=data.get("model", self.default_model),
            provider=self.name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    # -- public API ----------------------------------------------------------

    def generate(self, prompt, *, model=None, max_tokens=2048, temperature=0.0,
                 json_mode=False, system=None, timeout=120.0, think=None) -> LLMResponse:
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not set")
        started = time.perf_counter()
        with httpx.Client(timeout=timeout, transport=self._transport) as client:
            r = post_with_retry(
                client, f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system),
            )
        return self._parse(r.json(), started)

    async def agenerate(self, prompt, *, model=None, max_tokens=2048, temperature=0.0,
                        json_mode=False, system=None, timeout=120.0, think=None) -> LLMResponse:
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not set")
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout, transport=self._async_transport) as client:
            r = await apost_with_retry(
                client, f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system),
            )
        return self._parse(r.json(), started)

    def available_models(self) -> list[dict]:
        if not self.api_key:
            return _FALLBACK_MODELS
        try:
            with httpx.Client(timeout=5.0, transport=self._transport) as client:
                r = client.get(f"{self.base_url}/models", headers=self._headers())
                r.raise_for_status()
            ids = sorted(m["id"] for m in r.json().get("data", []) if m.get("active", True))
            # Chat-capable text models only; Groq also lists whisper/tts/guard models.
            ids = [i for i in ids if not any(k in i for k in ("whisper", "tts", "guard", "prompt-guard"))]
            return [{"id": i, "label": i} for i in ids] or _FALLBACK_MODELS
        except Exception as e:  # network / auth — UI still needs a list
            logger.warning("could not list Groq models: %s", e)
            return _FALLBACK_MODELS
