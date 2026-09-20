"""
Stage 1 of Walk the Talk v2: forward-looking claims with a typed target.

Candidates are sentences (from the v2 index) that carry a forward-looking
cue; an LLM structures each batch into claims. Every claim must quote its
source sentence verbatim — items whose quote is not in the batch text are
dropped, so the LLM cannot invent a promise.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from finsight.llm import LLMError, agenerate

logger = logging.getLogger(__name__)

CATEGORIES = [
    "revenue",
    "margin",
    "cash_flow",
    "tax",
    "hiring",
    "capex",
    "debt",
    "dividend",
    "cost",
    "growth",
    "product",
    "other",
]

# Cues that make a sentence a candidate. Broad on purpose: precision comes from the LLM + quote check.
_CUES = re.compile(
    r"\b(guidance|guide|expect|expects|expected|expecting|anticipate|target|targets|targeting|aim|aims|outlook|"
    r"forecast|plan|plans|planning|intend|intends|endeavou?r|commit|committed|will|shall|"
    r"going forward|next (year|quarter|fiscal)|for (the )?(financial year|fiscal|FY)\s*'?\d|for FY|"
    r"in FY\s*'?\d|by FY|by the end of|over the (next|coming)|should (be|remain|improve)|likely to|"
    r"range of|in the range|to be (above|below|between|around|about|lower|higher)|should (come|land))\b",
    re.I,
)
_HISTORICAL = re.compile(
    r"\b(was|were|grew|declined|stood at|came in at|closed the year|last year|previous year|compared to)\b", re.I
)

EXTRACT_PROMPT = """You are reading sentences from a company's earnings call. Extract every FORWARD-LOOKING commitment, target, guidance or expectation about a future period. Ignore statements about what already happened.

For each claim return:
- "quote": the exact sentence from the text (copy it verbatim — it will be checked)
- "claim": one clear sentence restating the commitment, starting with "The company"
- "category": one of {categories}
- "metric": the measured quantity in a few words (e.g. "revenue growth (constant currency)", "operating margin", "effective tax rate", "free cash flow as % of net profit", "freshers hired")
- "period": the period the claim is about, in the company's terms (e.g. "FY26", "Q1 FY26", "FY26 and beyond") or null
- "target": an object describing the numeric target if there is one, else null:
    {{"kind": "range"|"point"|"min"|"max", "low": number|null, "high": number|null, "value": number|null, "unit": "%"|"bps"|"$ bn"|"$ mn"|"Rs cr"|"count"|"x"|""}}
    Examples: "0% to 3%" → {{"kind":"range","low":0,"high":3,"unit":"%"}}; "above 100% of net profit" → {{"kind":"min","value":100,"unit":"%"}};
    "over 20,000 freshers" → {{"kind":"min","value":20000,"unit":"count"}}; "lower than FY25" → null (qualitative)

Text:
{text}

