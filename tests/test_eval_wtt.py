"""Claim matching and summary for the Walk-the-Talk eval (no LLM)."""

from eval.wtt import match_claims, similarity, summarise


def test_similarity_ignores_stopwords_and_brackets():
    a = "Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms."
    b = "The company guides FY26 growth of 0% to 3% in constant currency."
    assert similarity(a, b) > 0.3
    assert similarity("If we close [the two acquisitions] in Q1", "if we close in q1") > 0.6


def test_match_and_summarise():
    gold = [
        {
            "id": "w1",
            "claim": "We expect FY26 free cash flows to be above 100% of net profit.",
            "human_verdict": "MET",
            "category": "cash_flow",
        },
        {
            "id": "w2",
            "claim": "Our margin guidance for financial year 2026 is 20% to 22%.",
            "human_verdict": "MET",
            "category": "margin",
        },
        {
            "id": "w3",
            "claim": "We expect to hire over 20,000 freshers in FY26.",
            "human_verdict": "MET",
            "category": "hiring",
        },
    ]
    system = [
        {"claim": "The company expects FY26 free cash flow above 100% of net profit", "verdict": "met"},
        {"claim": "The company guides an operating margin of 20% to 22% for FY2026", "verdict": "MISSED"},
        {"claim": "The company will expand in Japan", "verdict": "PARTIAL"},
    ]
    rows = match_claims(gold, system)
    assert [r["matched"] for r in rows] == [True, True, False]
    assert rows[0]["system"] == "MET" and rows[1]["system"] == "MISSED"
    s = summarise(rows, {"pair": 3})
    assert s["labelled"] == 3 and s["matched"] == 2
    assert s["claim_recall"] == round(2 / 3, 4) and s["verdict_accuracy"] == 0.5
    assert s["unmatched_ids"] == ["w3"]
    assert s["confusion"] == {"MET": {"MET": 1, "MISSED": 1}}
    assert s["kappa"] is not None


def test_each_system_claim_used_once():
    gold = [
        {"id": "a", "claim": "revenue growth of 3% in FY26", "human_verdict": "MET", "category": "revenue"},
        {"id": "b", "claim": "revenue growth of 3% in FY26 again", "human_verdict": "MET", "category": "revenue"},
    ]
    system = [{"claim": "revenue growth of 3% in FY26", "verdict": "MET"}]
    rows = match_claims(gold, system)
    assert sum(r["matched"] for r in rows) == 1


def test_abstention_metrics():
    rows = [
        {
            "id": "a",
            "matched": True,
            "similarity": 1.0,
            "human": "UNVERIFIABLE",
            "system": "UNVERIFIABLE",
            "category": "x",
        },
        {"id": "b", "matched": True, "similarity": 1.0, "human": "UNVERIFIABLE", "system": "MET", "category": "x"},
        {"id": "c", "matched": True, "similarity": 1.0, "human": "MET", "system": "UNVERIFIABLE", "category": "x"},
        {"id": "d", "matched": True, "similarity": 1.0, "human": "MET", "system": "MET", "category": "x"},
    ]
    s = summarise(rows, {"p": 4})
    assert s["abstained"] == 2 and s["abstain_recall"] == 0.5 and s["abstain_precision"] == 0.5
    assert s["verdict_accuracy"] == 0.5 and s["verdict_accuracy_on_answered"] == 1.0
