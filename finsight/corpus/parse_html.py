"""
HTML filings (SEC EDGAR exhibits, company IR pages) → elements.

Tables keep their title (nearest preceding short line), header rows and
in-table group labels; bold-only short paragraphs in transcripts are
speaker labels and tag every paragraph until the next label. Text is cut
into synthetic pages of ~3,000 characters so citations stay locatable.
"""

from __future__ import annotations

import re

from finsight.corpus.elements import Element, ParsedDocument
from finsight.corpus.structure import finalize_speakers

PAGE_CHARS = 3000
_SPEAKER_MAX = 60
_NUMERIC = re.compile(r"^[\s$₹€£(]*[-–]?[\d.,]+\s*%?[)\s]*$|^[-–—]$|^n/?a$", re.I)
_BULLET = re.compile(r"^[·•\-\*o§]$")


def _clean(text: str) -> str:
    text = re.sub(r"[ \t\xa0\r\f\v]+", " ", text)
    return re.sub(r"\s*\n\s*", " ", text).strip()


def _is_numeric_cell(cell: str) -> bool:
    return bool(_NUMERIC.match(cell.strip())) if cell.strip() else True


def _split_header_rows(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """Leading rows whose non-empty cells are all non-numeric are header rows
    (a spanning "Quarter ended" line, then the column dates); they are merged
    column-wise. A trailing single-cell header row is really a group label and
    is handed back to the data rows."""
    header_rows: list[list[str]] = []
    for row in rows:
        cells = [c for c in row if c.strip()]
        if not cells:
            continue
        if all(not _is_numeric_cell(c) for c in cells) and len(header_rows) < 3:
            header_rows.append(row)
        else:
            break
    if header_rows and len([c for c in header_rows[-1] if c.strip()]) == 1 and len(header_rows) > 1:
        header_rows.pop()
    if not header_rows:
        return [], rows
    width = max(len(r) for r in header_rows)
    merged = []
    for i in range(width):
        parts = [r[i].strip() for r in header_rows if i < len(r) and r[i].strip()]
        merged.append(" ".join(dict.fromkeys(parts)))
    # a spanning label in a single-cell row applies to every column
    spanning = [r for r in header_rows if len([c for c in r if c.strip()]) == 1]
    if spanning and width > 1:
        label = next(c for c in spanning[0] if c.strip())
        merged = [m if m else "" for m in merged]
        merged = [(f"{label} {m}".strip() if m and label not in m else m) for m in merged]
    data_start = rows.index(header_rows[-1]) + 1
    return merged, rows[data_start:]


def _looks_like_layout_table(rows: list[list[str]]) -> bool:
    """Press releases and transcripts use 1–2 column tables for layout (prose cells,
    or [marker, text] numbered remarks); treat those cells as prose, not data."""
    nonempty = [[c for c in r if c.strip()] for r in rows]
    nonempty = [r for r in nonempty if r]
    if not nonempty:
        return True
    if max(len(r) for r in nonempty) > 2:
        return False
    if all(len(r) == 2 and len(r[0]) <= 4 and len(r[1]) > 40 for r in nonempty):
        return True  # "1. | Revenues grew …"
    cells = [c for r in nonempty for c in r]
    return sum(len(c) for c in cells) / len(cells) > 60


def parse_html(raw: str, page_chars: int = PAGE_CHARS) -> ParsedDocument:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "head", "title"]):
        tag.decompose()

    elements: list[Element] = []
    labels: list[tuple[str, int, int]] = []
    state = {"section": None, "speaker": None, "last_short": None, "table_id": 0, "chars": 0, "page": 1}

    def add(kind: str, text: str, **kw) -> None:
        text = _clean(text)
        if not text:
            return
        el = Element(kind=kind, text=text, order=len(elements), page=state["page"], section=state["section"], **kw)
        elements.append(el)
        state["chars"] += len(text) + 2
        if state["chars"] >= page_chars and not text.endswith(":"):
            state["page"] += 1
            state["chars"] = 0

    body = soup.body or soup
    blocks = body.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "table"], recursive=True)
    for el in blocks:
        if el.name != "table" and el.find(["p", "div", "li", "table", "h1", "h2", "h3", "h4"]):
            continue
        if el.find_parent("table") and el.name != "table":
            continue

        if el.name == "table":
            rows: list[list[str]] = []
            for tr in el.find_all("tr"):
                cells = [_clean(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
                if any(cells):
                    rows.append(cells)
            if not rows:
                continue
            # Word-exported bullets: [glyph, text]
            if all(
                len([c for c in r if c]) == 2 and _BULLET.match([c for c in r if c][0] or "") for r in rows if any(r)
            ):
                for r in rows:
                    cells = [c for c in r if c]
                    if len(cells) == 2:
                        add("paragraph", "- " + cells[1], speaker=state["speaker"])
                continue
            if _looks_like_layout_table(rows):
                for r in rows:
                    cells = [c for c in r if c.strip()]
                    if len(cells) == 2 and len(cells[0]) <= 4:
                        add(
                            "speaker_turn" if state["speaker"] else "paragraph",
                            f"{cells[0]} {cells[1]}",
                            speaker=state["speaker"],
                        )
                    else:
                        for c in cells:
                            add("speaker_turn" if state["speaker"] else "paragraph", c, speaker=state["speaker"])
                continue
            state["table_id"] += 1
            title = state["last_short"]
            header, data_rows = _split_header_rows(rows)
            group = None
            for r in data_rows:
                cells = [c for c in r if c.strip()]
                if len(cells) == 1 and not _is_numeric_cell(cells[0]):
                    group = cells[0].rstrip(":")
                    continue
                add(
                    "table_row",
                    " | ".join(c for c in r if c.strip()),
                    table_id=state["table_id"],
                    table_title=title,
                    table_group=group,
                    table_header=header,
                )
            continue

        text = el.get_text(" ", strip=True)
        if not text:
            continue
        text = _clean(text)
        bold = el.find(["b", "strong"])
        bold_only = bold is not None and _clean(bold.get_text(" ", strip=True)) == text

        # "Salil Parekh" / "SALIL PAREKH:" — a bold, short, name-like line is a speaker candidate; the
        # document-level gate (structure.finalize_speakers) decides whether the document is a dialogue.
        name_like = (
            bool(re.match(r"^[A-Za-z][A-Za-z.'\-]*(?: [A-Za-z][A-Za-z.'\-]*){0,3}:?$", text))
            and len(text) <= _SPEAKER_MAX
        )
        if bold_only and name_like and el.name not in ("h1", "h2", "h3", "h4") and not text.endswith((".", "?", "!")):
            label = text.rstrip(":")
            state["speaker"] = label
            state["last_short"] = label
            labels.append((label, state["page"], len(elements)))
            continue
        if (
            el.name in ("h1", "h2", "h3", "h4")
            or (bold_only and text.endswith(":"))
            or (bold_only and text.isupper() and len(text) < 80)
        ):
            state["section"] = text.rstrip(":")
            state["last_short"] = text.rstrip(":")
            add("heading", text)
            continue
        if len(text) < 80 and text.endswith(":"):
            state["last_short"] = text.rstrip(":")
            add("heading", text)
            continue
        if len(text) < 60:
            state["last_short"] = text.rstrip(":")
        add("speaker_turn" if state["speaker"] else "paragraph", text, speaker=state["speaker"])

    return ParsedDocument(elements=finalize_speakers(elements, labels), total_pages=max(1, state["page"]))
