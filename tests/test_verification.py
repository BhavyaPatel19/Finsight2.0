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
            ({"kind": "range", "low": 0, "high": 3, "unit": "%"}, 3.1, "PARTIAL"),  # neutral metric: just above the top
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

    @pytest.mark.parametrize(
        "metric,target,actual,expected",
        [
            (
                "revenue growth (constant currency)",
                {"kind": "range", "low": 1, "high": 3, "unit": "%"},
                3.1,
                "MET",
            ),  # beat a growth range
            ("revenue growth (constant currency)", {"kind": "range", "low": 1, "high": 3, "unit": "%"}, 0.5, "MISSED"),
            ("operating margin", {"kind": "range", "low": 20, "high": 22, "unit": "%"}, 22.8, "MET"),
            ("operating margin", {"kind": "range", "low": 20, "high": 22, "unit": "%"}, 19.9, "PARTIAL"),
            (
                "effective tax rate",
                {"kind": "range", "low": 29, "high": 30, "unit": "%"},
                26.4,
                "MET",
            ),  # lower tax than guided is a beat
            ("effective tax rate", {"kind": "range", "low": 29, "high": 30, "unit": "%"}, 32.0, "MISSED"),
            ("onsite mix", {"kind": "point", "value": 23, "unit": "%"}, 22.0, "MET"),
            ("free cash flow as % of net profit", {"kind": "min", "value": 100, "unit": "%"}, 112, "MET"),
        ],
    )
    def test_direction_aware(self, metric, target, actual, expected):
        assert vd.numeric_verdict(target, actual, metric) == expected

    def test_direction_inference(self):
        assert vd.direction("effective tax rate") == "lower"
        assert vd.direction("revenue growth (cc)") == "higher"
        assert vd.direction("number of clients") == "neutral"


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


class TestDedupeAndQuery:
    def _c(self, cid, quote, metric, period, target):
        return cl.Claim(
            id=cid,
            claim=quote,
            quote=quote,
            category="margin",
            metric=metric,
            period=period,
            target=target,
            source_chunk="s",
        )

    def test_restated_commitments_collapse(self):
        rng = {"kind": "range", "low": 20.0, "high": 22.0, "value": None, "unit": "%"}
        a = self._c("a", "Our margin guidance for financial year 2026 is 20% to 22%.", "operating margin", "FY26", rng)
        b = self._c(
            "b", "Our operating margin guidance for the year is 20% to 22%.", "operating margin guidance", "FY26", rng
        )
        c = self._c(
            "c",
            "We expect FY'26 free cash flows to be above 100% of net profit.",
            "free cash flow",
            "FY26",
            {"kind": "min", "low": None, "high": None, "value": 100.0, "unit": "%"},
        )
        assert [x.id for x in cl.dedupe([a, b, c])] == ["a", "c"]

    def test_evidence_query_asks_for_the_outcome(self):
        from finsight.verification.evidence import evidence_query

        q = evidence_query(
            self._c(
                "a",
                "The company guides FY26 revenue growth of 1% to 3% in constant currency.",
                "revenue growth (constant currency)",
                "FY26",
                {"kind": "range", "low": 1.0, "high": 3.0, "value": None, "unit": "%"},
            )
        )
        assert "1" not in q and "3" not in q.replace("FY26", ""), "target numbers removed"
        assert "guide" not in q.lower() and "revenue growth" in q and "FY26" in q and "actual" in q


class TestQuoteMatching:
    batch = [
        {
            "chunk_id": "c1",
            "sentence": "So, Abhishek, most of our employees got the wage hikes in January and the middle level to senior level employees will get wage hike, effective 1st of April.",
            "speaker": "J",
            "page": 8,
        },
        {
            "chunk_id": "c2",
            "sentence": "We expect FY'26 free cash flows to be above 100% of net profit.",
            "speaker": "J",
            "page": 4,
        },
    ]

    def test_exact_prefix_and_trimmed(self):
        assert (
            cl._match_quote("We expect FY'26 free cash flows to be above 100% of net profit.", self.batch)["chunk_id"]
            == "c2"
        )
        assert (
            cl._match_quote(
                "the middle level to senior level employees will get wage hike, effective 1st of April", self.batch
            )["chunk_id"]
            == "c1"
        )

    def test_light_rephrase_is_accepted_but_invention_is_not(self):
        assert (
            cl._match_quote(
                "Most of our employees got wage hikes in January and middle to senior level employees will get a wage hike effective 1st April.",
                self.batch,
            )["chunk_id"]
            == "c1"
        )
        assert cl._match_quote("We will double revenue by 2030 through acquisitions in Europe.", self.batch) is None


