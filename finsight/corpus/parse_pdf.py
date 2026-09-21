"""
PDF filings → elements via PyMuPDF.

- Tables via `find_tables()`, with multi-row headers merged per column, one
  element per data row (title = nearest preceding short line).
- Text blocks outside table boxes via `get_text("dict")`, so font flags are
  available: a short, all-bold, Title-Case line on its own is a speaker
  label (transcripts) or, if larger than body text / ending with ":", a heading.
- Repeated lines at the top/bottom of pages (running headers, "Page x of y")
  are dropped; hyphenated line breaks are joined; "1." markers are merged
  with the remark that follows.
- Real page numbers; sections from bookmarks when present, else headings.
"""

from __future__ import annotations

import re
from collections import Counter

from finsight.corpus.elements import Element, ParsedDocument
from finsight.corpus.parse_html import _clean, _is_numeric_cell, _split_header_rows
from finsight.corpus.structure import finalize_speakers

_MARKER = re.compile(r"^(\d{1,2}[.)]|[-•·▪o§])$")
_SPEAKER_TEXT = re.compile(r"^[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,3}$")
# "Koushik Chatterjee: ED & CFO – Tata Steel Limited" / "Amit Dixit: ICICI Securities" / "Operator:" — a bold
# label line carrying the name, a colon and optionally the speaker's role or firm (Indian IR transcripts)
# "Name: role", "Name, Firm" (analysts) or "Name:" — the separator after the name is a colon or a comma
_SPEAKER_LABEL = re.compile(
    r"^(?P<name>[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,3}|Moderator|Operator|Host)\s*[:,](?:\s*(?P<role>[^:]{0,90}))?$"
)


def _label_name(text: str) -> str | None:
    """The speaker a bold label line names, or None ("CORPORATE PARTICIPANTS" is a heading, not a person)."""
    if text.isupper() and len(text) > 1:
        return None  # "NOTES", "CORPORATE PARTICIPANTS"
    if _SPEAKER_TEXT.match(text) and (" " in text or text in ("Moderator", "Operator", "Host")):
        return text  # people have two names; "Amount" / "Total" are table captions
    m = _SPEAKER_LABEL.match(text)
    return m.group("name") if m else None


_SPEAKER_COLON = re.compile(
    r"^(?P<name>[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,3}|Moderator|Operator|Host)\s*:\s*(?P<rest>.+)$", re.S
)
_PAGE_NO = re.compile(r"^(page\s*)?\d+(\s*(of|/)\s*\d+)?$", re.I)
_EDGE = 0.08  # top/bottom band (fraction of page height) where running headers/footers live
_PAGE_NO_BAND = 0.15  # a bare number this close to the top or bottom edge is a page number, not content


def _is_bold(span: dict) -> bool:
    return bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower()


def _block_text(block: dict, page_height: float | None = None) -> str:
    """The block's lines joined, minus a page number PyMuPDF folded into the block: a paragraph
    that continues across the page break often shares its block with the footer number, which
    would otherwise land inside the sentence ("produced its last 4 liquid steel")."""
    lines = []
    for line in block.get("lines", []):
        t = "".join(s["text"] for s in line["spans"])
        if page_height and _PAGE_NO.match(t.strip()) and not re.fullmatch(r"\d{4}", t.strip()):  # a year is content
            y0, y1 = line["bbox"][1], line["bbox"][3]
            if y0 < page_height * _PAGE_NO_BAND or y1 > page_height * (1 - _PAGE_NO_BAND):
                continue
        lines.append(t)
    text = "\n".join(lines)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # hyphenated line break
    return _clean(text)


def _running_lines(doc, page_count: int) -> set[str]:
    """Lines that repeat near the top/bottom of many pages: headers, footers, page numbers."""
    if page_count < 3:
        return set()
    counts: Counter[str] = Counter()
    for page in doc:
        h = page.rect.height
        for block in page.get_text("dict")["blocks"]:
            y0, y1 = block["bbox"][1], block["bbox"][3]
            if y0 < h * _EDGE or y1 > h * (1 - _EDGE):
                t = _clean(_block_text(block, h))
                if t and len(t) < 120:
                    counts[re.sub(r"\d+", "#", t)] += 1
    return {t for t, n in counts.items() if n >= max(2, page_count * 0.4)}


def _outline_sections(doc) -> list[tuple[int, str]]:
    return sorted((page, _clean(title)) for level, title, page in (doc.get_toc() or []) if level <= 2 and page > 0)


