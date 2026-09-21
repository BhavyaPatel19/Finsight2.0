"""Parse health: the checks that flag a badly parsed document at ingestion."""

from finsight.corpus.chunker import chunk_elements
from finsight.corpus.elements import Element
from finsight.corpus.health import parse_health


def _el(kind, text, order, speaker=None, header=None):
    return Element(kind=kind, text=text, order=order, page=1, speaker=speaker, table_header=header or [])


def test_transcript_without_speakers_is_flagged():
    els = [_el("paragraph", f"Sentence number {i} about revenue and margins for the quarter.", i) for i in range(30)]
    h = parse_health("concall", els, chunk_elements(els))
    assert h["speakers"] == 0 and any(w.startswith("transcript_no_speakers") for w in h["warnings"])
    assert not h["ok"]


def test_healthy_transcript_passes():
    names = ["Operator", "Salil Parekh", "Jayesh Sanghrajka", "Analyst One"]
    els = [
        _el(
            "speaker_turn",
            f"Turn {i}: revenue grew and margins improved in the quarter under review.",
            i,
            speaker=names[i % 4],
        )
        for i in range(40)
    ]
    h = parse_health("concall", els, chunk_elements(els))
    assert h["ok"], h["warnings"]
    assert h["speakers"] == 4 and h["chunk_coverage"] == 1.0


def test_report_read_as_a_conversation_is_flagged():
    els = [_el("speaker_turn", f"Amount {i} for the year.", i, speaker=f"Caption {i % 50}") for i in range(200)]
    h = parse_health("annual_report", els, chunk_elements(els))
    assert any(w.startswith("non_transcript_with_speakers") for w in h["warnings"])


def test_headerless_tables_page_numbers_and_glued_digits():
    els = [
        _el("paragraph", "The BF#5 at Port Talbot produced its last 1 liquid steel on 04th July.", 0)
    ]  # page 1's number
    els += [_el("table_row", f"Revenues | {i},000 | {i},100", i + 1) for i in range(1, 7)]
    els += [_el("paragraph", "5", 8), _el("paragraph", "We expect the plant to produce 5 million tonnes a year.", 9)]
    h = parse_health("press_release", els, chunk_elements(els))
    w = " ".join(h["warnings"])
    assert "tables_without_headers: 6 of 6" in w
    assert "page_number_artifacts: 1" in w
    assert h["glued_digits"] == 1, "'last 4 liquid' counts, '5 million tonnes' does not"
