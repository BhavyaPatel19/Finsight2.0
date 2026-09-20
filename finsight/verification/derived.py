"""
Derived metrics: ratios a person computes from two reported figures.

    free cash flow as % of net profit  = FCF / net profit
    effective tax rate                 = income tax expense / profit before tax

Fires only when the claim's metric names the ratio and both figures are
found in the evidence (fact-sheet rows or prose); otherwise returns None
and the claim is judged as usual.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BN = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(bn|billion)\b", re.I)
_MN = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(mn|million)\b", re.I)
_ROW = re.compile(r"^(?P<label>[^|]+?)\s*\|\s*(?P<v1>[-–]?\d[\d,]*(?:\.\d+)?)", re.M)
# verbalised row: "<title> — <label>: <col> = <value>; <col> = <value>; …"
_VROW = re.compile(r"(?:^|— )(?P<label>[^:\n—]{2,80}?):\s*(?P<pairs>(?:[^=\n;]+=\s*[^;\n]+;?\s*)+)", re.M)
_PAIR = re.compile(r"(?P<col>[^=;]+?)\s*=\s*(?P<v>[-–]?\d[\d,]*(?:\.\d+)?)")


@dataclass(frozen=True)
class Ratio:
    name: str
    metric_pattern: re.Pattern
    numerator: re.Pattern
    denominator: re.Pattern
    sane: tuple[float, float]  # plausible % range
    queries: tuple[str, str]  # how to ask the index for each component


RATIOS = [
    Ratio(
        "free cash flow / net profit",
        re.compile(r"free cash flow.*(net profit|conversion|% of net)|cash conversion", re.I),
        re.compile(r"\bfree cash flow\b", re.I),
        re.compile(r"\bnet profit\b", re.I),
        (30.0, 300.0),
        ("free cash flow", "net profit"),
    ),
    Ratio(
        "effective tax rate",
        re.compile(r"effective tax|\betr\b|tax rate", re.I),
        re.compile(r"\bincome tax expense\b|\btax expense\b", re.I),
        re.compile(r"\bprofit before (income )?tax", re.I),
        (5.0, 60.0),
        ("income tax expense", "profit before income taxes"),
    ),
]


def ratio_for(metric: str | None) -> Ratio | None:
    return next((r for r in RATIOS if metric and r.metric_pattern.search(metric)), None)


def _prefer(period: str | None) -> tuple[str, ...]:
    """Column-header words for the claim's period: a full-year claim wants the 'Year ended' column."""
    if period and re.search(r"\bQ[1-4]\b", period, re.I):
        return ("3 months", "quarter", "three months")
    if period and re.search(r"\bFY|financial year|fiscal", period, re.I):
        return ("year ended", "year", "fy")
    return ()


def _first_number(text: str, label: re.Pattern, prefer: tuple[str, ...] = ()) -> float | None:
    """A figure in millions for the first row/sentence whose label matches. Verbalised rows: the
    value under the column matching `prefer` (else the first). Raw rows: first value cell.
    Prose: '$3.7 billion' → 3700, '$884 mn' → 884."""
    for m in _VROW.finditer(text):
        if not label.search(m.group("label")):
            continue
        pairs = [(p.group("col").strip().lower(), p.group("v")) for p in _PAIR.finditer(m.group("pairs"))]
        if not pairs:
            continue
        chosen = next((v for c, v in pairs if any(w in c for w in prefer)), pairs[0][1])
        try:
            return float(chosen.replace(",", "").replace("–", "-"))
        except ValueError:
            continue
    for m in _ROW.finditer(text):
        if label.search(m.group("label")):
            try:
                return float(m.group("v1").replace(",", "").replace("–", "-"))
            except ValueError:
                continue
    for sent in re.split(r"(?<=[.!?])\s+|\n", text):
        lm = label.search(sent)
        if not lm:
            continue
        after = sent[lm.end() :]  # the figure that follows the label, not an earlier one in the sentence
        b = _BN.search(after)
        m = _MN.search(after)
        cands = [(x.start(), float(x.group(1).replace(",", "")) * (1000 if x is b else 1)) for x in (b, m) if x]
        if cands:
            return min(cands)[1]
    return None


def derived_actual(
    metric: str | None, evidence_texts: list[str], period: str | None = None
) -> tuple[float, str] | None:
    """(value in %, explanation) when the claim is a known ratio and both figures are in the evidence."""
    if not metric:
        return None
    prefer = _prefer(period)
    for ratio in RATIOS:
        if not ratio.metric_pattern.search(metric):
            continue
        num = den = None
        num_src = den_src = ""
        for text in evidence_texts:
            if num is None:
                v = _first_number(text, ratio.numerator, prefer)
                if v is not None:
                    num, num_src = v, text[:80]
            if den is None:
                v = _first_number(text, ratio.denominator, prefer)
                if v is not None:
                    den, den_src = v, text[:80]
        if num is None or den in (None, 0):
            return None
        pct = round(num / den * 100, 1)
        lo, hi = ratio.sane
        if not (lo <= pct <= hi):
            return None
        return pct, f"{ratio.name} = {num:g} / {den:g} = {pct}% (from: {num_src!r}; {den_src!r})"
    return None
