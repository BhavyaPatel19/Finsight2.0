"""Ingestion v2: typed elements, lossless chunking, table headers, transcript gate — HTML and PDF."""

import re

import pytest

from finsight.corpus import chunk_elements, parse_document
from finsight.corpus.chunker import coverage, split_sentences
from finsight.corpus.parse_html import parse_html

TRANSCRIPT_HTML = """<html><body>
<p><b>Moderator</b></p><p>Welcome to the Q4 earnings call.</p>
<p><b>Salil Parekh</b></p><p>Thanks. Our guidance for growth for financial year '26 is 0% to 3% in constant currency terms.</p>
<p>Our margin guidance for financial year 2026 is 20% to 22%.</p>
<p><b>Analyst One</b></p><p>What drove the margin?</p>
<p><b>Jayesh Sanghrajka</b></p><p>Value-based selling and utilisation. Rs. 43 per share was paid.</p>
<p><b>Moderator</b></p><p>Next question.</p>
<p><b>Salil Parekh</b></p><p>Closing remarks.</p>
</body></html>"""

FACTSHEET_HTML = """<html><body>
<p><b>Client Data</b></p>
<table>
<tr><td></td><td>Quarter ended</td></tr>
<tr><td></td><td>Mar 31, 2026</td><td>Dec 31, 2025</td><td>Mar 31, 2025</td></tr>
<tr><td>Number of Clients</td></tr>
<tr><td>Active</td><td>1,869</td><td>1,876</td><td>1,882</td></tr>
<tr><td>Total employees</td><td>328,594</td><td>337,034</td><td>323,578</td></tr>
</table>
<p><b>Cash Flow</b></p>
<p>Free cash flow is defined as net cash provided by operating activities less capex.</p>
<p><b>Safe Harbor</b></p>
<p>Certain statements are forward-looking.</p>
</body></html>"""


class TestHtmlElements:
    def test_transcript_speakers_and_turns(self):
        doc = parse_html(TRANSCRIPT_HTML)
        turns = [e for e in doc.elements if e.kind == "speaker_turn"]
        assert {e.speaker for e in turns} == {"Moderator", "Salil Parekh", "Analyst One", "Jayesh Sanghrajka"}
        assert turns[1].speaker == "Salil Parekh" and "0% to 3%" in turns[1].text

    def test_non_transcript_bold_lines_become_headings_not_speakers(self):
        doc = parse_html(FACTSHEET_HTML)
        assert not any(e.speaker for e in doc.elements)
        assert [e.text for e in doc.elements if e.kind == "heading"] == ["Client Data", "Cash Flow", "Safe Harbor"]
        para = next(e for e in doc.elements if e.text.startswith("Free cash flow"))
        assert para.section == "Cash Flow"

    def test_table_rows_carry_merged_header_title_and_group(self):
        doc = parse_html(FACTSHEET_HTML)
        rows = [e for e in doc.elements if e.kind == "table_row"]
        assert [r.text for r in rows] == [
            "Active | 1,869 | 1,876 | 1,882",
            "Total employees | 328,594 | 337,034 | 323,578",
        ]
        assert rows[0].table_header == [
            "Quarter ended Mar 31, 2026",
            "Dec 31, 2025",
            "Mar 31, 2025",
        ] or "Mar 31, 2026" in " ".join(rows[0].table_header)
        assert rows[0].table_title == "Client Data" and rows[0].table_group == "Number of Clients"
        assert "Mar 31, 2026" in rows[1].context_line and "Client Data" in rows[1].context_line


class TestChunker:
    def test_sentence_splitter_keeps_financial_abbreviations(self):
        s = split_sentences("Rs. 43 was paid in Q4. Margin was 21.1% vs. 20.1% last year. Next item.")
        assert s == ["Rs. 43 was paid in Q4.", "Margin was 21.1% vs. 20.1% last year.", "Next item."]

    def test_lossless_and_speaker_bounded(self):
        doc = parse_html(TRANSCRIPT_HTML)
        chunks = chunk_elements(doc.elements, header="Test Co · call · Q4 FY25", max_chars=80)
        covered, missing = coverage(doc.elements, chunks)
        assert missing == []
        for c in chunks:
            speakers = {doc.elements[o].speaker for o in c.element_orders}
            assert len(speakers) == 1, "a chunk never mixes speakers"
        assert all(c.index_text.startswith("Test Co · call · Q4 FY25") for c in chunks)
        assert any("Salil Parekh:" in c.index_text and "Salil Parekh" not in c.text for c in chunks)

    def test_long_turn_splits_with_one_sentence_overlap(self):
        doc = parse_html(
            "<html><body><p><b>A B</b></p><p>" + " ".join(f"Sentence number {i} is here." for i in range(12)) + "</p>"
            "<p><b>C D</b></p><p>Reply one.</p><p><b>A B</b></p><p>More.</p><p><b>C D</b></p><p>End.</p><p><b>E F</b></p><p>x.</p><p><b>A B</b></p><p>y.</p></body></html>"
        )
        chunks = [
            c for c in chunk_elements(doc.elements, max_chars=90) if c.speaker == "A B" and "Sentence number" in c.text
        ]
        assert len(chunks) >= 3
        assert chunks[0].sentences[-1] == chunks[1].sentences[0], "consecutive chunks share one sentence"

    def test_table_rows_and_grouped_tables(self):
        doc = parse_html(FACTSHEET_HTML)
        chunks = chunk_elements(doc.elements)
        rows = [c for c in chunks if c.kind == "row"]
        table = [c for c in chunks if c.kind == "table"]
        assert len(rows) == 2 and len(table) == 1
        assert rows[1].text == "Total employees | 328,594 | 337,034 | 323,578"
        assert "Mar 31, 2026" in rows[1].index_text and "Client Data" in rows[1].index_text
        assert table[0].text.count("\n") == 1


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    """A small transcript-like PDF built with PyMuPDF: bold speaker names, a table, a footer."""
    import fitz

    path = tmp_path_factory.mktemp("pdf") / "call.pdf"
    doc = fitz.open()
    for pno in range(3):
        page = doc.new_page()
        y = 100
        for name, text in [
            ("Moderator", f"Welcome to part {pno + 1} of the call."),
            ("Salil Parekh", f"Page {pno + 1} remarks: revenue grew 4.2% in constant currency."),
            ("Analyst One", "What about margins?"),
            ("Jayesh Sanghrajka", "Margin was 21.1%, up 50 basis points."),
        ]:
            page.insert_text((50, y), name, fontname="hebo", fontsize=10)  # Helvetica-Bold
            y += 14
            page.insert_text((50, y), text, fontname="helv", fontsize=10)
            y += 22
        page.insert_text((250, 800), f"Page {pno + 1} of 3", fontname="helv", fontsize=8)  # footer
    doc.save(path)
    doc.close()
    return path


class TestPdf:
    def test_pdf_speakers_pages_and_footer_removal(self, sample_pdf):
        doc = parse_document(sample_pdf)
        assert doc.total_pages == 3
        turns = [e for e in doc.elements if e.kind == "speaker_turn"]
        assert {e.speaker for e in turns} == {"Moderator", "Salil Parekh", "Analyst One", "Jayesh Sanghrajka"}
        assert {e.page for e in turns} == {1, 2, 3}
        assert not any(re.match(r"Page \d+ of 3", e.text) for e in doc.elements), "running footer removed"
        chunks = chunk_elements(doc.elements)
        assert coverage(doc.elements, chunks)[1] == []

    def test_unsupported_and_missing(self, tmp_path):
        assert parse_document(tmp_path / "nope.pdf").elements == []
