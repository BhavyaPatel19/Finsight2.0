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


@dataclass(frozen=True)
class Ratio:
    name: str
    metric_pattern: re.Pattern
    numerator: re.Pattern
    denominator: re.Pattern
    sane: tuple[float, float]  # plausible % range


RATIOS = [
    Ratio(
        "free cash flow / net profit",
        re.compile(r"free cash flow.*(net profit|conversion|% of net)|cash conversion", re.I),
        re.compile(r"\bfree cash flow\b", re.I),
        re.compile(r"\bnet profit\b", re.I),
        (30.0, 300.0),
    ),
    Ratio(
        "effective tax rate",
        re.compile(r"effective tax|\betr\b|tax rate", re.I),
        re.compile(r"\bincome tax expense\b|\btax expense\b", re.I),
        re.compile(r"\bprofit before (income )?tax", re.I),
        (5.0, 60.0),
    ),
]


def _first_number(text: str, label: re.Pattern) -> float | None:
    """A figure in millions for the first row/sentence whose label matches. Rows: first value cell.
    Prose: '$3.7 billion' → 3700, '$884 mn' → 884."""
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


def derived_actual(metric: str | None, evidence_texts: list[str]) -> tuple[float, str] | None:
    """(value in %, explanation) when the claim is a known ratio and both figures are in the evidence."""
    if not metric:
        return None
    for ratio in RATIOS:
        if not ratio.metric_pattern.search(metric):
            continue
        num = den = None
        num_src = den_src = ""
        for text in evidence_texts:
            if num is None:
                v = _first_number(text, ratio.numerator)
                if v is not None:
                    num, num_src = v, text[:80]
            if den is None:
                v = _first_number(text, ratio.denominator)
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
