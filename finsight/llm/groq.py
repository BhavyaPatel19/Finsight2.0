"""
Groq backend — hosted, OpenAI-compatible chat completions — and the Cerebras
variant, which serves the same models through the same API shape.

Free tier at https://console.groq.com; no card required. Fast enough for
interactive RAG (GPT-OSS 120B at several hundred tokens/s). A new Groq project
blocks every model (HTTP 403 "blocked at the project level") until an admin
enables it under Settings → Project → Limits.
"""

from __future__ import annotations

import logging
import time

import httpx

from finsight.llm._retry import apost_with_retry, post_with_retry
from finsight.llm.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

# Shown in the UI when the models endpoint is unreachable. Kept short and current.
_FALLBACK_MODELS: list[dict] = [
    {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (Groq)"},
    {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (Groq, fast)"},
    {"id": "qwen/qwen3.8-27b", "label": "Qwen 3.8 27B (Groq)"},
]


def _min_reasoning_effort(model: str) -> str | None:
    """Lowest reasoning setting Groq accepts for `model`, or None for non-reasoning models."""
    if "gpt-oss" in model:
        return "low"  # gpt-oss accepts low | medium | high
    if "qwen3" in model:
        return "none"  # qwen3 accepts none | default
    return None


class GroqProvider(LLMProvider):
    name = "groq"
    key_env = "GROQ_API_KEY"
    fallback_models: list[dict] = _FALLBACK_MODELS

    def __init__(
        self,
        api_key: str,
        default_model: str = "openai/gpt-oss-120b",
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

    def _payload(self, prompt, model, max_tokens, temperature, json_mode, system, think=None) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        # Reasoning models spend max_tokens on hidden reasoning first; a 600-token JSON
        # call at the default (medium) effort returns nothing and Groq answers 400
        # json_validate_failed. think=False (all our JSON tasks) asks for the minimum.
        effort = _min_reasoning_effort(model) if think is False else None
        if effort:
            payload["reasoning_effort"] = effort
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

    def generate(
        self,
        prompt,
        *,
        model=None,
        max_tokens=2048,
        temperature=0.0,
        json_mode=False,
        system=None,
        timeout=None,
        think=None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMError(f"{self.key_env} is not set")
        started = time.perf_counter()
        with httpx.Client(timeout=timeout or self.default_timeout, transport=self._transport) as client:
            r = post_with_retry(
                client,
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system, think),
            )
        return self._parse(r.json(), started)

    async def agenerate(
        self,
        prompt,
        *,
        model=None,
        max_tokens=2048,
        temperature=0.0,
        json_mode=False,
        system=None,
        timeout=None,
        think=None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMError(f"{self.key_env} is not set")
        started = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=timeout or self.default_timeout, transport=self._async_transport
        ) as client:
            r = await apost_with_retry(
                client,
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system, think),
            )
        return self._parse(r.json(), started)

    def available_models(self) -> list[dict]:
        if not self.api_key:
            return self.fallback_models
        try:
            with httpx.Client(timeout=5.0, transport=self._transport) as client:
                r = client.get(f"{self.base_url}/models", headers=self._headers())
                r.raise_for_status()
            ids = sorted(m["id"] for m in r.json().get("data", []) if m.get("active", True))
            # Chat-capable text models only; Groq also lists speech, guard and agentic
            # "compound" systems (web search + tools — not grounded, so excluded).
            skip = ("whisper", "tts", "orpheus", "guard", "compound")
            ids = [i for i in ids if not any(k in i for k in skip)]
            return [{"id": i, "label": i} for i in ids] or self.fallback_models
        except Exception as e:  # network / auth — UI still needs a list
            logger.warning("could not list %s models: %s", self.name, e)
            return self.fallback_models


class CerebrasProvider(GroqProvider):
    """Cerebras — same OpenAI-compatible surface and the same open models as Groq
    (ids without the vendor prefix), with a free tier of 1M tokens/day and a
    pay-as-you-go tier without daily caps."""

    name = "cerebras"
    key_env = "CEREBRAS_API_KEY"
    fallback_models = [
        {"id": "gpt-oss-120b", "label": "GPT-OSS 120B (Cerebras)"},
        {"id": "qwen-3.8-27b", "label": "Qwen 3.8 27B (Cerebras)"},
    ]

    def __init__(self, api_key: str, default_model: str = "gpt-oss-120b", base_url: str = CEREBRAS_BASE_URL, **kw):
        super().__init__(api_key, default_model=default_model, base_url=base_url, **kw)
