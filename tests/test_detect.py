"""Document type, period and company read from a filing's first pages (no model)."""

import fitz
import pytest

from finsight.corpus.detect import _company_from_text, _period_from_text, detect_metadata


def _pdf(tmp_path, name, lines, pages=1):
    path = tmp_path / name
    doc = fitz.open()
    for p in range(pages):
        page = doc.new_page()
        y = 60
        for line in lines if p == 0 else ["Continued."]:
            page.insert_text((40, y), line, fontname="helv", fontsize=10)
            y += 14
    doc.save(path)
    doc.close()
    return path


def test_transcript_with_title_page(tmp_path):
    d = detect_metadata(
        _pdf(
            tmp_path,
            "call.pdf",
            ["Infosys Limited", "Q1 FY26 Earnings Conference Call", "July 23, 2025", "CORPORATE PARTICIPANTS"],
        )
    )
    assert (d["doc_type"], d["fiscal_quarter"], d["fiscal_year"]) == ("concall", "Q1", "FY26")
    assert d["company_name"] == "Infosys Limited"


def test_transcript_without_title_page_uses_the_opening_remarks(tmp_path):
    lines = [
        "CORPORATE PARTICIPANTS",
        "T V Narendran, CEO & MD - Tata Steel Limited",
        "Operator:",
        "Welcome to the call to discuss our results for the fourth quarter and full year FY2025.",
        "Compared to 3QFY25 volumes were higher.",
    ]
    d = detect_metadata(_pdf(tmp_path, "4qfy25-and-fy2025-transcript.pdf", lines))
    assert (d["doc_type"], d["fiscal_quarter"], d["fiscal_year"]) == ("concall", "Q4", "FY25")


def test_press_release_period_from_quarter_ended(tmp_path):
    d = detect_metadata(
        _pdf(tmp_path, "pr.pdf", ["Press Release", "Results for the quarter ended June 30, 2025", "Revenues grew 4%."])
    )
    assert (d["doc_type"], d["fiscal_quarter"], d["fiscal_year"]) == ("press_release", "Q1", "FY26")


def test_annual_report_by_title_and_length(tmp_path):
    d = detect_metadata(
        _pdf(tmp_path, "ir.pdf", ["Integrated Report and Annual Accounts 2024-25", "118th Year"], pages=3)
    )
    assert (d["doc_type"], d["fiscal_quarter"], d["fiscal_year"]) == ("annual_report", "Q4", "FY25")
    d = detect_metadata(_pdf(tmp_path, "long.pdf", ["Board's report"], pages=120))
    assert d["doc_type"] == "annual_report" and d["evidence"]["doc_type"] == "120 pages"


def test_period_falls_back_to_the_file_name(tmp_path):
    d = detect_metadata(_pdf(tmp_path, "ACME_concall_Q2FY25.pdf", ["Operator: Good morning and welcome."]))
    assert (d["fiscal_quarter"], d["fiscal_year"]) == ("Q2", "FY25") and "file name" in d["evidence"]["period"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("our results for the first quarter of FY2026. Compared to 1QFY25 and 4QFY25 volumes", ("Q1", "FY26")),
        ("Quarter ended Mar 31, 2025 Dec 31, 2024 Mar 31, 2024 Quarter ended Mar 31, 2025", ("Q4", "FY25")),
        ("Annual Accounts 2024-25 FY2024-25 highlights; the EAF will be built by FY2027-28 end", ("Q4", "FY25")),
        ("Q4 FY'25 Earnings Conference Call", ("Q4", "FY25")),
    ],
)
def test_period_mentions(text, expected):
    q, fy, _ = _period_from_text(text)
    assert (q, fy) == expected


def test_company_name_strips_title_words():
    assert (
        _company_from_text("Earnings Conference Call Infosys Limited Q1 FY26. Infosys Limited reported.")
        == "Infosys Limited"
    )
    assert (
        _company_from_text(
            "T V Narendran, CEO & MD - Tata Steel Limited; Koushik Chatterjee, ED & CFO - Tata Steel Limited"
        )
        == "Tata Steel Limited"
    )
