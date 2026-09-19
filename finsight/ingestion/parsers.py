import re
from pathlib import Path

from finsight.config import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP

# ---------------------------------------------------------------------------
# Concall transcript detection
# ---------------------------------------------------------------------------

# Matches speaker turn starts: "Moderator:", "Q:", "John Smith:", "[Analyst]"
_SPEAKER_RE = re.compile(
    r"(?m)^(?:"
    r"(?:Moderator|Operator|Host|Chairman|CEO|CFO|MD|CTO|COO|President|Director)\s*[:\-]|"
    r"(?:Q|A|Question|Answer)\s*[:\-]|"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*[:\-]|"
    r"\[.*?\]"
    r")"
)


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract text using PyMuPDF first, fallback to pdfplumber."""
    path = Path(pdf_path)
    if not path.exists():
        return ""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text
    except Exception:
        return ""


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple sliding-window chunking by character count (approx tokens)."""
    if not text or not text.strip():
        return []
    text = text.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start >= len(text):
            break
    return chunks


# ---------------------------------------------------------------------------
# Structured extraction for RAG (page-aware with TOC / section hierarchy)
# ---------------------------------------------------------------------------

SUPPORTED_SUFFIXES = (".pdf", ".htm", ".html", ".txt")


def extract_structured_document(pdf_path: str | Path) -> dict:
    """
    Extract document structure. PDFs go through PyMuPDF (real pages + TOC);
    HTML/text sources are paginated into synthetic pages (see html_parser).
    """
    if Path(pdf_path).suffix.lower() in (".htm", ".html", ".txt"):
        from finsight.ingestion.html_parser import extract_structured_html
        return extract_structured_html(pdf_path)
    return _extract_structured_pdf(pdf_path)


def _extract_structured_pdf(pdf_path: str | Path) -> dict:
    """
    Extract document structure using PyMuPDF:
    - TOC (table of contents) with section hierarchy
    - Page-by-page text
    - Section boundaries mapped to pages

    Returns:
        {
            "toc": [(level, title, page_number), ...],
            "pages": [{"page": 1, "text": "...", "section": "...", "sub_section": "..."}, ...],
            "sections": [{"title": ..., "level": ..., "start_page": ..., "end_page": ..., "children": [...]}, ...],
            "total_pages": int,
        }
    """
    import fitz

    path = Path(pdf_path)
    if not path.exists():
        return {"toc": [], "pages": [], "sections": [], "total_pages": 0}

    doc = fitz.open(path)
    total_pages = len(doc)

    # 1. Extract TOC (PyMuPDF built-in — no LLM needed)
    raw_toc = doc.get_toc()  # [(level, title, page_number), ...]

    # 2. Build section tree from TOC
    sections = _build_section_tree(raw_toc, total_pages)

    # 3. Extract page-by-page text and tag with sections
    pages = []
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text("text")
        pg = page_num + 1  # 1-indexed
        section, sub_section = _find_section_for_page(sections, pg)
        pages.append({
            "page": pg,
            "text": text.strip(),
            "section": section,
            "sub_section": sub_section,
        })

    doc.close()
    return {
        "toc": raw_toc,
        "pages": pages,
        "sections": sections,
        "total_pages": total_pages,
    }


def _build_section_tree(toc: list, total_pages: int) -> list[dict]:
    """
    Convert PyMuPDF TOC list into a nested section tree.
    Input: [(level, title, page_number), ...]
    Output: [{"title", "level", "start_page", "end_page", "children": [...]}, ...]
    """
    if not toc:
        return []

    # Flatten into list of section dicts with page ranges
    flat_sections = []
    for i, (level, title, page) in enumerate(toc):
        # end_page = next section's start - 1, or total_pages
        end_page = total_pages
        for j in range(i + 1, len(toc)):
            if toc[j][0] <= level:  # same or higher level = section ends
                end_page = toc[j][2] - 1
                break
        flat_sections.append({
            "title": title.strip(),
            "level": level,
            "start_page": page,
            "end_page": end_page,
            "children": [],
        })

    # Build tree: nest children under parents based on level
    root: list[dict] = []
    stack: list[dict] = []

    for section in flat_sections:
        # Pop stack until we find a parent with lower level
        while stack and stack[-1]["level"] >= section["level"]:
            stack.pop()

        if stack:
            stack[-1]["children"].append(section)
        else:
            root.append(section)

        stack.append(section)

    return root


