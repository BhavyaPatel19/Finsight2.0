"""Walk the Talk v2: candidate gate, extraction with quote check, numeric verdicts, evidence-quote downgrade."""

import asyncio

import pytest

from finsight.llm import LLMResponse
from finsight.verification import claims as cl
from finsight.verification import verdict as vd


class TestCandidateGate:
    @pytest.mark.parametrize(
        "sentence,expected",
        [
            ("Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms.", True),
            ("We expect FY'26 free cash flows to be above 100% of net profit.", True),
            (
                "Most of our employees got the wage hikes in January and the middle level employees will get wage hike, effective 1st of April.",
                True,
            ),
            ("We closed the year with revenues at $19.3 bn, a growth of 4.2% in constant currency terms.", False),
            ("Thank you.", False),
            ("Free cash flow for FY'25 was highest ever at $4.1 bn, 129% of net profit.", False),
        ],
    )
    def test_gate(self, sentence, expected):
        assert cl.is_candidate(sentence) is expected


class TestExtraction:
    def test_quote_must_be_in_batch(self, monkeypatch):
        cands = [
            {
                "chunk_id": "d1:c1",
                "sentence": "Our margin guidance for financial year 2026 is 20% to 22%.",
                "speaker": "Salil Parekh",
                "page": 2,
            },
            {
                "chunk_id": "d1:c2",
                "sentence": "We expect to hire over 20,000 freshers in FY'26.",
                "speaker": "Jayesh Sanghrajka",
                "page": 3,
            },
        ]

        async def fake(prompt, **kw):
            return LLMResponse(
                text=(
                    '{"claims": ['
                    '{"quote": "Our margin guidance for financial year 2026 is 20% to 22%.", "claim": "The company guides FY26 operating margin of 20% to 22%", '
                    '"category": "margin", "metric": "operating margin", "period": "FY26", "target": {"kind": "range", "low": 20, "high": 22, "unit": "%"}},'
                    '{"quote": "We will double revenue by 2030.", "claim": "The company will double revenue by 2030", "category": "revenue", "metric": "revenue", "period": "2030", "target": null},'
                    '{"quote": "We expect to hire over 20,000 freshers in FY\'26.", "claim": "The company plans to hire over 20,000 freshers in FY26", '
                    '"category": "hiring", "metric": "freshers hired", "period": "FY26", "target": {"kind": "min", "value": "20,000", "unit": "count"}}'
                    "]}"
                ),
                model="m",
                provider="t",
            )

        monkeypatch.setattr(cl, "agenerate", fake)
        out = asyncio.run(cl.extract_claims(cands, batch_size=12))
        assert [c.category for c in out] == ["margin", "hiring"], "the invented 'double revenue' claim is dropped"
        assert out[0].target == {"kind": "range", "low": 20.0, "high": 22.0, "value": None, "unit": "%"}
        assert (
            out[1].target["value"] == 20000.0
            and out[1].speaker == "Jayesh Sanghrajka"
            and out[1].source_chunk == "d1:c2"
        )

    def test_bad_target_shapes_become_qualitative(self):
        assert cl._clean_target({"kind": "range", "low": 1}) is None
        assert cl._clean_target({"kind": "min"}) is None
        assert cl._clean_target("20%") is None
        assert cl._clean_target({"kind": "point", "value": 21.1, "unit": "%"})["value"] == 21.1


class TestNumericVerdict:
    @pytest.mark.parametrize(
        "target,actual,expected",
        [
            ({"kind": "range", "low": 0, "high": 3, "unit": "%"}, 3.1, "PARTIAL"),  # just above the top of the range
            ({"kind": "range", "low": 0, "high": 3, "unit": "%"}, 2.0, "MET"),
            ({"kind": "range", "low": 20, "high": 22, "unit": "%"}, 21.0, "MET"),
            ({"kind": "range", "low": 29, "high": 30, "unit": "%"}, 26.4, "MISSED"),
            ({"kind": "min", "value": 100, "unit": "%"}, 112, "MET"),
            ({"kind": "min", "value": 100, "unit": "%"}, 96, "PARTIAL"),
            ({"kind": "min", "value": 20000, "unit": "count"}, 20000, "MET"),
            ({"kind": "max", "value": 25, "unit": "%"}, 27, "MISSED"),
            ({"kind": "point", "value": 21, "unit": "%"}, 21.5, "MET"),
            (None, 5, None),
            ({"kind": "range", "low": 0, "high": 3, "unit": "%"}, None, None),
        ],
    )
    def test_cases(self, target, actual, expected):
        assert vd.numeric_verdict(target, actual) == expected


