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


def _draw_grid(page, x0: float, y0: float, rows: list[list[str]], col_w: float = 110, row_h: float = 18) -> None:
    """A ruled table PyMuPDF's find_tables recognises: one rectangle per cell, text inside."""
    for r, cells in enumerate(rows):
        for c, txt in enumerate(cells):
            rect = (x0 + c * col_w, y0 + r * row_h, x0 + (c + 1) * col_w, y0 + (r + 1) * row_h)
            page.draw_rect(rect, width=0.5)
            page.insert_text((rect[0] + 3, rect[1] + 13), txt, fontname="helv", fontsize=8)


class TestPdfTablesAcrossPages:
    def test_header_carries_to_the_continuation_page(self, tmp_path):
        """EDGAR press releases put the income statement's header row at the foot of one
        page and every data row at the top of the next; without the carry-over each row
        read 'Gross profit | 1,428 | 1,345 | 5,872 | 5,587' with no idea which figure
        was the quarter and which the year."""
        import fitz

        from finsight.corpus.chunker import chunk_elements, verbalize_row

        path = tmp_path / "press.pdf"
        doc = fitz.open()
        p1 = doc.new_page()  # 842pt high: header table at the very bottom
        p1.insert_text(
            (40, 735), "Extracted from the Statement of Comprehensive Income for:", fontname="helv", fontsize=9
        )
        _draw_grid(p1, 40, 745, [["", "3 months ended March 31, 2025", "Year ended March 31, 2025"]], col_w=170)
        p2 = doc.new_page()
        _draw_grid(p2, 40, 30, [["Revenues", "4,730", "19,277"], ["Gross profit", "1,428", "5,872"]], col_w=170)
        doc.save(path)
        doc.close()

        parsed = parse_document(path)
        rows = [e for e in parsed.elements if e.kind == "table_row"]
        assert [r.text.split(" | ")[0] for r in rows] == ["Revenues", "Gross profit"]
        assert all(r.page == 2 for r in rows)
        assert rows[1].table_header == ["", "3 months ended March 31, 2025", "Year ended March 31, 2025"]
        assert rows[1].table_title and rows[1].table_title.startswith("Extracted from the Statement")
        v = verbalize_row(rows[1])
        assert "3 months ended March 31, 2025 = 1,428" in v and "Year ended March 31, 2025 = 5,872" in v

        chunks = chunk_elements(parsed.elements)
        row = next(c for c in chunks if c.kind == "row" and c.text.startswith("Gross profit"))
        table = next(c for c in chunks if c.kind == "table")
        assert row.text == "Gross profit | 1,428 | 5,872", "verbatim text is untouched (citations)"
        assert row.display_text == v, "the answerer sees the verbalised form"
        assert table.display_text and "Revenues: 3 months ended March 31, 2025 = 4,730" in table.display_text


