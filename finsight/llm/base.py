"""
Provider-agnostic LLM interface.

Every backend (Groq, Ollama, ...) implements `LLMProvider`. Call sites use
`finsight.llm.generate()` / `agenerate()` and never talk to a vendor API
directly, so swapping hosted ↔ local is a config change, not a code change.
"""
from __future__ import annotations

import abc
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