def _claim(target=None, metric="operating margin"):
    return cl.Claim(
        id="c1",
        claim="The company guides FY26 operating margin of 20% to 22%",
        quote="q",
        category="margin",
        metric=metric,
        period="FY26",
        target=target,
        source_chunk="d1:c1",
    )


EVIDENCE = [
    {
        "id": "d2:c7",
        "text": "Adjusted operating margin was stable at 21%. Gains from currency and Maximus were reinvested.",
        "doc_type": "concall",
        "page": 3,
    },
    {"id": "d3:c2", "text": "Operating Margin % | 20.3 | 21.1 | -0.8%", "doc_type": "fact_sheet", "page": 3},
]


class TestJudge:
    def _run(self, monkeypatch, payload, target=None):
        async def fake(prompt, **kw):
            return LLMResponse(text=payload, model="m", provider="t")

        monkeypatch.setattr(vd, "agenerate", fake)
        return asyncio.run(vd.judge_claim(_claim(target), EVIDENCE))

    def test_verified_quote_and_numeric_override(self, monkeypatch):
        v = self._run(
            monkeypatch,
            '{"verdict": "MISSED", "actual_value": "21% adjusted", "actual_number": 21, "evidence_id": "d2:c7", '
            '"evidence_quote": "Adjusted operating margin was stable at 21%.", "explanation": "x"}',
            target={"kind": "range", "low": 20, "high": 22, "unit": "%"},
        )
        assert v.verdict == "MET" and v.method == "numeric", "21% is inside 20–22%; the LLM's MISSED is overridden"
        assert v.evidence_page == 3 and v.evidence_doc_type == "concall"

    def test_quote_not_in_evidence_downgrades(self, monkeypatch):
        v = self._run(
            monkeypatch,
            '{"verdict": "MET", "actual_value": "21%", "actual_number": 21, "evidence_id": "d2:c7", "evidence_quote": "margin was 24%", "explanation": "x"}',
        )
        assert v.verdict == "UNVERIFIABLE" and v.method == "downgraded:quote-not-found"
        assert v.actual_value is None and v.evidence_quote is None

    def test_quote_found_in_other_block_is_accepted(self, monkeypatch):
        v = self._run(
            monkeypatch,
            '{"verdict": "MISSED", "actual_value": "20.3%", "actual_number": 20.3, "evidence_id": "d2:c7", "evidence_quote": "Operating Margin % | 20.3 | 21.1", "explanation": "x"}',
        )
        assert v.verdict == "MISSED" and v.evidence_id == "d3:c2"

    def test_unverifiable_passthrough(self, monkeypatch):
        v = self._run(
            monkeypatch,
            '{"verdict": "UNVERIFIABLE", "actual_value": null, "actual_number": null, "evidence_id": null, "evidence_quote": null, "explanation": "not stated"}',
        )
        assert v.verdict == "UNVERIFIABLE" and v.method == "llm"

    def test_llm_error_is_unverifiable(self, monkeypatch):
        from finsight.llm import LLMError

        async def boom(prompt, **kw):
            raise LLMError("down")

        monkeypatch.setattr(vd, "agenerate", boom)
        v = asyncio.run(vd.judge_claim(_claim(), EVIDENCE))
        assert v.verdict == "UNVERIFIABLE" and v.method == "llm-error"


def test_overall_score_excludes_unverifiable():
    from finsight.verification import overall_score

    assert overall_score(["MET", "PARTIAL", "MISSED", "UNVERIFIABLE"]) == 50.0
    assert overall_score(["UNVERIFIABLE"]) is None