class TestPeriodGuard:
    def test_period_parsing(self):
        assert vd.claim_period_end("FY27") == (27, 4)
        assert vd.claim_period_end("Q1 FY26") == (26, 1)
        assert vd.claim_period_end("fiscal '27") == (27, 4)
        assert vd.claim_period_end("FY26 and beyond") is None
        assert vd.claim_period_end(None) is None

    def test_has_ended(self):
        assert vd.period_has_ended("FY27", (27, 1)) is False  # one quarter of FY27 reported
        assert vd.period_has_ended("FY26", (26, 4)) is True
        assert vd.period_has_ended("FY26", (27, 1)) is True
        assert vd.period_has_ended("Q1 FY26", (26, 1)) is True
        assert vd.period_has_ended("medium term", (27, 1)) is None

    def test_judge_short_circuits_before_the_llm(self, monkeypatch):
        async def boom(prompt, **kw):
            raise AssertionError("LLM must not be called")

        monkeypatch.setattr(vd, "agenerate", boom)
        c = cl.Claim(
            id="c",
            claim="FY27 margin 20–22%",
            quote="q",
            category="margin",
            metric="operating margin",
            period="FY27",
            target={"kind": "range", "low": 20, "high": 22, "value": None, "unit": "%"},
            source_chunk="s",
        )
        v = asyncio.run(vd.judge_claim(c, EVIDENCE, latest_reported=(27, 1)))
        assert v.verdict == "UNVERIFIABLE" and v.method == "period-not-ended"

    def test_promise_cited_as_evidence_is_downgraded(self, monkeypatch):
        ev = [
            {
                "id": "d8:c4",
                "text": "We expect effective tax rate for the year to be in the range of 29% to 30%.",
                "doc_type": "concall",
                "page": 4,
                "kind": "prose",
            }
        ]

        async def fake(prompt, **kw):
            return LLMResponse(
                text='{"verdict": "MET", "actual_value": "29-30%", "actual_number": 29.5, "evidence_id": "d8:c4", "evidence_quote": "We expect effective tax rate for the year to be in the range of 29% to 30%.", "explanation": "x"}',
                model="m",
                provider="t",
            )

        monkeypatch.setattr(vd, "agenerate", fake)
        v = asyncio.run(
            vd.judge_claim(
                _claim(
                    {"kind": "range", "low": 29, "high": 30, "value": None, "unit": "%"}, metric="effective tax rate"
                ),
                ev,
            )
        )
        assert v.verdict == "UNVERIFIABLE" and v.method == "downgraded:evidence-is-a-promise"
        assert vd.is_forward_looking("Adjusted operating margin was stable at 21%.") is False


class TestDerived:
    FACTS = [
        "Strong Large Deal wins of $14.9 Billion and healthy Free Cash Flow of $3.7 Billion",
        "Net Profit (after non-controlling interests) | 3,313 | 3,158 | 4.9%",
        "Profit before income taxes | 4,506 | 4,447 | 1.3%",
        "Income tax expense (1) | 1,190 | 1,285 | -7.4%",
    ]

    def test_fcf_over_net_profit(self):
        from finsight.verification.derived import derived_actual

        pct, note = derived_actual("free cash flow as % of net profit", self.FACTS)
        assert pct == 111.7 and "3700" in note and "3313" in note

    def test_effective_tax_rate(self):
        from finsight.verification.derived import derived_actual

        pct, _ = derived_actual("effective tax rate", self.FACTS)
        assert pct == 26.4

    def test_needs_both_figures_and_a_known_metric(self):
        from finsight.verification.derived import derived_actual

        assert derived_actual("effective tax rate", self.FACTS[:2]) is None
        assert derived_actual("operating margin", self.FACTS) is None
        assert derived_actual(None, self.FACTS) is None

    def test_judge_uses_derived_value(self, monkeypatch):
        async def abstain(prompt, **kw):
            return LLMResponse(
                text='{"verdict": "UNVERIFIABLE", "actual_value": null, "actual_number": null, "evidence_id": null, "evidence_quote": null, "explanation": "not stated"}',
                model="m",
                provider="t",
            )

        monkeypatch.setattr(vd, "agenerate", abstain)
        ev = [
            {"id": f"e{i}", "text": t, "doc_type": "fact_sheet", "page": 3, "kind": "row"}
            for i, t in enumerate(self.FACTS)
        ]
        c = cl.Claim(
            id="c",
            claim="FCF above 100% of net profit",
            quote="q",
            category="cash_flow",
            metric="free cash flow as % of net profit",
            period="FY26",
            target={"kind": "min", "low": None, "high": None, "value": 100.0, "unit": "%"},
            source_chunk="s",
        )
        v = asyncio.run(vd.judge_claim(c, ev, latest_reported=(26, 4)))
        assert v.verdict == "MET" and v.method == "derived" and v.actual_number == 111.7
        c2 = cl.Claim(
            id="c2",
            claim="ETR 29-30%",
            quote="q",
            category="tax",
            metric="effective tax rate",
            period="FY26",
            target={"kind": "range", "low": 29.0, "high": 30.0, "value": None, "unit": "%"},
            source_chunk="s",
        )
        v2 = asyncio.run(vd.judge_claim(c2, ev, latest_reported=(26, 4)))
        assert v2.verdict == "MET" and v2.actual_number == 26.4, "lower tax than guided is a beat"


