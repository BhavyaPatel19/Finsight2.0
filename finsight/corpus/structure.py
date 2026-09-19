"""Document-level structure decisions shared by the PDF and HTML parsers."""

from __future__ import annotations

from collections import Counter

from finsight.corpus.elements import Element

MIN_DISTINCT = 3  # at least this many distinct labels …
MIN_REPEATING = 2  # … of which at least this many open ≥2 turns → the document is a dialogue


def finalize_speakers(elements: list[Element], labels: list[tuple[str, int, int]]) -> list[Element]:
    """
    `labels` = (label_text, page, order_before_which_it_appeared) for every
    bold short line that *looked* like a speaker. If the document is not a
    transcript by the gate above, speaker tags are cleared and the labels are
    restored as headings (they were section titles all along).
    """
    # A "turn" is a change of speaker in document order; a label that only ever
    # heads one block of text (a section title in a press release) has one turn.
    turns_per_speaker: Counter[str] = Counter()
    prev = None
    for el in elements:
        if not el.speaker:
            continue  # table rows and headings carry no speaker and do not end a turn
        if el.speaker != prev:
            turns_per_speaker[el.speaker] += 1
        prev = el.speaker
    repeating = sum(1 for n in turns_per_speaker.values() if n >= 2)
    is_transcript = len(turns_per_speaker) >= MIN_DISTINCT and repeating >= MIN_REPEATING
    if is_transcript:
        return elements

    section = None
    out: list[Element] = []
    by_order = {order: (label, page) for label, page, order in labels}
    for el in elements:
        if el.order in by_order:
            label, page = by_order[el.order]
            section = label
            out.append(Element(kind="heading", text=label, order=len(out), page=page, section=None))
        if el.kind == "speaker_turn":
            el.kind = "paragraph"
        el.speaker = None
        if el.section is None and section:
            el.section = section
        el.order = len(out)
        out.append(el)
    return out
