"""
LLM provider registry.

    from finsight.llm import generate, agenerate, get_provider, LLMError

Selection (config.LLM_PROVIDER):
    "auto"     → Groq if GROQ_API_KEY is set, else Cerebras if CEREBRAS_API_KEY
                 is set, else Ollama   (default)
    "groq"     → Groq (raises at call time if the key is missing)
    "cerebras" → Cerebras (same open models as Groq, higher free quota)
    "ollama"   → Ollama at OLLAMA_BASE_URL
"""

from __future__ import annotations

import logging

from finsight import config
from finsight.llm.base import LLMError, LLMProvider, LLMResponse
from finsight.llm.groq import CerebrasProvider, GroqProvider
from finsight.llm.ollama import OllamaProvider

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "get_provider",
    "reset_provider",
    "generate",
    "agenerate",
    "llm_configured",
]

logger = logging.getLogger(__name__)
_provider: LLMProvider | None = None


def _build(name: str) -> LLMProvider:
    if name == "groq":
        return GroqProvider(api_key=config.GROQ_API_KEY, default_model=config.GROQ_MODEL)
    if name == "cerebras":
        return CerebrasProvider(api_key=config.CEREBRAS_API_KEY, default_model=config.CEREBRAS_MODEL)
    if name == "ollama":
        return OllamaProvider(
            base_url=config.OLLAMA_BASE_URL,
            default_model=config.OLLAMA_MODEL,
            num_ctx=config.OLLAMA_NUM_CTX,
            default_timeout=config.OLLAMA_TIMEOUT_S,
        )
    raise ValueError(f"unknown LLM_PROVIDER {name!r}; expected auto, groq, cerebras or ollama")


def resolve_provider_name() -> str:
    name = (config.LLM_PROVIDER or "auto").lower()
    if name == "auto":
        if config.GROQ_API_KEY:
            return "groq"
        if config.CEREBRAS_API_KEY:
            return "cerebras"
        return "ollama"
    return name


def get_provider() -> LLMProvider:
    """Process-wide provider singleton, chosen from config on first use."""
    global _provider
    if _provider is None:
        name = resolve_provider_name()
        _provider = _build(name)
        logger.info("LLM provider: %s (default model %s)", _provider.name, _provider.default_model)
    return _provider


def reset_provider() -> None:
    """Drop the cached provider (tests, or after config changes)."""
    global _provider
    _provider = None


def llm_configured() -> bool:
    return get_provider().is_configured()


def generate(prompt: str, **kw) -> LLMResponse:
    """Synchronous completion via the active provider. See LLMProvider.generate."""
    return get_provider().generate(prompt, **kw)


async def agenerate(prompt: str, **kw) -> LLMResponse:
    """Async completion via the active provider. See LLMProvider.agenerate."""
    return await get_provider().agenerate(prompt, **kw)
