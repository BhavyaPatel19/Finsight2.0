"""
Guess what a filing is from its first pages and its file name, so that dropping a
folder of a company's documents needs no form: document type, fiscal quarter and
year (Indian April–March convention), and the company name. Every guess carries
the text it came from; nothing here calls a model.

    >>> detect_metadata("documents/external/TATASTEEL/TATASTEEL_concall_Q4FY25.pdf")
    {'doc_type': 'concall', 'fiscal_quarter': 'Q4', 'fiscal_year': 'FY25', 'company_name': 'Tata Steel Limited', ...}
"""

from __future__ import annotations

import re
from pathlib import Path

_MONTH_Q = {  # Indian fiscal year: April–March
    "jun": ("Q1", 0),
    "sep": ("Q2", 0),
    "dec": ("Q3", 0),
    "mar": ("Q4", 1),  # March 2025 closes FY25 → FY = year
}
_TYPE_RULES = [
    (
        "concall",
        re.compile(
            r"earnings (conference )?call|conference call|call transcript|transcript of|corporate participants|analyst call",
            re.I,
        ),
    ),
    ("fact_sheet", re.compile(r"\bfact ?sheet", re.I)),
    (
        "press_release",
        re.compile(
            r"press release|results for the (quarter|year)|announces (its )?results|financial results for", re.I
        ),
    ),
    ("annual_report", re.compile(r"annual report|integrated report|annual accounts|integrated annual", re.I)),
    (
        "presentation",
        re.compile(r"investor presentation|results presentation|analyst presentation|earnings presentation", re.I),
    ),
]
_ORDINAL = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
_PERIOD_RULES = [
    # "results for the first quarter of FY2026" · "fourth quarter and full year FY2025" — how a call opens
    re.compile(
        r"\b(first|second|third|fourth) quarter(?: and (?:full |the )?year)?(?: results)?(?: of| for| ended)?(?: the)?(?: fiscal| financial)?"
        r"(?: year)?\s*(?:FY\s*'?)?(\d{4}|'?\d{2})\b",
        re.I,
    ),
    # Q1 FY26 · Q1FY'26 · Q1 FY2026 · 1QFY25 · 1Q FY2025
    re.compile(r"\b(?:Q([1-4])\s*FY\s*'?(\d{2,4})|([1-4])Q\s*FY\s*'?(\d{2,4}))\b", re.I),
    # quarter ended June 30, 2024 · quarter and year ended March 31, 2025
    re.compile(
        r"\b(?:quarter|three months|3 months)(?: and (?:nine|six|three) months)?(?: and (?:half|full) year)?(?: and year)? ended\s+([A-Za-z]+)\s+\d{1,2},?\s+(\d{4})",
        re.I,
    ),
    # year ended March 31, 2025 · financial year ended 31 March 2025
    re.compile(r"\b(?:financial |fiscal )?year ended\s+(?:(\d{1,2})\s+)?([A-Za-z]+)\s*(?:\d{1,2},?\s+)?(\d{4})", re.I),
    # Annual Accounts 2024-25 · FY2024-25 · financial year 2024-25
    re.compile(
        r"\b(?:FY|financial year|fiscal year|annual accounts|integrated report(?: and annual accounts)?)\s*'?(\d{4})\s*[-–]\s*(\d{2,4})\b",
        re.I,
    ),
]
_COMPANY = re.compile(
    r"\b([A-Z][A-Za-z&.'\-]*(?: [A-Z][A-Za-z&.'\-]*){0,4} (?:Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?|plc|PLC))\b"
)


def _fy(year: int, add: int) -> str:
    return f"FY{(year + add) % 100:02d}"


def _period_mentions(text: str) -> list[tuple[str, str, str]]:
    """Every (quarter, FY, matched text) the first pages mention. A transcript names its own
    quarter many times and the comparison quarters once or twice, so the caller counts."""
    out = []
    for rx in _PERIOD_RULES:
        for m in rx.finditer(text):
            g = m.groups()
            if rx is _PERIOD_RULES[0]:
                yy = int(g[1].strip("'")) % 100
                out.append((_ORDINAL[g[0].lower()], f"FY{yy:02d}", m.group(0)))
            elif rx is _PERIOD_RULES[1]:
                q = g[0] or g[2]
                yy = g[1] or g[3]
                out.append((f"Q{q}", f"FY{int(yy) % 100:02d}", m.group(0)))
            elif rx is _PERIOD_RULES[2]:
                mon, year = g[0][:3].lower(), int(g[1])
                if mon in _MONTH_Q:
                    q, _ = _MONTH_Q[mon]
                    out.append((q, _fy(year, 0 if mon == "mar" else 1), m.group(0)))
            elif rx is _PERIOD_RULES[3]:
                mon, year = g[1][:3].lower(), int(g[2])
                if mon == "mar":
                    out.append(("Q4", _fy(year, 0), m.group(0)))
            elif rx is _PERIOD_RULES[4]:
                out.append(("Q4", f"FY{int(g[1]) % 100:02d}", m.group(0)))
    return out


