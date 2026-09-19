"""
Ollama backend — fully local inference via the Ollama HTTP API.

Used when no hosted key is configured, or when LLM_PROVIDER=ollama.
"""
from __future__ import annotations

import logging
import time

import httpx

from finsight.llm._retry import apost_with_retry, post_with_retry
from finsight.llm.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.1:8b",
        num_ctx: int = 8192,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.num_ctx = num_ctx
        self._transport = transport
        self._async_transport = async_transport

    def _payload(self, prompt, model, max_tokens, temperature, json_mode, system, think=None) -> dict:
        payload = {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature, "num_ctx": self.num_ctx},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        if think is not None:
            payload["think"] = think
        return payload

    def _parse(self, data: dict, started: float) -> LLMResponse:
        if "response" not in data:
            raise LLMError(f"unexpected Ollama response shape: {str(data)[:200]}")
        return LLMResponse(
            text=(data.get("response") or "").strip(),
            model=data.get("model", self.default_model),
            provider=self.name,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def generate(self, prompt, *, model=None, max_tokens=2048, temperature=0.0,
                 json_mode=False, system=None, timeout=120.0, think=None) -> LLMResponse:
        started = time.perf_counter()
        with httpx.Client(timeout=timeout, transport=self._transport) as client:
            r = post_with_retry(
                client, f"{self.base_url}/api/generate",
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system, think),
            )
        return self._parse(r.json(), started)

    async def agenerate(self, prompt, *, model=None, max_tokens=2048, temperature=0.0,
                        json_mode=False, system=None, timeout=120.0, think=None) -> LLMResponse:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout, transport=self._async_transport) as client:
            r = await apost_with_retry(
                client, f"{self.base_url}/api/generate",
                json=self._payload(prompt, model, max_tokens, temperature, json_mode, system, think),
            )
        return self._parse(r.json(), started)

    def available_models(self) -> list[dict]:
        try:
            with httpx.Client(timeout=3.0, transport=self._transport) as client:
                r = client.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
            names = sorted(m["name"] for m in r.json().get("models", []))
            return [{"id": n, "label": f"{n} (local)"} for n in names] or [
                {"id": self.default_model, "label": f"{self.default_model} (local)"}
            ]
        except Exception as e:
            logger.warning("could not list Ollama models: %s", e)
            return [{"id": self.default_model, "label": f"{self.default_model} (local)"}]
