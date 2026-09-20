"""
Lossless, structure-aware chunking.

Invariant (tested): every element's text appears verbatim in at least one
chunk. Prose is split at sentence boundaries with one sentence of overlap;
table rows become one chunk each (plus grouped table chunks for context);
speaker turns never merge across speakers.

Two texts per chunk:
    text        verbatim source — what the user sees and what citations quote
    index_text  context lines + text — what the embedder, BM25 and reranker see
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from finsight.corpus.elements import Element

MAX_CHARS = 1200  # prose chunk target
MIN_CHARS = 300  # merge short paragraphs up to at least this
TABLE_GROUP_ROWS = 12
QUESTION_MAX_CHARS = 500  # a turn this short before an answer is treated as the question it answers

# Sentence boundary: terminal punctuation followed by whitespace and an upper-case/quote/digit start,
# not after common financial abbreviations.
_ABBREVS = [
    "Rs",
    "Mr",
    "Ms",
    "Mrs",
    "Dr",
    "vs",
    "No",
    "Inc",
    "Ltd",
    "Cr",
    "bn",
    "mn",
    "approx",
    "St",
    "Jr",
    "Sr",
    "Co",
    "e.g",
    "i.e",
]
_ABBREV = "".join(rf"(?<!\b{re.escape(a)}\.)" for a in _ABBREVS)
_SENT = re.compile(_ABBREV + r"(?<=[.!?])\s+(?=[A-Z\"'“(\d])")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT.split(text) if p and p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


@dataclass
class Chunk:
    text: str
    index_text: str
    kind: str  # prose | row | table
    page: int
    section: str | None = None
    speaker: str | None = None
    element_orders: list[int] = field(default_factory=list)
    sentences: list[str] = field(default_factory=list)
    chunk_index: int = -1


def verbalize_row(el: Element) -> str:
    """'Financial services | 28.4 | 27.8' + header → 'Financial services: Mar 31, 2025 = 28.4; Dec 31, 2024 = 27.8'.
    Pairing each value with its column header is what makes a table row match a question."""
    cells = [c.strip() for c in el.text.split(" | ")]
    header = [h.strip() for h in (el.table_header or [])]
    if len(cells) < 2:
        return el.text
    label, values = cells[0], cells[1:]
    cols = [h for h in header if h] if header else []
    if cols and len(cols) == len(cells):  # header includes a label column
        cols = cols[1:]
    if cols and len(cols) >= len(values):
        pairs = "; ".join(f"{c} = {v}" for c, v in zip(cols, values, strict=False))
    else:
        pairs = "; ".join(values)
    prefix = " — ".join(x for x in (el.table_title, el.table_group) if x)
    return f"{prefix} — {label}: {pairs}" if prefix else f"{label}: {pairs}"


def _with_context(header: str, context: str | None, text: str) -> str:
    lines = [header] if header else []
    if context:
        lines.append(context)
    lines.append(text)
    return "\n".join(lines)


def chunk_elements(elements: list[Element], header: str = "", max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []

    def emit(
        text: str,
        kind: str,
        first: Element,
        orders: list[int],
        sentences: list[str],
        context: str | None,
        index_body: str | None = None,
    ) -> None:
        sec = f"{first.section}" if first.section else None
        ctx_lines = [x for x in (sec, context) if x]
        chunks.append(
            Chunk(
                text=text,
                index_text=_with_context(header, "\n".join(ctx_lines) or None, index_body or text),
                kind=kind,
                page=first.page,
                section=first.section,
                speaker=first.speaker,
                element_orders=orders,
                sentences=sentences,
            )
        )

    # ---- prose runs: consecutive paragraph/speaker_turn/heading elements with the same speaker ----
    i = 0
    n = len(elements)
    last_question: str | None = None  # short preceding turn by another speaker (an analyst's question)
    while i < n:
        el = elements[i]
        if el.kind == "table_row":
            # a table: collect the whole run of rows from this table
            j = i
            rows: list[Element] = []
            while j < n and elements[j].kind == "table_row" and elements[j].table_id == el.table_id:
                rows.append(elements[j])
                j += 1
            for r in rows:
                # verbatim text for citations; the verbalised form (header:value pairs) is what gets indexed
                emit(r.text, "row", r, [r.order], [r.text], None, index_body=verbalize_row(r))
            for k in range(0, len(rows), TABLE_GROUP_ROWS):
                grp = rows[k : k + TABLE_GROUP_ROWS]
                text = "\n".join(r.text for r in grp)
                emit(text, "table", grp[0], [r.order for r in grp], [r.text for r in grp], grp[0].context_line)
            i = j
            continue

        # prose run
        j = i
        run: list[Element] = []
        while (
            j < n
            and elements[j].kind != "table_row"
            and elements[j].speaker == el.speaker
            and elements[j].section == el.section
        ):
            run.append(elements[j])
            j += 1
        question_ctx = last_question if run and run[0].kind == "speaker_turn" else None
        _emit_prose_run(run, max_chars, emit, question_ctx)
        run_text = " ".join(e.text for e in run)
        if run and run[0].kind == "speaker_turn" and len(run_text) <= QUESTION_MAX_CHARS:
            last_question = f"{run[0].speaker}: {run_text}" if run[0].speaker else run_text
        else:
            last_question = None
        i = j

    for idx, c in enumerate(chunks):
        c.chunk_index = idx
    return chunks


def _emit_prose_run(run: list[Element], max_chars: int, emit, question_ctx: str | None = None) -> None:
    """Pack a run of same-speaker prose into sentence-bounded chunks with one-sentence overlap."""
    sents: list[tuple[str, Element]] = []
    for el in run:
        for s in split_sentences(el.text):
            sents.append((s, el))
    if not sents:
        return
    context = run[0].context_line if run[0].kind == "speaker_turn" else None
    if question_ctx and run[0].kind == "speaker_turn" and question_ctx.split(":")[0] != run[0].speaker:
        context = f"[in reply to] {question_ctx}\n{context}" if context else f"[in reply to] {question_ctx}"

    start = 0
    while start < len(sents):
        size = 0
        end = start
        while end < len(sents) and (size + len(sents[end][0]) <= max_chars or end == start):
            size += len(sents[end][0]) + 1
            end += 1
        piece = sents[start:end]
        text = " ".join(s for s, _ in piece)
        orders = sorted({el.order for _, el in piece})
        emit(text, "prose", piece[0][1], orders, [s for s, _ in piece], context)
        if end >= len(sents):
            break
        start = end - 1 if end - 1 > start else end  # one-sentence overlap


def coverage(elements: list[Element], chunks: list[Chunk]) -> tuple[int, list[Element]]:
    """(#elements fully covered, elements whose text is not verbatim inside any chunk)."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    joined = [norm(c.text) for c in chunks]
    missing = []
    for el in elements:
        t = norm(el.text)
        # a long paragraph may be split across chunks at sentence boundaries; require every sentence present
        ok = all(any(norm(s) in j for j in joined) for s in split_sentences(t))
        if not ok:
            missing.append(el)
    return len(elements) - len(missing), missing
