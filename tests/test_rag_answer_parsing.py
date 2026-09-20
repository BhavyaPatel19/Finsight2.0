def test_normalize_output_undoes_model_typography():
    from finsight.rag.service import _normalize_output

    raw = "ANSWER:\nMargin was **20.9%**【fact sheet Q4 FY26, Page 2】 on $14.9 billion, 1.5%‑3%."
    assert _normalize_output(raw) == "ANSWER:\nMargin was 20.9%[fact sheet Q4 FY26, Page 2] on $14.9 billion, 1.5%-3%."


def test_verify_quotes_ignores_unicode_spacing():
    from finsight.rag.service import verify_quotes

    ctx = ["large deal wins of $14.9 billion, 55% net new; growth of 1.5%-3%"]
    out = verify_quotes(["$14.9 billion, 55 % net new", "1.5%‑3%", "not in context"], ctx)
    assert [o["verified"] for o in out] == [True, True, False]