def _push_short(state: dict, value: str) -> None:
    """Remember the last two short lines before a table: a title and, often, a units line."""
    if value != state.get("last_short"):
        state["prev_short"] = state.get("last_short")
        state["last_short"] = value


def _table_title(state: dict) -> str | None:
    last, prev = state.get("last_short"), state.get("prev_short")
    units = last and (last.startswith("(") or last.lower().startswith("in ") or len(last) < 12)
    if last and prev and units:
        return f"{prev} {last}"
    return last


def parse_pdf(path: str) -> ParsedDocument:
    import fitz

    doc = fitz.open(path)
    n_pages = len(doc)
    running = _running_lines(doc, n_pages)
    outline = _outline_sections(doc)
    elements: list[Element] = []
    labels: list[tuple[str, int, int]] = []  # (label, page, order of the next element)
    state = {
        "speaker": None,
        "section": None,
        "last_short": None,
        "prev_short": None,
        "table_id": 0,
        "pending_marker": None,
        "carry": None,  # header of a table that may continue on the next page
    }

    def section_for(page: int) -> str | None:
        current = state["section"]
        for start, title in outline:
            if start <= page:
                current = title
        return current

    def add(kind: str, text: str, page: int, **kw) -> None:
        text = _clean(text)
        if not text:
            return
        if state["pending_marker"] and kind in ("paragraph", "speaker_turn"):
            text = f"{state['pending_marker']} {text}"
            state["pending_marker"] = None
        elements.append(Element(kind=kind, text=text, order=len(elements), page=page, section=section_for(page), **kw))

    for pno in range(n_pages):
        page = doc[pno]
        pg = pno + 1
        h = page.rect.height
        table_boxes = []
        text_blocks = [b for b in page.get_text("dict")["blocks"] if b.get("type", 0) == 0]

        def title_above(bbox, text_blocks=text_blocks, table_boxes=table_boxes, h=h) -> str | None:
            """Up to two short text lines directly above the table: a title and often a units line."""
            x0, y0, x1, _ = bbox
            cands = []
            for b in text_blocks:
                bx0, by0, bx1, by1 = b["bbox"]
                if by1 <= y0 + 2 and y0 - by1 < 70 and bx1 > x0 and bx0 < x1:
                    own = fitz.Rect(bbox)
                    if any(tb != own and fitz.Rect(b["bbox"]).intersects(tb) for tb in table_boxes):
                        continue  # a row of the table above, not a title
                    t = _block_text(b, h)
                    if t and len(t) < 120 and not _MARKER.match(t):
                        cands.append((by1, t))
            cands.sort(reverse=True)
            picked = [t for _, t in cands[:2]]
            return " ".join(reversed(picked)).rstrip(":") if picked else None

        try:
            for t in page.find_tables().tables:
                rows = [[_clean(c or "") for c in r] for r in t.extract()]
                rows = [r for r in rows if any(c for c in r)]
                if not rows or max(len([c for c in r if c]) for r in rows) < 2:
                    continue
                width = max(len(r) for r in rows)
                header, data_rows = _split_header_rows(rows)
                carry = state["carry"]
                if not data_rows:
                    # Header-only table (the body starts on the next page): remember it, emit nothing.
                    table_boxes.append(fitz.Rect(t.bbox))
                    state["carry"] = {"header": header, "width": width, "title": title_above(t.bbox), "page": pg}
                    continue
                if len(rows) < 2:
                    continue
                table_boxes.append(fitz.Rect(t.bbox))
                state["table_id"] += 1
                title = title_above(t.bbox)
                if (
                    not header
                    and carry
                    and carry["page"] == pg - 1
                    and carry["width"] == width
                    and t.bbox[1] < h * 0.15
                    and (title is None or not any(_is_numeric_cell(c) for c in rows[0] if c))
                ):
                    # Continuation of the previous page's table: reuse its column headers and title.
                    header, title = carry["header"], title or carry["title"]
                state["carry"] = (
                    {"header": header, "width": width, "title": title, "page": pg}
                    if header and t.bbox[3] > h * 0.8
                    else None
                )
                group = None
                for r in data_rows:
                    cells = [c for c in r if c]
                    if len(cells) == 1 and not _is_numeric_cell(cells[0]):
                        group = cells[0].rstrip(":")
                        continue
                    add(
                        "table_row",
                        " | ".join(cells),
                        pg,
                        table_id=state["table_id"],
                        table_title=title,
                        table_group=group,
                        table_header=header,
                    )
        except Exception:  # find_tables is best-effort across versions/layouts
            pass

        blocks = text_blocks
        sizes = [s["size"] for b in blocks for line in b.get("lines", []) for s in line["spans"] if s["text"].strip()]
        body_size = sorted(sizes)[len(sizes) // 2] if sizes else 10.0

        for block in blocks:
            if block.get("type", 0) != 0:
                continue
            x0, y0, x1, y1 = block["bbox"]
            if any(fitz.Rect(x0, y0, x1, y1).intersects(tb) for tb in table_boxes):
                continue
            text = _block_text(block, h)
            if not text:
                continue
            if (y0 < h * _EDGE or y1 > h * (1 - _EDGE)) and (
                re.sub(r"\d+", "#", text) in running or _PAGE_NO.match(text)
            ):
                continue
            spans = [s for line in block.get("lines", []) for s in line["spans"] if s["text"].strip()]
            all_bold = bool(spans) and all(_is_bold(s) for s in spans)
            max_size = max((s["size"] for s in spans), default=body_size)
            lines = block.get("lines", [])
            single_line = len(lines) == 1

            # A bold label line anywhere in the block ("Koushik Chatterjee: ED & CFO – …" as the last line of the
            # previous speaker's block is how some transcripts come out of the PDF): split the block there.
            if len(lines) > 1:
                cuts = []
                for li, line in enumerate(lines):
                    ls = [s for s in line["spans"] if s["text"].strip()]
                    lt = _clean("".join(s["text"] for s in ls))
                    if ls and all(_is_bold(s) for s in ls) and lt and len(lt) <= 100 and _label_name(lt):
                        cuts.append((li, _label_name(lt)))
                if cuts:
                    start = 0
                    for li, name in cuts:
                        seg = _clean("\n".join("".join(s["text"] for s in line["spans"]) for line in lines[start:li]))
                        if seg:
                            add("speaker_turn" if state["speaker"] else "paragraph", seg, pg, speaker=state["speaker"])
                        state["speaker"] = name
                        _push_short(state, name)
                        labels.append((name, pg, len(elements)))
                        start = li + 1
                    tail = _clean("\n".join("".join(s["text"] for s in line["spans"]) for line in lines[start:]))
                    if tail:
                        add("speaker_turn", tail, pg, speaker=state["speaker"])
                    continue

            # "Name" in bold on the first line, the turn's text on the following lines of the same block
            if len(lines) > 1:
                first = [s for s in lines[0]["spans"] if s["text"].strip()]
                rest = [s for line in lines[1:] for s in line["spans"] if s["text"].strip()]
                first_text = _clean("".join(s["text"] for s in first))
                name = _label_name(first_text) if first_text and len(first_text) <= 100 else None
                if first and all(_is_bold(s) for s in first) and rest and not all(_is_bold(s) for s in rest) and name:
                    state["speaker"] = name
                    _push_short(state, name)
                    labels.append((name, pg, len(elements)))
                    add(
                        "speaker_turn",
                        _clean("\n".join("".join(s["text"] for s in line["spans"]) for line in lines[1:])),
                        pg,
                        speaker=name,
                    )
                    continue

            if _MARKER.match(text):
                state["pending_marker"] = text
                continue
            m = _SPEAKER_COLON.match(text)
            if m and len(m.group("name")) <= 40 and (all_bold or single_line or len(text) < 200):
                state["speaker"] = m.group("name")
                _push_short(state, m.group("name"))
                add("speaker_turn", m.group("rest"), pg, speaker=state["speaker"])
                continue
            name = _label_name(text) if single_line and all_bold and len(text) <= 100 else None
            if name and not text.endswith((".", "?", "!")):
                state["speaker"] = name
                _push_short(state, name)
                labels.append((name, pg, len(elements)))
                continue
            is_heading = (
                all_bold and len(text) < 100 and (text.endswith(":") or text.isupper() or max_size > body_size * 1.15)
            ) or (len(text) < 80 and text.endswith(":"))
            if is_heading:
                state["section"] = text.rstrip(":")
                _push_short(state, text.rstrip(":"))
                add("heading", text, pg)
                continue
            if len(text) < 60:
                _push_short(state, text.rstrip(":"))
            add("speaker_turn" if state["speaker"] else "paragraph", text, pg, speaker=state["speaker"])

    doc.close()
    return ParsedDocument(elements=finalize_speakers(elements, labels), total_pages=n_pages)
