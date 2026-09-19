"""Deterministic answer metrics and judge plumbing (LLM calls stubbed)."""

from eval import judge
from eval.generation import deterministic, number_recall, numbers, summarise
from finsight.llm import LLMResponse


class TestNumbers:
    def test_normalises_units_and_commas(self):
        assert numbers("$4,730 million, up 4.8%") == {"4730mn", "4.8%"}
        assert numbers("$4.1 bn (129% of net profit)") == {"4.1bn", "129%"}
        assert numbers("Rs 43.00 vs Rs 38.00") == {"43.00", "38.00"}

    def test_single_digits_ignored(self):
        assert numbers("grew 3x in Q4") == set()

    def test_recall(self):
        ref = "$4,730 million, up 4.8% YoY in constant currency and 3.6% in reported terms."
        assert (
            number_recall(ref, "Q4 revenues were $4,730 million, an increase of 4.8% in CC and 3.6% reported.") == 1.0
        )
        assert number_recall(ref, "Revenue was $4,730 million.") == 1 / 3
        assert number_recall("no numbers here", "anything") is None

    def test_recall_does_not_match_substrings_of_other_numbers(self):
        assert number_recall("14.1%", "attrition was 114.1%") == 0.0


class TestDeterministic:
    item = {"answerable": True, "answer": "21.1%, an improvement of 50 basis points."}

    def test_cited_and_valid(self):
        row = deterministic(
            self.item, "Margin was 21.1% [Section: CFO remarks > Page 2]", [{"page_number": 2}, {"page_number": 5}]
        )
        assert row["cited"] and row["citation_valid"] is True and row["number_recall"] == 0.5
        assert row["false_abstain"] is False

    def test_invalid_citation_page(self):
        row = deterministic(self.item, "Margin was 21.1% [Page 9]", [{"page_number": 2}])
        assert row["citation_valid"] is False

    def test_abstain_on_unanswerable(self):
        row = deterministic(
            {"answerable": False, "answer": "Not found in the selected documents."},
            "Not found in the selected documents.",
            [],
        )
        assert row["abstain_ok"] is True and row["cited"] is False and row["citation_valid"] is None

    def test_false_abstain(self):
        row = deterministic(self.item, "Not found in the selected documents.", [])
        assert row["false_abstain"] is True


class TestSummarise:
    def test_aggregates(self):
        rows = [
            {
                "id": "a",
                "type": "numeric",
                "answerable": True,
                "abstained": False,
                "cited": True,
                "citation_valid": True,
                "number_recall": 1.0,
                "false_abstain": False,
                "latency_ms": 100,
                "faithfulness": {"score": 1.0},
                "correctness": {"grade": "correct"},
            },
            {
                "id": "b",
                "type": "numeric",
                "answerable": True,
                "abstained": True,
                "cited": False,
                "citation_valid": None,
                "number_recall": 0.0,
                "false_abstain": True,
                "latency_ms": 300,
                "correctness": {"grade": "incorrect"},
            },
            {
                "id": "c",
                "type": "unanswerable",
                "answerable": False,
                "abstained": True,
                "cited": False,
                "citation_valid": None,
                "abstain_ok": True,
                "latency_ms": 200,
            },
            {"id": "d", "type": "numeric", "error": "boom"},
        ]
        s = summarise(rows)
        assert s["n"] == 4 and s["errors"] == 1 and s["answerable"] == 2 and s["unanswerable"] == 1
        assert s["number_recall"] == 0.5 and s["false_abstain_rate"] == 0.5 and s["abstain_rate_on_unanswerable"] == 1.0
        assert s["cited_rate"] == 1.0 and s["citation_valid_rate"] == 1.0
        assert s["faithfulness"] == 1.0 and s["correctness"]["correct"] == 0.5
        assert s["latency_ms_mean"] == 200


class TestJudge:
    def test_json_extraction_strips_think(self):
        assert judge._json('<think>hmm</think>{"grade": "correct"}') == {"grade": "correct"}
        assert judge._json("garbage") == {}

    def test_faithfulness_pipeline(self, monkeypatch):
        calls = []

        def fake(prompt, **kw):
            calls.append(prompt)
            if "atomic factual claims" in prompt:
                return LLMResponse(
                    text='{"claims": ["FCF was $4.1 bn", "FCF was 129% of net profit"]}', model="m", provider="t"
                )
            return LLMResponse(
                text='{"verdicts": [{"claim": "FCF was $4.1 bn", "supported": true}, {"claim": "129%", "supported": false}]}',
                model="m",
                provider="t",
            )

        monkeypatch.setattr(judge, "generate", fake)
        r = judge.judge_faithfulness("FCF was $4.1 bn, 129% of net profit.", ["Free cash flow was $4.1 bn"])
        assert r["claims"] == 2 and r["supported"] == 1 and r["score"] == 0.5
        assert len(calls) == 2

    def test_faithfulness_no_claims(self, monkeypatch):
        monkeypatch.setattr(
            judge, "generate", lambda p, **kw: LLMResponse(text='{"claims": []}', model="m", provider="t")
        )
        assert judge.judge_faithfulness("Not found in the selected documents.", [])["score"] is None

    def test_correctness_grade_validation(self, monkeypatch):
        monkeypatch.setattr(
            judge,
            "generate",
            lambda p, **kw: LLMResponse(text='{"grade": "Correct", "reason": "same"}', model="m", provider="t"),
        )
        assert judge.judge_correctness("q", "ref", "ans")["grade"] == "correct"
        monkeypatch.setattr(
            judge, "generate", lambda p, **kw: LLMResponse(text='{"grade": "meh"}', model="m", provider="t")
        )
        assert judge.judge_correctness("q", "ref", "ans")["grade"] == "unknown"

    def test_llm_error_is_contained(self, monkeypatch):
        from finsight.llm import LLMError

        def boom(p, **kw):
            raise LLMError("down")

        monkeypatch.setattr(judge, "generate", boom)
        assert judge.judge_correctness("q", "ref", "ans")["grade"] == "unknown"
        assert judge.judge_faithfulness("x", ["y"])["score"] is None
