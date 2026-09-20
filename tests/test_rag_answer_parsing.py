def test_normalize_output_undoes_model_typography():
    from finsight.rag.service import _normalize_output

    raw = "ANSWER:\nMargin was **20.9%**【fact sheet Q4 FY26, Page 2】 on $14.9 billion, 1.5%‑3%."
    assert _normalize_output(raw) == "ANSWER:\nMargin was 20.9%[fact sheet Q4 FY26, Page 2] on $14.9 billion, 1.5%-3%."


def test_verify_quotes_ignores_unicode_spacing():
    from finsight.rag.service import verify_quotes

    ctx = ["large deal wins of $14.9 billion, 55% net new; growth of 1.5%-3%"]
    out = verify_quotes(["$14.9 billion, 55 % net new", "1.5%‑3%", "not in context"], ctx)
    assert [o["verified"] for o in out] == [True, True, False]


def test_answer_without_citation_borrows_verified_evidence_citations():
    from finsight.rag.service import attach_citations, parse_evidence, verify_quotes

    raw = (
        'EVIDENCE:\n- "Operating margin was at 21.1%, expansion of 0.5% year on year." [results press release Q4 FY25, Page 1]\n'
        '- "made-up sentence" [earnings call transcript Q4 FY25, Page 9]\n\nANSWER:\nMargin was 21.1%, up 0.5% year on year.'
    )
    answer, lines = parse_evidence(raw)
    ev = verify_quotes([q for q, _ in lines], ["Operating margin was at 21.1%, expansion of 0.5% year on year."])
    assert [e["verified"] for e in ev] == [True, False]
    out = attach_citations(answer, ev, dict(lines))
    assert out == "Margin was 21.1%, up 0.5% year on year. [results press release Q4 FY25, Page 1]"
    # already cited, or an abstention: untouched
    assert attach_citations("X [press release Q4 FY25, Page 2].", ev, dict(lines)).endswith("Page 2].")
    assert (
        attach_citations("Not found in the selected documents.", ev, dict(lines))
        == "Not found in the selected documents."
    )