def _find_section_for_page(sections: list[dict], page: int) -> tuple[str | None, str | None]:
    """
    Find the section and sub-section title for a given page number.
    Returns (section_title, sub_section_title).
    """
    section_title = None
    sub_section_title = None

    def search(nodes: list[dict], depth: int = 0):
        nonlocal section_title, sub_section_title
        for node in nodes:
            if node["start_page"] <= page <= node["end_page"]:
                if depth == 0:
                    section_title = node["title"]
                    sub_section_title = None  # reset on new top section
                elif depth == 1:
                    sub_section_title = node["title"]
                else:
                    # Deeper levels update sub_section
                    sub_section_title = node["title"]
                # Search children for more specific match
                if node["children"]:
                    search(node["children"], depth + 1)
                return  # Found match at this level

    search(sections)
    return section_title, sub_section_title


def chunk_pages(
    pages: list[dict],
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[dict]:
    """
    Page-aware chunking: split text within page boundaries.
    Each chunk preserves page_number, section_title, sub_section_title.

    Returns list of dicts:
    [{"text": ..., "page_number": ..., "section": ..., "sub_section": ..., "chunk_index": ...}, ...]
    """
    chunks = []
    chunk_idx = 0

    for page in pages:
        text = page.get("text", "").strip()
        if not text:
            continue

        page_num = page["page"]
        section = page.get("section")
        sub_section = page.get("sub_section")

        # If page text fits in one chunk, keep it whole
        if len(text) <= chunk_size:
            chunks.append({
                "text": text,
                "page_number": page_num,
                "section": section,
                "sub_section": sub_section,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1
        else:
            # Split large pages with overlap
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text_slice = text[start:end].strip()
                if chunk_text_slice:
                    chunks.append({
                        "text": chunk_text_slice,
                        "page_number": page_num,
                        "section": section,
                        "sub_section": sub_section,
                        "chunk_index": chunk_idx,
                    })
                    chunk_idx += 1
                start = end - overlap
                if start >= len(text):
                    break

    return chunks


# ---------------------------------------------------------------------------
# Concall-aware chunking
# ---------------------------------------------------------------------------

def is_concall_transcript(pages: list[dict]) -> bool:
    """
    Detect if document is an earnings call transcript by counting speaker
    turn patterns in the first 5 pages. Threshold: >= 5 matches.
    """
    sample = " ".join(p.get("text", "") for p in pages[:5])
    return len(_SPEAKER_RE.findall(sample)) >= 5


def chunk_by_speaker(
    pages: list[dict],
    chunk_size: int = 1500,
) -> list[dict]:
    """
    Chunk concall transcript by grouping speaker turns.
    Each chunk = one complete Q&A exchange (or several turns that fit in chunk_size).
    Preserves page_number, section, sub_section from the first page of each chunk.
    """
    chunks = []
    chunk_idx = 0
    buf_turns: list[str] = []
    buf_len = 0
    buf_page = pages[0]["page"] if pages else 1
    buf_section = pages[0].get("section") if pages else None
    buf_sub = pages[0].get("sub_section") if pages else None

    for page in pages:
        page_num = page["page"]
        text = page.get("text", "").strip()
        if not text:
            continue

        section = page.get("section")
        sub_section = page.get("sub_section")

        # Split page into speaker turns at detected boundaries
        positions = [m.start() for m in _SPEAKER_RE.finditer(text)]
        if not positions:
            positions = [0]
        boundaries = positions + [len(text)]
        turns = [
            text[boundaries[i]:boundaries[i + 1]].strip()
            for i in range(len(boundaries) - 1)
            if text[boundaries[i]:boundaries[i + 1]].strip()
        ]

        for turn in turns:
            # Flush buffer when adding this turn would overflow chunk_size
            if buf_len + len(turn) > chunk_size and buf_turns:
                chunks.append({
                    "text": "\n".join(buf_turns),
                    "page_number": buf_page,
                    "section": buf_section,
                    "sub_section": buf_sub,
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1
                buf_turns = []
                buf_len = 0
                buf_page = page_num
                buf_section = section
                buf_sub = sub_section

            if not buf_turns:
                buf_page = page_num
                buf_section = section
                buf_sub = sub_section

            buf_turns.append(turn)
            buf_len += len(turn)

    if buf_turns:
        chunks.append({
            "text": "\n".join(buf_turns),
            "page_number": buf_page,
            "section": buf_section,
            "sub_section": buf_sub,
            "chunk_index": chunk_idx,
        })

    return chunks


def chunk_smart(
    pages: list[dict],
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[dict]:
    """
    Auto-select chunking strategy:
    - Concall transcripts  → speaker-turn chunking (Q&A pairs)
    - Annual reports / other → page-section chunking with overlap
    """
    if pages and is_concall_transcript(pages):
        return chunk_by_speaker(pages, chunk_size=chunk_size)
    return chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
