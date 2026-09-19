from __future__ import annotations

from pathlib import Path

from finsight.corpus.elements import ParsedDocument
from finsight.corpus.parse_html import parse_html
from finsight.corpus.parse_pdf import parse_pdf

SUPPORTED = (".pdf", ".htm", ".html", ".txt")


def parse_document(path: str | Path) -> ParsedDocument:
    p = Path(path)
    if not p.exists():
        return ParsedDocument(elements=[], total_pages=0, source=str(p))
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        parsed = parse_pdf(str(p))
    elif suffix in (".htm", ".html"):
        parsed = parse_html(p.read_text(encoding="utf-8", errors="replace"))
    else:
        raw = p.read_text(encoding="utf-8", errors="replace")
        html = "".join(f"<p>{para}</p>" for para in raw.split("\n\n") if para.strip())
        parsed = parse_html(html)
    parsed.source = str(p)
    return parsed
