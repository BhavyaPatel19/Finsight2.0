"""Tests for Walking-the-Talk backend utilities (Phase 06, Plan 01)."""

import asyncio
import inspect

import pytest

from finsight.models.enums import ClaimCategory


# ---------------------------------------------------------------------------
# ClaimCategory enum tests
# ---------------------------------------------------------------------------

class TestClaimCategory:
    def test_enum_has_exactly_10_members(self):
        assert len(ClaimCategory) == 10

    def test_enum_contains_all_required_values(self):
        expected = {
            "revenue_growth",
            "margin_expansion",
            "capex",
            "debt_reduction",
            "market_share",
            "new_products",
            "cost_optimization",
            "employee_growth",
            "geographic_expansion",
            "regulatory_compliance",
        }
        actual = {e.value for e in ClaimCategory}
        assert actual == expected


# ---------------------------------------------------------------------------
# strip_think_tags tests
# ---------------------------------------------------------------------------

from finsight.credisentiment.prompts import (
    strip_think_tags,
    parse_json_array,
    parse_json_object,
    deduplicate_claims,
    STAGE1_EXTRACT_CLAIMS_PROMPT,
    STAGE2_VERIFY_CLAIMS_PROMPT,
)


class TestStripThinkTags:
    def test_properly_closed_tags(self):
        assert strip_think_tags("before<think>thinking</think>after") == "beforeafter"

    def test_unclosed_tag(self):
        assert strip_think_tags("before<think>thinking") == "before"

    def test_orphan_close_tag(self):
        assert strip_think_tags("before</think>after") == "beforeafter"

    def test_multiple_blocks(self):
        result = strip_think_tags(
            "<think>block1</think>middle<think>block2</think>end"
        )
        assert result == "middleend"

    def test_no_tags(self):
        assert strip_think_tags("no tags here") == "no tags here"


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestParseJsonArray:
    def test_plain_json_array(self):
        assert parse_json_array('[{"a":1}]') == [{"a": 1}]

    def test_markdown_fences(self):
        text = 'Here is the result:\n```json\n[{"a":1}]\n```'
        assert parse_json_array(text) == [{"a": 1}]

    def test_no_json(self):
        assert parse_json_array("no json here") == []


class TestParseJsonObject:
    def test_plain_json_object(self):
        assert parse_json_object('{"score": 85}') == {"score": 85}

    def test_invalid_json(self):
        assert parse_json_object("invalid") == {}


# ---------------------------------------------------------------------------
# deduplicate_claims tests
# ---------------------------------------------------------------------------

class TestDeduplicateClaims:
    def test_removes_exact_duplicates(self):
        claims = [
            {"category": "revenue_growth", "claim": "We expect 20% revenue growth in FY25"},
            {"category": "revenue_growth", "claim": "We expect 20% revenue growth in FY25"},
        ]
        result = deduplicate_claims(claims)
        assert len(result) == 1

    def test_keeps_different_categories(self):
        claims = [
            {"category": "revenue_growth", "claim": "We expect 20% revenue growth in FY25"},
            {"category": "margin_expansion", "claim": "We expect 20% revenue growth in FY25"},
        ]
        result = deduplicate_claims(claims)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Prompt template tests
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_stage1_contains_all_categories(self):
        for cat in ClaimCategory:
            assert cat.value in STAGE1_EXTRACT_CLAIMS_PROMPT

    def test_stage2_contains_verdict_keywords(self):
        for keyword in ("MET", "MISSED", "PARTIAL"):
            assert keyword in STAGE2_VERIFY_CLAIMS_PROMPT


# ---------------------------------------------------------------------------
# Async Ollama tests
# ---------------------------------------------------------------------------

from finsight.rag.service import call_ollama_async


class TestCallOllamaAsync:
    def test_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(call_ollama_async)

    def test_uses_async_client(self):
        """Verify call_ollama_async invokes httpx.AsyncClient (mocked)."""
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "test reply"}
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client_instance) as mock_cls:
            result = asyncio.run(call_ollama_async("hello"))
            mock_cls.assert_called_once_with(timeout=180.0)
            assert result == "test reply"
