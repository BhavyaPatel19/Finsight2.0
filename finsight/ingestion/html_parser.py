"""
HTML / plain-text ingestion.

Regulatory filings (e.g. SEC EDGAR 6-K exhibits) are HTML without page
markers. We flatten them to paragraphs, render bold-only paragraphs as
"Speaker:" lines so transcripts chunk by speaker turn, and cut the text into
synthetic ~3,000-character "pages" at paragraph boundaries so citations
stay locatable. `page` therefore means "segment" for these sources.
"""
from __future__ import annotations

import re
from pathlib import Path

HTML_PAGE_CHARS = 3000
_SPEAKER_MAX_LEN = 60


def html_to_paragraphs(raw: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "head", "title"]):
        tag.decompose()

    paragraphs: list[str] = []

    def emit(text: str) -> None:
        text = re.sub(r"[ \t\xa0\r\f\v]+", " ", text)
        text = re.sub(r"\s*\n\s*", " ", text).strip()
        if text:
            paragraphs.append(text)

    body = soup.body or soup
    for el in body.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "table"], recursive=True):
        # Only leaf-ish blocks: skip containers that hold other block elements.
        if el.name != "table" and el.find(["p", "div", "li", "table", "h1", "h2", "h3", "h4"]):
            continue
        if el.find_parent("table") and el.name != "table":
            continue  # cells are handled by the table branch
        if el.name == "table":
            for tr in el.find_all("tr"):
                cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
                cells = [c for c in cells if c]
                # Word-exported bullets are 2-col tables: [bullet glyph, text]
                if len(cells) >= 2 and re.fullmatch(r"[·•\-\*o§]", cells[0]):
                    emit("- " + " | ".join(cells[1:]))
                elif cells:
                    emit(" | ".join(cells))
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        # A short bold-only paragraph is a speaker label in transcripts.
        bold = el.find(["b", "strong"])
        if (
            bold is not None
            and bold.get_text(" ", strip=True) == text
            and len(text) <= _SPEAKER_MAX_LEN
            and not text.endswith((".", "?", "!", ":"))
            and re.match(r"^[A-Z][A-Za-z.'\- ]+$", text)
        ):
            text = f"{text}:"
        emit(text)
    return paragraphs


def paginate(paragraphs: list[str], page_chars: int = HTML_PAGE_CHARS) -> list[dict]:
    """Group paragraphs into synthetic pages of roughly page_chars characters."""
    pages: list[dict] = []
    buf: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal buf, size
        if buf:
            pages.append({"page": len(pages) + 1, "text": "\n\n".join(buf), "section": None, "sub_section": None})
        buf, size = [], 0

    for para in paragraphs:
        # Keep a speaker label with the paragraph that follows it.
        if buf and size + len(para) > page_chars and not buf[-1].endswith(":"):
            flush()
        buf.append(para)
        size += len(para) + 2
    flush()
    return pages


def extract_structured_html(path: str | Path, page_chars: int = HTML_PAGE_CHARS) -> dict:
    p = Path(path)
    if not p.exists():
        return {"toc": [], "pages": [], "sections": [], "total_pages": 0}
    raw = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in (".htm", ".html"):
        paragraphs = html_to_paragraphs(raw)
    else:  # plain text: blank-line separated paragraphs
        paragraphs = [re.sub(r"\s+", " ", para).strip() for para in re.split(r"\n\s*\n", raw) if para.strip()]
    pages = paginate(paragraphs, page_chars=page_chars)
    return {"toc": [], "pages": pages, "sections": [], "total_pages": len(pages)}
