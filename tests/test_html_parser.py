"""HTML/text ingestion: paragraphs, speaker labels, tables, synthetic pages."""

from finsight.ingestion.html_parser import extract_structured_html, html_to_paragraphs, paginate
from finsight.ingestion.parsers import chunk_smart, extract_structured_document, is_concall_transcript

TRANSCRIPT = """
<html><body>
<p><b>Moderator</b></p>
<p>Welcome to the Q4 earnings call. Joining us is the CEO.</p>
<p><b>Salil Parekh</b></p>
<p>Thanks. Our guidance for growth for financial year '26 is 0% to 3%
in constant currency terms.</p>
<p>Our margin guidance for financial year 2026 is 20% to 22%.</p>
<p><b>Analyst One</b></p>
<p>What drove the margin?</p>
<p><b>Jayesh Sanghrajka</b></p>
<p>Value-based selling and utilisation.</p>
<p><b>Moderator</b></p>
<p>Thank you.</p>
<p><b>Salil Parekh</b></p>
<p>Closing remarks.</p>
</body></html>
"""

PRESS_RELEASE = """
<html><head><style>p{margin:0}</style><script>var x=1;</script></head><body>
<div><p>Infosys announces Q4 results</p></div>
<table>
<tr><td>·</td><td>Revenue grew 4.2% in constant currency</td></tr>
<tr><th>Metric</th><th>Q4 FY25</th><th>Q4 FY24</th></tr>
<tr><td>Revenue ($ mn)</td><td>4,730</td><td>4,564</td></tr>
</table>
<p>This sentence <b>has some bold</b> inside but is not a label.</p>
<p><b>SHORT BOLD.</b></p>
</body></html>
"""


class TestParagraphs:
    def test_speaker_labels_get_colons(self):
        paras = html_to_paragraphs(TRANSCRIPT)
        assert paras[0] == "Moderator:"
        assert paras[2] == "Salil Parekh:"
        assert "guidance for growth" in paras[3]
        assert "\n" not in paras[3], "line breaks inside a paragraph are joined"

    def test_tables_become_rows_and_bullets(self):
        paras = html_to_paragraphs(PRESS_RELEASE)
        assert "Infosys announces Q4 results" in paras
        assert "- Revenue grew 4.2% in constant currency" in paras
        assert "Metric | Q4 FY25 | Q4 FY24" in paras
        assert "Revenue ($ mn) | 4,730 | 4,564" in paras

    def test_script_and_style_dropped(self):
        text = " ".join(html_to_paragraphs(PRESS_RELEASE))
        assert "var x" not in text and "margin:0" not in text

    def test_inline_bold_and_sentence_bold_are_not_labels(self):
        paras = html_to_paragraphs(PRESS_RELEASE)
        assert "This sentence has some bold inside but is not a label." in paras
        assert "SHORT BOLD." in paras and "SHORT BOLD.:" not in paras


class TestPaginate:
    def test_pages_are_numbered_and_bounded(self):
        paras = [f"para {i} " + "x" * 400 for i in range(20)]
        pages = paginate(paras, page_chars=1000)
        assert [p["page"] for p in pages] == list(range(1, len(pages) + 1))
        assert all(len(p["text"]) <= 1000 + 410 for p in pages)  # one paragraph may overflow
        assert sum(p["text"].count("para ") for p in pages) == 20

    def test_speaker_label_stays_with_its_turn(self):
        paras = ["Moderator:", "a" * 900, "Salil Parekh:", "b" * 900]
        pages = paginate(paras, page_chars=1000)
        for p in pages:
            assert not p["text"].endswith(":"), "a page must not end on a dangling speaker label"


class TestDispatch:
    def test_html_file_goes_through_html_path_and_chunks_by_speaker(self, tmp_path):
        f = tmp_path / "call.htm"
        f.write_text(TRANSCRIPT)
        doc = extract_structured_document(f)
        assert doc["total_pages"] == 1 and doc["pages"][0]["page"] == 1
        assert is_concall_transcript(doc["pages"])
        chunks = chunk_smart(doc["pages"])
        assert chunks and all("chunk_index" in c for c in chunks)

    def test_txt_file(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("First para\nstill first.\n\nSecond para.")
        doc = extract_structured_html(f)
        assert doc["pages"][0]["text"] == "First para still first.\n\nSecond para."

    def test_missing_file(self, tmp_path):
        assert extract_structured_document(tmp_path / "nope.htm")["pages"] == []
