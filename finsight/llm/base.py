"""
Provider-agnostic LLM interface.

Every backend (Groq, Ollama, ...) implements `LLMProvider`. Call sites use
`finsight.llm.generate()` / `agenerate()` and never talk to a vendor API
directly, so swapping hosted ↔ local is a config change, not a code change.
"""

from __future__ import annotations

import abc
import os
import threading
from dataclasses import dataclass


class LLMError(RuntimeError):
    """Raised when a provider cannot return a completion (network, auth, quota, bad output)."""


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int | None:
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens


class TokenMeter:
    """Process-wide count of hosted-API tokens, with an optional hard cap.

    ``check()`` runs before every request and refuses to send once the cap is reached, so a
    paid run can never spend more than ``cap`` tokens plus whatever requests are already in
    flight. ``cap=0`` means no limit.
    """

    def __init__(self, cap: int = 0) -> None:
        self.cap = cap
        self.prompt = 0
        self.completion = 0
        self.calls = 0
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    def check(self, provider: str) -> None:
        if self.cap and self.total >= self.cap:
            raise LLMError(
                f"token budget reached: {self.total:,} of LLM_MAX_TOTAL_TOKENS={self.cap:,} "
                f"used; not sending more requests to {provider}"
            )

    def add(self, resp: LLMResponse) -> None:
        with self._lock:
            self.calls += 1
            self.prompt += resp.prompt_tokens or 0
            self.completion += resp.completion_tokens or 0

    def snapshot(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt,
            "completion_tokens": self.completion,
            "total_tokens": self.total,
            "cap": self.cap,
        }


METER = TokenMeter(int(os.getenv("LLM_MAX_TOTAL_TOKENS", "0") or 0))


class LLMProvider(abc.ABC):
    """A text-completion backend."""

    #: short identifier, e.g. "groq" or "ollama"
    name: str
    #: model used when the caller does not pass one
    default_model: str
    #: request timeout when the caller does not pass one (local reasoning models need more)
    default_timeout: float = 120.0

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        json_mode: bool = False,
        system: str | None = None,
        timeout: float | None = None,
        think: bool | None = None,
    ) -> LLMResponse: ...

    @abc.abstractmethod
    async def agenerate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        json_mode: bool = False,
        system: str | None = None,
        timeout: float | None = None,
        think: bool | None = None,
    ) -> LLMResponse: ...

    # `think`: for reasoning models that expose a switch (Ollama qwen3/deepseek-r1),
    # None keeps the model default, False disables the reasoning trace. Ignored elsewhere.

    def available_models(self) -> list[dict]:
        """Models the UI may offer, as [{"id": ..., "label": ...}]. Best effort."""
        return [{"id": self.default_model, "label": self.default_model}]

    def is_configured(self) -> bool:
        """True if this provider has what it needs to make a call (keys, URL)."""
        return True
