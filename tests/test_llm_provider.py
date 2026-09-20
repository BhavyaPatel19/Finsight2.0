"""Provider layer: selection, request shapes, retries, and error mapping. No network."""

import asyncio
import json

import httpx
import pytest

from finsight import config
from finsight.llm import LLMError, get_provider, reset_provider, resolve_provider_name
from finsight.llm.groq import GroqProvider
from finsight.llm.ollama import OllamaProvider


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_provider()
    yield
    reset_provider()


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_auto_prefers_groq_when_key_present(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "auto")
        monkeypatch.setattr(config, "GROQ_API_KEY", "gsk_x")
        assert resolve_provider_name() == "groq"
        assert isinstance(get_provider(), GroqProvider)

    def test_auto_falls_back_to_ollama(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "auto")
        monkeypatch.setattr(config, "GROQ_API_KEY", "")
        assert resolve_provider_name() == "ollama"
        assert isinstance(get_provider(), OllamaProvider)

    def test_explicit_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(config, "GROQ_API_KEY", "gsk_x")
        assert isinstance(get_provider(), OllamaProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "bedrock")
        with pytest.raises(ValueError):
            get_provider()

    def test_singleton(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
        assert get_provider() is get_provider()


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------


def _groq_ok(content="hello", model="openai/gpt-oss-120b"):
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    }


class TestGroq:
    def test_request_shape_and_response_parsing(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json=_groq_ok("42"))

        p = GroqProvider(api_key="gsk_test", transport=httpx.MockTransport(handler))
        r = p.generate("q?", max_tokens=99, temperature=0.2, json_mode=True, system="be terse")

        assert seen["url"].endswith("/chat/completions")
        assert seen["auth"] == "Bearer gsk_test"
        body = seen["body"]
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["max_tokens"] == 99 and body["temperature"] == 0.2
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0] == {"role": "system", "content": "be terse"}
        assert body["messages"][1] == {"role": "user", "content": "q?"}

        assert r.text == "42" and r.provider == "groq"
        assert r.prompt_tokens == 12 and r.completion_tokens == 3 and r.total_tokens == 15
        assert r.latency_ms >= 0

    def test_model_override(self):
        def handler(request):
            body = json.loads(request.content)
            return httpx.Response(200, json=_groq_ok(model=body["model"]))

        p = GroqProvider(api_key="k", transport=httpx.MockTransport(handler))
        assert p.generate("x", model="openai/gpt-oss-20b").model == "openai/gpt-oss-20b"

    def test_retries_on_429_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("finsight.llm._retry.time.sleep", lambda s: None)
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"retry-after": "0"}, text="slow down")
            return httpx.Response(200, json=_groq_ok("ok"))

        p = GroqProvider(api_key="k", transport=httpx.MockTransport(handler))
        assert p.generate("x").text == "ok"
        assert calls["n"] == 2

    def test_non_retryable_error_raises_llm_error(self):
        def handler(request):
            return httpx.Response(401, text='{"error":"bad key"}')

        p = GroqProvider(api_key="k", transport=httpx.MockTransport(handler))
        with pytest.raises(LLMError, match="401"):
            p.generate("x")

    def test_missing_key_raises_without_network(self):
        p = GroqProvider(api_key="")
        assert not p.is_configured()
        with pytest.raises(LLMError, match="GROQ_API_KEY"):
            p.generate("x")

    def test_async_path(self):
        def handler(request):
            return httpx.Response(200, json=_groq_ok("async ok"))

        p = GroqProvider(api_key="k", async_transport=httpx.MockTransport(handler))
        assert asyncio.run(p.agenerate("x")).text == "async ok"

    def test_available_models_filters_non_chat(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "openai/gpt-oss-120b"},
                        {"id": "whisper-large-v3"},
                        {"id": "openai/gpt-oss-safeguard-20b"},
                        {"id": "canopylabs/orpheus-v1-english"},
                        {"id": "groq/compound"},
                    ]
                },
            )

        p = GroqProvider(api_key="k", transport=httpx.MockTransport(handler))
        assert [m["id"] for m in p.available_models()] == ["openai/gpt-oss-120b"]


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


class TestOllama:
    def test_request_shape_and_response_parsing(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "model": "llama3.1:8b",
                    "response": "  hi  ",
                    "prompt_eval_count": 5,
                    "eval_count": 2,
                },
            )

        p = OllamaProvider(base_url="http://ollama:11434/", transport=httpx.MockTransport(handler))
        r = p.generate("q", max_tokens=50, json_mode=True, system="sys")

        assert seen["url"] == "http://ollama:11434/api/generate"
        body = seen["body"]
        assert body["model"] == "llama3.1:8b" and body["stream"] is False
        assert body["options"] == {"num_predict": 50, "temperature": 0.0, "num_ctx": 8192}
        assert body["format"] == "json" and body["system"] == "sys"
        assert r.text == "hi" and r.provider == "ollama"
        assert r.prompt_tokens == 5 and r.completion_tokens == 2

    def test_connection_error_raises_llm_error(self, monkeypatch):
        monkeypatch.setattr("finsight.llm._retry.time.sleep", lambda s: None)

        def handler(request):
            raise httpx.ConnectError("refused")

        p = OllamaProvider(transport=httpx.MockTransport(handler))
        with pytest.raises(LLMError, match="failed"):
            p.generate("x")

    def test_available_models_from_tags(self):
        def handler(request):
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.1:8b"}]})

        p = OllamaProvider(transport=httpx.MockTransport(handler))
        assert [m["id"] for m in p.available_models()] == ["llama3.1:8b", "qwen2.5:7b"]


# ---------------------------------------------------------------------------
# /llm/models endpoint
# ---------------------------------------------------------------------------


class TestModelsEndpoint:
    def test_requires_auth(self, api_client):
        assert api_client.get("/llm/models").status_code == 401

    def test_reports_active_provider(self, api_client, auth_headers, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
        monkeypatch.setattr(config, "GROQ_API_KEY", "")  # configured=False, fallback list
        r = api_client.get("/llm/models", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["provider"] == "groq"
        assert data["configured"] is False
        assert data["default_model"] == "openai/gpt-oss-120b"
        assert data["models"] and all({"id", "label"} <= set(m) for m in data["models"])

    def test_default_falls_back_to_an_installed_model(self, api_client, auth_headers, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(config, "OLLAMA_MODEL", "llama3.1:8b")
        monkeypatch.setattr(
            OllamaProvider, "available_models", lambda self: [{"id": "qwen3:14b", "label": "qwen3:14b (local)"}]
        )
        r = api_client.get("/llm/models", headers=auth_headers)
        assert r.json()["default_model"] == "qwen3:14b"
