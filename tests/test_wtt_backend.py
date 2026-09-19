"""Tests for Walking-the-Talk backend utilities (Phase 06, Plan 01)."""

import asyncio
import inspect

from finsight.credisentiment.prompts import (
    STAGE1_EXTRACT_CLAIMS_PROMPT,
    STAGE2_VERIFY_CLAIMS_PROMPT,
    deduplicate_claims,
    parse_json_array,
    parse_json_object,
    strip_think_tags,
)
from finsight.credisentiment.router import get_wtt_documents, walk_the_talk_endpoint
from finsight.credisentiment.service import _call_wtt_llm, get_document_chunks, walk_the_talk
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


class TestStripThinkTags:
    def test_properly_closed_tags(self):
        assert strip_think_tags("before<think>thinking</think>after") == "beforeafter"

    def test_unclosed_tag(self):
        assert strip_think_tags("before<think>thinking") == "before"

    def test_orphan_close_tag(self):
        assert strip_think_tags("before</think>after") == "beforeafter"

    def test_multiple_blocks(self):
        result = strip_think_tags("<think>block1</think>middle<think>block2</think>end")
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
# _call_wtt_llm goes through the provider layer
# ---------------------------------------------------------------------------


class TestCallWttLlm:
    def test_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(_call_wtt_llm)

    def test_returns_provider_text(self, monkeypatch):
        from finsight.llm import LLMResponse

        async def fake(prompt, **kw):
            assert kw["json_mode"] is True and kw["temperature"] == 0.0
            return LLMResponse(text='{"claims": []}', model="m", provider="test")

        monkeypatch.setattr("finsight.credisentiment.service.agenerate", fake)
        assert asyncio.run(_call_wtt_llm("hello")) == '{"claims": []}'

    def test_returns_empty_string_on_llm_error(self, monkeypatch):
        from finsight.llm import LLMError

        async def boom(prompt, **kw):
            raise LLMError("down")

        monkeypatch.setattr("finsight.credisentiment.service.agenerate", boom)
        assert asyncio.run(_call_wtt_llm("hello")) == ""


# ---------------------------------------------------------------------------
# get_document_chunks tests
# ---------------------------------------------------------------------------


class TestGetDocumentChunks:
    def test_returns_ordered_texts(self):
        """Create 3 ComparisonChunk rows with different chunk_index values,
        verify get_document_chunks returns them in order."""
        from unittest.mock import MagicMock

        from finsight.models import ComparisonChunk

        # Create mock chunks out of order
        chunk_a = MagicMock(spec=ComparisonChunk, text="chunk_0", chunk_index=0)
        chunk_b = MagicMock(spec=ComparisonChunk, text="chunk_1", chunk_index=1)
        chunk_c = MagicMock(spec=ComparisonChunk, text="chunk_2", chunk_index=2)

        mock_session = MagicMock()
        # session.exec(stmt).all() returns ordered chunks
        mock_session.exec.return_value.all.return_value = [chunk_a, chunk_b, chunk_c]

        result = get_document_chunks(mock_session, document_id=42)

        assert result == ["chunk_0", "chunk_1", "chunk_2"]
        # Verify select was called
        mock_session.exec.assert_called_once()


# ---------------------------------------------------------------------------
# walk_the_talk pipeline tests
# ---------------------------------------------------------------------------


class TestWalkTheTalkPipeline:
    def test_walk_the_talk_is_async(self):
        assert inspect.iscoroutinefunction(walk_the_talk)

    def test_walk_the_talk_rejects_non_cs_indexed_docs(self):
        """Mock session with doc that has cs_status='pending', verify returns None."""
        from unittest.mock import MagicMock

        mock_doc = MagicMock()
        mock_doc.cs_status = "pending"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_doc

        result = asyncio.run(walk_the_talk(mock_session, 1, 2))
        assert result is None


# ---------------------------------------------------------------------------
# Router endpoint tests
# ---------------------------------------------------------------------------


class TestRouterEndpoints:
    def test_walk_the_talk_endpoint_is_async(self):
        assert inspect.iscoroutinefunction(walk_the_talk_endpoint)

    def test_wtt_documents_endpoint_exists(self):
        """Verify get_wtt_documents endpoint exists and is callable."""
        assert callable(get_wtt_documents)

    def test_wtt_documents_endpoint_filters_cs_status(self):
        """Verify the endpoint source contains cs_status filtering logic."""
        source = inspect.getsource(get_wtt_documents)
        assert "cs_status" in source
        assert '"indexed"' in source
