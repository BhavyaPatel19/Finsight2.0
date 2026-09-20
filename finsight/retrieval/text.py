"""Tokenisation shared by BM25 and the period parser: numbers stay whole."""

from __future__ import annotations

import re

# 4,730 → 4730 ; 21.1% → 21.1% ; $4.1 → 4.1 ; fy'26 → fy26 ; words lower-cased, light suffix stemming
_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[a-z]+\d+|[a-z]+(?:'[a-z]+)?", re.I)
_STEM_SUFFIXES = ("ations", "ation", "ings", "ing", "ies", "ers", "es", "ed", "ly", "s")


def stem(word: str) -> str:
    for suf in _STEM_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)] + ("y" if suf == "ies" else "")
    return word


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    text = re.sub(r"\bfy\s*'?(?:20)?(\d{2})\b", r"fy\1", text)  # FY 2026, FY'26, FY26 → fy26
    out = []
    for tok in _TOKEN.findall(text):
        if tok[0].isdigit():
            out.append(tok.replace(",", ""))
        elif tok[-1].isdigit():  # q4, fy25, h1
            out.append(tok)
        else:
            out.append(stem(tok.replace("'", "")))
    return out