class TestDirectionalClaims:
    def _claim(self, target):
        from finsight.verification.claims import Claim

        return Claim(
            "c1",
            "we expect third-party costs to be lower than FY25",
            "q",
            "cost",
            "third-party costs",
            "FY26",
            target,
            "d1:c1",
        )

    def test_is_directional(self):
        from finsight.verification.evidence import is_directional

        assert is_directional(self._claim(None))
        assert is_directional(self._claim({"kind": "min", "value": 0.0, "unit": "percentage change"}))
        assert is_directional(self._claim({"kind": "max", "value": 0, "unit": "%"}))
        assert not is_directional(self._claim({"kind": "range", "low": 29.0, "high": 30.0, "unit": "%"}))
        assert not is_directional(self._claim({"kind": "min", "value": 100.0, "unit": "%"}))

    def test_numeric_rule_leaves_direction_only_targets_to_the_judge(self):
        # "lower than FY25" became {min, 0, percentage change}; the actual "-1" was graded MISSED
        # by the level rule although the cost fell. Direction-only targets are the judge's call.
        assert (
            vd.numeric_verdict({"kind": "min", "value": 0.0, "unit": "percentage change"}, -1.0, "third-party costs")
            is None
        )
        assert vd.numeric_verdict({"kind": "max", "value": 0, "unit": "%"}, 1.0, "attrition") is None
        assert vd.numeric_verdict({"kind": "min", "value": 100.0, "unit": "%"}, 106.0, "fcf conversion") == "MET"

    def test_baseline_blocks_reach_the_prompt(self, monkeypatch):
        import asyncio

        seen = {}

        async def fake(prompt, **kw):
            seen["prompt"] = prompt

            class R:
                text = '{"verdict": "MISSED", "actual_value": "21.0%", "actual_number": 21.0, "evidence_id": "e1", "evidence_quote": "Operating margin was 21.0%", "explanation": "flat"}'

            return R()

        monkeypatch.setattr(vd, "agenerate", fake)
        ev = [
            {
                "id": "e1",
                "text": "Operating margin was 21.0% for FY26.",
                "doc_type": "press_release",
                "page": 1,
                "kind": "paragraph",
            }
        ]
        base = [
            {
                "id": "b1",
                "text": "Operating margin was 21.1% for FY25.",
                "doc_type": "press_release",
                "page": 1,
                "kind": "paragraph",
            }
        ]
        v = asyncio.run(vd.judge_claim(self._claim(None), ev, baseline=base))
        assert "BASELINE — the metric" in seen["prompt"] and "21.1% for FY25" in seen["prompt"]
        assert v.verdict == "MISSED"
        seen.clear()
        asyncio.run(vd.judge_claim(self._claim(None), ev))
        assert "BASELINE — the metric" not in seen["prompt"]


class TestDerivedFromVerbalisedRows:
    def test_picks_the_period_column(self):
        from finsight.verification.derived import derived_actual

        rows = [
            "Statement of Comprehensive Income — Income tax expense: 3 months ended March 31, 2026 = 300; "
            "3 months ended March 31, 2025 = 280; Year ended March 31, 2026 = 1,190; Year ended March 31, 2025 = 1,100",
            "Statement of Comprehensive Income — Profit before income taxes: 3 months ended March 31, 2026 = 1,200; "
            "3 months ended March 31, 2025 = 1,100; Year ended March 31, 2026 = 4,506; Year ended March 31, 2025 = 4,300",
        ]
        fy = derived_actual("effective tax rate", rows, "FY26")
        q = derived_actual("effective tax rate", rows, "Q4 FY26")
        assert fy and fy[0] == 26.4, fy
        assert q and q[0] == 25.0, q

    def test_verdict_quote_overlap_fallback(self, monkeypatch):
        import asyncio

        async def fake(prompt, **kw):
            class R:
                text = (
                    '{"verdict": "MET", "actual_value": "20.3%", "actual_number": 20.3, "evidence_id": "e1", '
                    '"evidence_quote": "Reported IFRS operating margin was 20.3% and adjusted operating margin at 21.0%", '
                    '"explanation": "in range"}'
                )

            return R()

        monkeypatch.setattr(vd, "agenerate", fake)
        ev = [
            {
                "id": "e1",
                "text": "Reported IFRS operating margin was at 20.3% and adjusted1 operating margin at 21.0% for FY26.",
                "doc_type": "press_release",
                "page": 1,
                "kind": "paragraph",
            }
        ]
        v = asyncio.run(vd.judge_claim(_claim({"kind": "range", "low": 20, "high": 22, "unit": "%"}), ev))
        assert v.verdict == "MET" and v.method != "downgraded:quote-not-found"


