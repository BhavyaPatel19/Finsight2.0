"""
Period mentions in a question → document prior.

"Q4 FY25", "FY26", "financial year '26", "April 2025", "March 31, 2026",
"fiscal 2026" all resolve to (fiscal_year, fiscal_quarter) constraints in
the corpus's own labels ("FY25", "Q4"). Indian fiscal years end in March:
a results call held in April 2025 is the Q4 FY25 call; July → Q1 of the
next FY; October → Q2; January → Q3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august september october november december".split()
    )
}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})


def _reported_in(year: int, month: int) -> tuple[str, str]:
    """(fiscal_year, quarter) whose results are announced in this calendar month."""
    if month in (4, 5, 6):
        return f"FY{year % 100:02d}", "Q4"  # April 2025 → Q4 FY25
    if month in (7, 8, 9):
        return f"FY{(year + 1) % 100:02d}", "Q1"  # July 2025 → Q1 FY26
    if month in (10, 11, 12):
        return f"FY{(year + 1) % 100:02d}", "Q2"
    return f"FY{year % 100:02d}", "Q3"  # January 2026 → Q3 FY26


@dataclass(frozen=True)
class Period:
    fiscal_year: str | None  # "FY26"
    fiscal_quarter: str | None  # "Q4"

    def matches(self, fiscal_year: str | None, fiscal_quarter: str | None) -> bool:
        if self.fiscal_year and _fy(self.fiscal_year) != _fy(fiscal_year):
            return False
        if self.fiscal_quarter and fiscal_quarter and self.fiscal_quarter.upper() != fiscal_quarter.upper():
            return False
        return True


def _fy(label: str | None) -> str | None:
    if not label:
        return None
    m = re.search(r"(\d{2,4})", label)
    if not m:
        return None
    y = int(m.group(1))
    return f"FY{y % 100:02d}"


def _calendar_to_fy(year: int, month: int) -> str:
    # April 2025 → FY26 (year ending March 2026); January–March 2026 → FY26
    fy_end = year + 1 if month >= 4 else year
    return f"FY{fy_end % 100:02d}"


def parse_periods(question: str) -> set[Period]:
    q = question.replace("’", "'")
    found: set[Period] = set()

    for m in re.finditer(r"\bQ([1-4])\s*[- ]?\s*(?:FY|financial year|fiscal year|fiscal)?\s*'?(\d{2,4})\b", q, re.I):
        found.add(Period(_fy(m.group(2)), f"Q{m.group(1)}"))
    for m in re.finditer(r"\b(?:FY|financial year|fiscal year|fiscal)\s*'?(\d{2,4})\b", q, re.I):
        found.add(Period(_fy(m.group(1)), None))
    for m in re.finditer(r"\b(?:FY|financial year|fiscal year)\s*'?(\d{2,4})\s*[-–/]\s*(\d{2,4})\b", q, re.I):
        found.add(Period(_fy(m.group(2)), None))
    for m in re.finditer(r"\b([A-Za-z]{3,9})\.?\s+(?:(\d{1,2}),?\s+)?(20\d{2})\b", q):
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            year = int(m.group(3))
            day = m.group(2)
            if day and mon == 3 and int(day) >= 28:  # "March 31, 2026" = FY26 year end → Q4 FY26
                found.add(Period(_calendar_to_fy(year, mon), "Q4"))
            elif day and mon in (6, 9, 12) and int(day) >= 28:  # quarter ends
                found.add(Period(_calendar_to_fy(year, mon), {6: "Q1", 9: "Q2", 12: "Q3"}[mon]))
            else:  # a results month → the quarter reported that month
                found.add(Period(*_reported_in(year, mon)))
    # a bare FY with a quarter mentioned elsewhere ("Q4 ... FY25") is covered by the first pattern;
    # drop FY-only periods that duplicate a FY+Q one
    fy_q = {p.fiscal_year for p in found if p.fiscal_quarter}
    return {p for p in found if p.fiscal_quarter or p.fiscal_year not in fy_q}


def period_boost(question: str, fiscal_year: str | None, fiscal_quarter: str | None, factor: float = 1.5) -> float:
    """Multiplier for a document given the periods the question names (1.0 when none match or none named)."""
    periods = parse_periods(question)
    if not periods:
        return 1.0
    return factor if any(p.matches(fiscal_year, fiscal_quarter) for p in periods) else 1.0