class TestIndianIrTranscripts:
    """Tata Steel's transcripts label speakers as 'Name: Role – Company' or 'Name, Firm' in bold,
    and PyMuPDF often glues the label onto the end of the previous speaker's block."""

    def test_role_and_firm_labels_and_mid_block_split(self, tmp_path):
        import fitz

        path = tmp_path / "ts.pdf"
        doc = fitz.open()
        page = doc.new_page()
        y = 80
        page.insert_text((40, y), "Operator:", fontname="hebo", fontsize=10)
        y += 14
        page.insert_text(
            (40, y), "Ladies and gentlemen, welcome to the Tata Steel analyst call.", fontname="helv", fontsize=10
        )
        y += 14  # label immediately after the text: same block in the text layer
        page.insert_text((40, y), "Koushik Chatterjee: ED & CFO - Tata Steel Limited", fontname="hebo", fontsize=10)
        y += 14
        page.insert_text(
            (40, y),
            "Thank you, Naren. Consolidated EBITDA was Rs 6,762 crores for the quarter.",
            fontname="helv",
            fontsize=10,
        )
        y += 14
        page.insert_text((40, y), "Amit Dixit, ICICI Securities", fontname="hebo", fontsize=10)
        y += 14
        page.insert_text(
            (40, y), "Could you tell us the volume guidance for India for FY2026?", fontname="helv", fontsize=10
        )
        y += 14
        page.insert_text((40, y), "Koushik Chatterjee: ED & CFO - Tata Steel Limited", fontname="hebo", fontsize=10)
        y += 14
        page.insert_text(
            (40, y),
            "We expect about 1.5 million tonnes of incremental volume from Kalinganagar.",
            fontname="helv",
            fontsize=10,
        )
        y += 14
        page.insert_text((40, y), "Operator:", fontname="hebo", fontsize=10)
        y += 14
        page.insert_text((40, y), "Thank you. That concludes the call.", fontname="helv", fontsize=10)
        doc.save(path)
        doc.close()

        parsed = parse_document(path)
        turns = [(e.speaker, e.text) for e in parsed.elements if e.kind == "speaker_turn"]
        assert [s for s, _ in turns] == [
            "Operator",
            "Koushik Chatterjee",
            "Amit Dixit",
            "Koushik Chatterjee",
            "Operator",
        ]
        assert turns[1][1].startswith("Thank you, Naren.") and turns[2][1].startswith("Could you tell us")
        assert not any("ED & CFO" in t for _, t in turns), "the role on the label line is not part of the turn"

    def test_report_captions_are_not_speakers(self):
        from finsight.corpus.parse_pdf import _label_name

        assert _label_name("Koushik Chatterjee: ED & CFO – Tata Steel Limited") == "Koushik Chatterjee"
        assert _label_name("Amit Dixit, ICICI Securities") == "Amit Dixit"
        assert _label_name("Operator:") == "Operator"
        assert _label_name("Salil Parekh") == "Salil Parekh"
        for caption in ("NOTES", "Amount", "Total", "CORPORATE PARTICIPANTS", "Deferred tax:"):
            assert _label_name(caption) is None, caption

    def test_dialogue_gate_rejects_a_report_sized_cast(self):
        from finsight.corpus.elements import Element
        from finsight.corpus.structure import finalize_speakers

        # 80 distinct bold Title-Case captions, each heading two blocks: an annual report, not a call
        els, labels = [], []
        for i in range(80):
            name = f"Caption Number{i}"
            labels.append((name, 1, len(els)))
            for _ in range(2):
                els.append(Element(kind="speaker_turn", text=f"text {i}", order=len(els), page=1, speaker=name))
        out = finalize_speakers(els, labels)
        assert not any(e.speaker for e in out) and sum(1 for e in out if e.kind == "heading") == 80


def test_page_number_folded_into_a_paragraph_block_is_dropped(tmp_path):
    """The footer number sits in the same PyMuPDF block as a paragraph that runs to the page
    bottom; it must not end up inside the sentence."""
    import fitz

    path = tmp_path / "num.pdf"
    doc = fitz.open()
    for pno, site in enumerate(("Port Talbot", "IJmuiden", "Kalinganagar")):
        page = doc.new_page()  # 842 pt high
        page.insert_text((40, 60), f"Remarks on {site}", fontname="hebo", fontsize=10)
        page.insert_text((40, 790), f"The BF#5 at {site} produced its last", fontname="helv", fontsize=10)
        page.insert_text(
            (40, 803),
            "liquid steel on 04th July and one of the two furnaces is now closed.",
            fontname="helv",
            fontsize=10,
        )
        page.insert_text((540, 803), str(pno + 1), fontname="helv", fontsize=10)  # footer number, same band
    doc.save(path)
    doc.close()

    parsed = parse_document(path)
    text = " ".join(e.text for e in parsed.elements)
    assert "produced its last liquid steel" in text
    assert not re.search(r"last \d liquid|\b[123] The BF", text)
