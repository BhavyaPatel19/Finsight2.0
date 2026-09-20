"""Quote-then-answer parsing and runtime quote verification (no LLM)."""

from finsight.rag.service import _build_section_context, parse_answer, verify_quotes

RAW = """EVIDENCE:
- "Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms." [earnings call transcript Q4 FY25, Page 2]
- "Operating margin was at 21.1%, expansion of 0.5% year on year." [results press release Q4 FY25, Page 1]
ANSWER:
Infosys guided FY26 growth of 0% to 3% in constant currency [earnings call transcript Q4 FY25, Page 2] and reported a 21.1% FY25 margin [results press release Q4 FY25, Page 1]."""


def test_parse_two_sections():
    answer, quotes = parse_answer(RAW)
    assert answer.startswith("Infosys guided FY26 growth") and "[earnings call transcript Q4 FY25, Page 2]" in answer
    assert quotes == [
        "Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms.",
        "Operating margin was at 21.1%, expansion of 0.5% year on year.",
    ]


def test_parse_tolerates_missing_evidence_and_plain_text():
    assert parse_answer("ANSWER:\nNot found in the selected documents.") == ("Not found in the selected documents.", [])
    assert parse_answer("Just an answer with no sections.") == ("Just an answer with no sections.", [])
    assert (
        parse_answer("EVIDENCE:\n- (none)\nANSWER:\nNot found in the selected documents.")[0]
        == "Not found in the selected documents."
    )


def test_verify_quotes_against_context():
    ctx = [
        "Salil said: Our guidance for growth for financial year ’26 is 0% to 3% in constant currency terms. Next.",
        "Operating Margin % | 21.1 | 20.1",
    ]
    out = verify_quotes(
        [
            "Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms.",
            "Operating Margin % 21.1 20.1",
            "Margin was 24%.",
        ],
        ctx,
    )
    assert [o["verified"] for o in out] == [True, True, False]


def test_context_header_names_doc_type_and_period():
    chunk = {
        "text": "x",
        "metadata": {
            "doc_type": "concall",
            "fiscal_quarter": "Q4",
            "fiscal_year": "FY25",
            "symbol": "INFY",
            "page_number": 3,
            "speaker": "Salil Parekh",
            "section": "",
        },
    }
    ctx = _build_section_context([chunk])
    assert ctx.startswith("[1] earnings call transcript Q4 FY25 (INFY) | Page 3 | Speaker: Salil Parekh")
