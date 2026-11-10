"""
List candidate Walk-the-Talk claims in the test-set transcripts (eval/gold/LABELLING.md §6, step 1).

A candidate is a sentence spoken by management (a speaker whose surname is in the transcript's
own "Management" list) that contains a forward-looking cue. This is a recall-oriented first pass
done without the system: a labeller then reads each candidate in context and keeps the ones that
meet LABELLING.md §2. Pages are physical PDF pages, 1-based.

    uv run python -m eval.gold.enumerate_claims            # counts per transcript
    uv run python -m eval.gold.enumerate_claims LT_concall_Q4FY25   # candidates for one transcript
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "eval" / "gold" / "documents_multi.json"
TEXT = ROOT / "eval" / ".cache" / "text"

CUE = re.compile(
    r"\b(expect\w*|guidance|guid(e|ing)|target\w*|aim\w*|anticipat\w*|outlook|plan(ned|ning)? to|intend\w*|"
    r"going forward|on track|will be|would be|should be|we will|we'll|we would|we should|commission\w*|"
    r"by (the )?(end of )?(FY|March|this year|next year|H1|H2|Q[1-4])|next (year|quarter|financial year)|"
    r"FY\s?'?2[5-9]|range of|estimate\w*|commit\w*)\b",
    re.I,
)
SPEAKER = re.compile(r"^\s*((?:Mr\.|Ms\.|Dr\.)?\s*[A-Z][A-Za-z.\- ]{1,40}?)\s*:\s*(.*)$")
# Management speakers per company, from each transcript's own participant list (page 1). Anyone
# else who speaks (analysts, unlisted staff) is excluded, so an analyst's view can't become a claim.
MANAGEMENT = {
    "LT": {"ramakrishnan", "sarma", "raman"},
    "BAJFINANCE": {"jain", "saha"},
    "ULTRACEMCO": {"daga", "jhanwar"},
    "INDIGO": {"elbers", "negi", "walsh", "bhatia"},
}


def page_texts(entry: dict) -> list[dict]:
    out = TEXT / f"{entry['key']}.json"
    if out.exists():
        return json.loads(out.read_text())
    doc = pymupdf.open(ROOT / "documents" / entry["file"])
    pages = [{"page": i + 1, "text": pg.get_text()} for i, pg in enumerate(doc)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pages, ensure_ascii=False))
    return pages


def is_speaker_line(name: str, known: set[str]) -> bool:
    """A "Name:" line starts a new turn if it is a known speaker or looks like a person's name;
    section headings inside a speech ("Coming to Revenues:", "Infrastructure:") do not."""
    words = name.replace("Mr.", "").replace("Ms.", "").replace("Dr.", "").split()
    if not words:
        return False
    if name.strip().lower() == "moderator" or words[-1].strip(".").lower() in known:
        return True
    return 2 <= len(words) <= 4 and all(w[0].isupper() for w in words) and not name.isupper()


def turns(pages: list[dict], known: set[str]) -> list[tuple[str, list[tuple[int, str]]]]:
    """(speaker, [(page, line), ...]) for each run of lines by one speaker."""
    out: list[tuple[str, list[tuple[int, str]]]] = []
    speaker, lines = "", []
    for p in pages:
        for line in p["text"].splitlines():
            m = SPEAKER.match(line)
            if m and is_speaker_line(m.group(1), known):
                if lines:
                    out.append((speaker, lines))
                speaker = "Moderator" if m.group(1).strip().lower() == "moderator" else m.group(1).strip()
                lines = [(p["page"], m.group(2).strip())] if m.group(2).strip() else []
            elif line.strip():
                lines.append((p["page"], line.strip()))
    if lines:
        out.append((speaker, lines))
    return out


def sentences_with_pages(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Split a turn into sentences, each tagged with the page it starts on."""
    text, starts = "", []
    for page, line in lines:
        starts.append((len(text), page))
        text += line + " "
    text = re.sub(r"\s+", " ", text)
    out, pos = [], 0
    for sent in re.split(r"(?<=[.?!])\s+(?=[A-Z])", text):
        page = max((pg for off, pg in starts if off <= pos), default=lines[0][0])
        out.append((page, sent.strip()))
        pos += len(sent) + 1
    return out


def candidates(entry: dict) -> list[dict]:
    mgmt = MANAGEMENT[entry["symbol"]]
    found = []
    for speaker, lines in turns(page_texts(entry), mgmt):
        if speaker.split()[-1].strip(".").lower() not in mgmt if speaker else True:
            continue
        for page, sent in sentences_with_pages(lines):
            if 40 <= len(sent) <= 600 and CUE.search(sent) and re.search(r"\d|commission|complet|launch", sent, re.I):
                found.append({"doc": entry["key"], "page": page, "speaker": speaker, "sentence": sent})
    return found


def main() -> None:
    docs = json.loads(MANIFEST.read_text())["documents"]
    if len(sys.argv) > 1:
        entry = next(d for d in docs if d["key"] == sys.argv[1])
        print(json.dumps(candidates(entry), indent=1, ensure_ascii=False))
        return
    for d in docs:
        tl = turns(page_texts(d), MANAGEMENT[d["symbol"]])
        mgmt = sorted({sp for sp, _ in tl if sp and sp.split()[-1].strip(".").lower() in MANAGEMENT[d["symbol"]]})
        print(f"{d['key']:28s} candidates={len(candidates(d)):3d}  management speaking={mgmt}")


if __name__ == "__main__":
    main()