class TestReportedVerbs:
    @pytest.mark.parametrize(
        "sentence,forward",
        [
            ("it dropped by about Rs. 2,400 per ton compared to the Rs. 2,000 per ton guidance", False),
            ("we have increased our production from Tata Steel Kalinganagar by 1 million tons", False),
            ("the Company commissioned India's largest blast furnace in FY2024-25", False),
            ("the full year EBITDA was -ve £385 million", False),
            ("Our operating margin guidance for the year is 20% to 22%.", True),
            ("we will finish Kalinganagar at close to 7 million tons", True),
        ],
    )
    def test_results_are_not_promises(self, sentence, forward):
        assert vd.is_forward_looking(sentence) is forward

    def test_outcome_weight_prefers_results(self):
        from finsight.verification.evidence import outcome_weight

        assert outcome_weight("it dropped by about Rs. 2,400 per ton compared to the guidance", "prose") == 1.0
        assert outcome_weight("we expect the turnaround to happen in 4Q", "prose") == 0.5


def test_change_targets_are_directional_and_left_to_the_judge():
    from finsight.verification.claims import Claim
    from finsight.verification.evidence import is_directional

    c = Claim(
        "c",
        "coal costs $15 per ton lower in 2Q",
        "q",
        "cost",
        "coal cost",
        "Q2 FY25",
        {"kind": "min", "value": 15, "unit": "$ per ton reduction"},
        "d1:c1",
    )
    assert is_directional(c)
    # a $27 reduction against a promised $15 reduction must not be read as a cost of 27 vs a cap of 15
    assert vd.numeric_verdict(c.target, 27.0, "coal cost") is None


class TestCaches:
    def test_extraction_is_cached_per_document_and_prompt(self, monkeypatch):
        import asyncio

        from finsight.verification import pipeline

        pipeline.clear_cache()
        calls = {"n": 0}

        async def fake_extract(cands, **kw):
            calls["n"] += 1
            from finsight.verification.claims import last_extraction

            last_extraction.update(batches=1, failed=0)
            return [_claim(None)]

        monkeypatch.setattr(pipeline, "extract_claims", fake_extract)
        key = (1, None, hash(pipeline.EXTRACT_PROMPT), 10, "t")
        assert key not in pipeline._claims_cache
        pipeline._claims_cache[key] = asyncio.run(fake_extract([]))
        assert calls["n"] == 1 and pipeline._claims_cache[key]
        pipeline.clear_cache()
        assert not pipeline._claims_cache

    def test_failed_batches_are_counted_and_not_cached(self, monkeypatch):
        import asyncio

        from finsight.llm import LLMError
        from finsight.verification import claims as cl

        async def boom(prompt, **kw):
            raise LLMError("429")

        monkeypatch.setattr(cl, "agenerate", boom)
        out = asyncio.run(cl.extract_claims([{"sentence": "We expect margins to improve.", "chunk_id": "d1:c1"}] * 13))
        assert out == [] and cl.last_extraction == {"batches": 2, "failed": 2}

    def test_retrieval_cache_keyed_on_query_and_documents(self, monkeypatch):
        from finsight.verification import evidence as ev

        ev.clear_cache()
        calls = {"n": 0}

        def fake_retrieve(session, query, document_ids=None, **kw):
            calls["n"] += 1
            return {"chunks": []}

        monkeypatch.setattr(ev, "retrieve", fake_retrieve)
        ev._retrieve(None, "q", [2, 1], top_k=8)
        ev._retrieve(None, "q", [1, 2], top_k=8)  # same documents, different order
        ev._retrieve(None, "q", [1, 3], top_k=8)
        assert calls["n"] == 2
        ev.clear_cache()
        ev._retrieve(None, "q", [1, 2], top_k=8)
        assert calls["n"] == 3
