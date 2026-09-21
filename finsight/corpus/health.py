"""
Parse health: what a document looks like after parsing, and whether it looks wrong.

Computed at ingestion and stored on the Document, so a transcript whose speaker
labels were not recognised, a report whose tables lost their headers, or a PDF
whose page numbers ended up inside sentences is flagged the moment it is
uploaded — not discovered days later in an evaluation. Every check is a count
over the parsed elements; no model is involved and it runs in milliseconds.
"""

from __future__ import annotations

import re
from collections import Counter

from finsight.corpus.chunker import Chunk, coverage
from finsight.corpus.elements import Element

_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
# a small page-like number stuck between two words: "produced its last 4 liquid steel". A number
# followed by a unit or a plural noun ("25 years", "50 million", "18 countries") is content.
_GLUED = re.compile(
    r"[a-z,] (\d{1,2}) (?=[a-z])(?!(?:years?|months?|weeks?|days?|quarters?|million|billion|thousand|lakh|crore|"
    r"percent|per|bps|basis|tons?|tonnes?|mt|mtpa|countries|people|employees|customers|clients|deals?|"
    r"plants?|sites?|lines?|units?|projects?|furnaces?|mills?|x\b|times|hours?|minutes?|odd|more|less|new|large|"
    r"big|small|major|key|other|different|additional|such|of|in|each|out|mega|mn|bn|to|and|or)\b)"
)
_LEGIT_BEFORE = re.compile(
    r"(rs\.?|₹|\$|£|€|about|around|approx\w*|by|to|of|over|than|per|and|from|at|or|on|with|across|into|for|q|fy|phase|"
    r"tier|level|grade|stage|no\.?|number|section|page|slide|table|note|item|chapter|part|between|almost|nearly|only|"
    r"another|some|is|are|was|were|be|the|a|an|these|those|all|circa|c\.|~)$",
    re.I,
)

TRANSCRIPT_TYPES = {"concall", "transcript"}


def parse_health(doc_type: str | None, elements: list[Element], chunks: list[Chunk]) -> dict:
    kinds = Counter(e.kind for e in elements)
    speakers = Counter(e.speaker for e in elements if e.kind == "speaker_turn" and e.speaker)
    rows = [e for e in elements if e.kind == "table_row"]
    rows_without_header = sum(1 for e in rows if not e.table_header)
    page_number_elements = sum(1 for e in elements if _PAGE_NUMBER.match(e.text.strip()))
    glued = 0
    for e in elements:
        if e.kind not in ("paragraph", "speaker_turn"):
            continue
        for m in _GLUED.finditer(e.text):
            before = e.text[max(0, m.start() - 12) : m.start() + 1].strip().split()
            if before and _LEGIT_BEFORE.search(before[-1]):
                continue
            # a page number folded into a sentence is the page's own number (or its neighbour's)
            if int(m.group(1)) == e.page:
                glued += 1
    covered, missing = coverage(elements, chunks)
    cov = round(covered / len(elements), 4) if elements else 0.0

    warnings: list[str] = []
    is_transcript = (doc_type or "") in TRANSCRIPT_TYPES
    if not elements:
        warnings.append("no_text: nothing was extracted — a scanned PDF needs OCR")
    elif len(elements) < 20:
        warnings.append(f"little_text: only {len(elements)} elements — is this a scanned or image-only PDF?")
    if is_transcript and len(speakers) < 3:
        warnings.append(
            f"transcript_no_speakers: {len(speakers)} speaker(s) recognised — labels are not in a format the parser "
            "knows, so turns carry no speaker and Walk the Talk will see fewer commitments"
        )
    if not is_transcript and len(speakers) >= 3 and sum(speakers.values()) > 0.5 * max(1, len(elements)):
        warnings.append(
            f"non_transcript_with_speakers: {len(speakers)} 'speakers' in a {doc_type} — bold captions were read as people"
        )
    if rows and rows_without_header / len(rows) > 0.5:
        warnings.append(
            f"tables_without_headers: {rows_without_header} of {len(rows)} table rows have no column headers — "
            "figures will reach the model without their period or unit"
        )
    if page_number_elements:
        warnings.append(f"page_number_artifacts: {page_number_elements} bare page numbers survived as text")
    if glued:
        warnings.append(
            f"glued_digits: {glued} small numbers stuck between words — page numbers may sit inside sentences"
        )
    if cov < 1.0:
        warnings.append(f"incomplete_chunk_coverage: {len(missing)} elements are not verbatim in any chunk ({cov:.1%})")

    return {
        "elements": len(elements),
        "kinds": dict(kinds),
        "speakers": len(speakers),
        "turns": sum(speakers.values()),
        "table_rows": len(rows),
        "table_rows_without_header": rows_without_header,
        "page_number_elements": page_number_elements,
        "glued_digits": glued,
        "chunk_coverage": cov,
        "chunks": len(chunks),
        "warnings": warnings,
        "ok": not warnings,
    }