def _period_from_text(text: str) -> tuple[str | None, str | None, str | None]:
    """The period mentioned most often in the first pages; ties go to the latest."""
    from collections import Counter

    mentions = _period_mentions(text)
    if not mentions:
        return None, None, None
    counts = Counter((q, fy) for q, fy, _ in mentions)
    # explicit quarter mentions decide when present; a "FY2024-25" style mention alone is a report title
    quarterly = {
        k: v
        for k, v in counts.items()
        if any(
            (q, fy) == k and not t.lower().startswith(("fy", "financial", "fiscal", "annual", "integrated"))
            for q, fy, t in mentions
        )
    }
    pool = quarterly or counts
    best = max(pool, key=lambda k: (pool[k], k[1], k[0]))
    example = next(t for q, fy, t in mentions if (q, fy) == best)
    return best[0], best[1], f"{example} (×{counts[best]})"


def _period_from_name(name: str) -> tuple[str | None, str | None]:
    m = re.search(r"(?:Q([1-4])\s*FY\s*(\d{2,4})|([1-4])Q\s*FY\s*(\d{2,4}))", name, re.I)
    if m:
        q = m.group(1) or m.group(3)
        yy = m.group(2) or m.group(4)
        return f"Q{q}", f"FY{int(yy) % 100:02d}"
    m = re.search(r"(?:annual|integrated|IR)[-_ ]?(?:FY)?(\d{2,4})(?:[-–](\d{2}))?", name, re.I)
    if m:
        yy = int(m.group(2) or m.group(1)) % 100
        return "Q4", f"FY{yy:02d}"
    return None, None


_NOT_A_NAME = {
    "earnings",
    "conference",
    "call",
    "press",
    "release",
    "transcript",
    "exhibit",
    "fact",
    "sheet",
    "of",
    "the",
    "quarter",
    "year",
    "annual",
    "integrated",
    "report",
    "results",
    "limited",
    "ltd",
}


def _company_from_text(text: str) -> str | None:
    """The most frequent short '<Name> Limited/Ltd/Inc' in the first pages, with title words
    ("Earnings Conference Call Infosys Limited") stripped from the front."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for m in _COMPANY.finditer(text):
        words = m.group(1).split()
        while len(words) > 2 and words[0].lower().strip(".,:'") in _NOT_A_NAME:
            words = words[1:]
        if 2 <= len(words) <= 5:
            counts[" ".join(words)] += 1
    return max(counts, key=lambda k: (counts[k], -len(k))) if counts else None


def detect_metadata(path: str | Path, pages: int = 3, period_pages: int = 12) -> dict:
    """`pages` decide the document type and company; `period_pages` are counted for the period
    (a transcript without a title page names its quarter in the prepared remarks, not on page 1)."""
    import fitz

    path = Path(path)
    doc = fitz.open(path)
    n_pages = len(doc)
    page_texts = [" ".join(doc[i].get_text().split()) for i in range(min(max(pages, period_pages), n_pages))]
    doc.close()
    text = " ".join(page_texts[:pages])
    period_text = " ".join(page_texts[:period_pages])
    head = text[:4000]

    doc_type, type_evidence = None, None
    for kind, rx in _TYPE_RULES:
        m = rx.search(head)
        if m:
            doc_type, type_evidence = kind, m.group(0)
            break
    if doc_type is None and n_pages >= 100:
        doc_type, type_evidence = "annual_report", f"{n_pages} pages"
    if doc_type is None:
        # a transcript without a title page: the cast list or a moderator
        if re.search(r"\b(moderator|operator)\s*:", head, re.I) or re.search(r"\bparticipants\b", head, re.I):
            doc_type, type_evidence = "concall", "speaker labels on the first page"

    q, fy, period_evidence = _period_from_text(period_text)
    if not q:
        q, fy = _period_from_name(path.name)
        period_evidence = f"file name {path.name}" if q else None

    company = _company_from_text(text)

    return {
        "doc_type": doc_type,
        "fiscal_quarter": q,
        "fiscal_year": fy,
        "company_name": company,
        "pages": n_pages,
        "evidence": {"doc_type": type_evidence, "period": period_evidence},
    }