Return JSON: {{"claims": [ ... ]}}. Return {{"claims": []}} if there are none."""


@dataclass
class Claim:
    id: str
    claim: str
    quote: str
    category: str
    metric: str | None
    period: str | None
    target: dict | None
    source_chunk: str
    speaker: str | None = None
    page: int | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def is_candidate(sentence: str) -> bool:
    s = sentence.strip()
    if len(s) < 25 or not _CUES.search(s):
        return False
    # "we expect …" beats a historical verb in the same sentence; pure history is skipped
    return not (
        _HISTORICAL.search(s)
        and not re.search(r"\b(expect|guidance|target|will|plan|aim|outlook|going forward|endeavou?r)\b", s, re.I)
    )


def candidate_sentences(chunks: list[dict]) -> list[dict]:
    """[{chunk_id, sentence, speaker, page}] from v2 chunk records of the claims document."""
    out = []
    from finsight.corpus.chunker import split_sentences

    for c in chunks:
        m = c["metadata"]
        if m.get("kind") != "prose":
            continue
        for s in split_sentences(c["text"]):
            if is_candidate(s):
                out.append(
                    {
                        "chunk_id": c["id"],
                        "sentence": s,
                        "speaker": m.get("speaker") or None,
                        "page": m.get("page_number"),
                    }
                )
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        return json.loads(text[a : b + 1])
    except json.JSONDecodeError:
        return {}


def _clean_target(t) -> dict | None:
    if not isinstance(t, dict) or t.get("kind") not in ("range", "point", "min", "max"):
        return None

    def num(x):
        try:
            return float(str(x).replace(",", "")) if x is not None and str(x).strip() != "" else None
        except ValueError:
            return None

    out = {
        "kind": t["kind"],
        "low": num(t.get("low")),
        "high": num(t.get("high")),
        "value": num(t.get("value")),
        "unit": str(t.get("unit") or ""),
    }
    if out["kind"] == "range" and (out["low"] is None or out["high"] is None):
        return None
    if out["kind"] in ("point", "min", "max") and out["value"] is None:
        return None
    return out


async def extract_claims(
    candidates: list[dict], *, model: str | None = None, batch_size: int = 12, parallel: int = 1
) -> list[Claim]:
    import asyncio

    batches = [candidates[i : i + batch_size] for i in range(0, len(candidates), batch_size)]
    sem = asyncio.Semaphore(max(1, parallel))
    claims: list[Claim] = []

    async def run(bi: int, batch: list[dict]) -> list[Claim]:
        text = "\n".join(f"- {c['sentence']}" for c in batch)
        prompt = EXTRACT_PROMPT.format(categories=", ".join(CATEGORIES), text=text)
        async with sem:
            try:
                resp = await agenerate(
                    prompt, model=model, max_tokens=1800, temperature=0.0, json_mode=True, think=False
                )
            except LLMError as e:
                logger.warning("claim extraction batch %d failed: %s", bi, e)
                return []
        items = _parse_json(resp.text).get("claims") or []
        out = []
        by_norm = {_norm(c["sentence"]): c for c in batch}
        for n, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            quote = str(it.get("quote") or "").strip()
            src = by_norm.get(_norm(quote)) or next(
                (c for c in batch if _norm(quote)[:60] and _norm(quote)[:60] in _norm(c["sentence"])), None
            )
            if not src:
                continue  # quote not in the batch → not a claim we can stand behind
            cat = str(it.get("category") or "other").lower()
            claims_text = str(it.get("claim") or "").strip()
            if len(claims_text) < 15:
                continue
            out.append(
                Claim(
                    id=f"c{bi}_{n}",
                    claim=claims_text,
                    quote=src["sentence"],
                    category=cat if cat in CATEGORIES else "other",
                    metric=(str(it["metric"]).strip() if it.get("metric") else None),
                    period=(str(it["period"]).strip() if it.get("period") else None),
                    target=_clean_target(it.get("target")),
                    source_chunk=src["chunk_id"],
                    speaker=src.get("speaker"),
                    page=src.get("page"),
                )
            )
        return out

    results = await asyncio.gather(*(run(i, b) for i, b in enumerate(batches)))
    for r in results:
        claims.extend(r)
    return dedupe(claims)


def _metric_key(metric: str | None) -> str:
    words = re.findall(r"[a-z]+", (metric or "").lower())
    stop = {
        "the",
        "of",
        "in",
        "and",
        "for",
        "a",
        "an",
        "as",
        "guidance",
        "guide",
        "target",
        "expected",
        "expect",
        "outlook",
        "range",
    }
    return " ".join(sorted(w[:5] for w in words if w not in stop))


def dedupe(claims: list[Claim]) -> list[Claim]:
    """Drop restatements: same quote prefix, or the same metric + period + numeric target."""
    seen: set[str] = set()
    out = []
    for c in claims:
        keys = [_norm(c.quote)[:80]]
        if c.target:
            t = c.target
            keys.append(
                f"{_metric_key(c.metric)}|{(c.period or '').lower()}|{t['kind']}|{t.get('low')}|{t.get('high')}|{t.get('value')}|{t.get('unit')}"
            )
        if any(k in seen for k in keys):
            continue
        seen.update(keys)
        out.append(c)
    return out
