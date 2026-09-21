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

What counts as a claim:
- It names an outcome a later filing could confirm or refute: a figure, a date, a start/close/commissioning, a level to reach. An intention with no checkable outcome is NOT a claim ("we will continue to provide updates", "we remain committed to growth", "we will engage with the government").
- A commitment restated from an earlier call ("what we had said is that we expect…") or one the company relays about a partner or government ("the government is committed to delivering the £500m grant") IS a claim.
- A sentence with two measurable parts (a start date AND a volume; a revenue range AND a margin range) yields two claims, one per part.

For each claim return:
- "quote": the exact sentence from the text (copy it verbatim — it will be checked)
- "claim": one clear sentence restating the commitment, starting with "The company"
- "category": one of {categories}
- "metric": the measured quantity in a few words (e.g. "revenue growth (constant currency)", "operating margin", "effective tax rate", "free cash flow as % of net profit", "freshers hired")
- "period": the period the claim is about, in the company's terms (e.g. "FY26", "Q1 FY26", "FY26 and beyond") or null
- "outcome": one sentence, in the past tense, as a later filing would report the result if the commitment was kept — full names instead of abbreviations, the figure or event, the period (e.g. "Blast Furnace 4 at Port Talbot was shut down in September 2024"; "Revenue grew 3.1% in constant currency in FY26"; "The board approved the Neelachal Ispat Nigam expansion to 5 million tonnes")
- "target": an object describing the numeric target if there is one, else null:
    {{"kind": "range"|"point"|"min"|"max", "low": number|null, "high": number|null, "value": number|null, "unit": "%"|"bps"|"$ bn"|"$ mn"|"Rs cr"|"Rs per share"|"count"|"x"|""}}
    The unit is the one written in the quote — never convert currencies.
    Examples: "0% to 3%" → {{"kind":"range","low":0,"high":3,"unit":"%"}}; "above 100% of net profit" → {{"kind":"min","value":100,"unit":"%"}};
    "over 20,000 freshers" → {{"kind":"min","value":20000,"unit":"count"}}; "total payout for FY'25 will be Rs. 43" → {{"kind":"point","value":43,"unit":"Rs per share"}};
    "lower than FY25" → null (qualitative)
    A target is a figure the outcome will be measured against. A change is a target with the change in its unit:
    "$15 per ton lower in 2Q vs. 1Q" → {{"kind":"min","value":15,"unit":"$ per ton reduction"}}. The size of a project or
    a spend that describes what is being built is NOT a target: "commissioning facilities amounting to Rs. 19,000 crores"
    → null, the commitment is the commissioning; "a relining that will run about 160 days and come back in July" → null,
    the commitment is coming back in July.

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
    outcome: str | None = None  # how a later filing would report it if it happened — the evidence search key
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


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9%.']+", _norm(s)) if len(t) > 2}


def _match_quote(quote: str, batch: list[dict], min_overlap: float = 0.7) -> dict | None:
    """The batch sentence the quote came from: exact, prefix/substring, or ≥70% token overlap
    (models trim or lightly rephrase long sentences; the sentence must still exist)."""
    nq = _norm(quote)
    if not nq:
        return None
    for c in batch:
        ns = _norm(c["sentence"])
        if nq == ns or nq[:60] in ns or ns in nq:
            return c
    qt = _tokens(quote)
    if len(qt) < 4:
        return None
    best, best_ov = None, 0.0
    for c in batch:
        st = _tokens(c["sentence"])
        ov = len(qt & st) / len(qt)
        if ov > best_ov:
            best, best_ov = c, ov
    return best if best_ov >= min_overlap else None


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        return json.loads(text[a : b + 1])
    except json.JSONDecodeError:
        return {}


# Nouns that make a qualitative claim checkable against a later filing. A claim with no metric,
# no target and none of these is an intention ("continue to provide updates") and is dropped.
_OUTCOME_NOUNS = re.compile(
    r"\b(volume|production|deliver|cost|margin|ebitda|profit|revenue|realisation|price|debt|capex|spend|invest|"
    r"commission\w*|start\w*|clos\w+|cease\w*|shut\w*|complet\w+|launch\w*|hire|hiring|headcount|dividend|cash|tax|"
    r"grant|approv\w+|order\w*|contract\w*|operations?|"
    r"ramp|capacity|plant|furnace|mill|line|expansion|acquisition|guidance|breakeven|neutral|reduction|saving|"
    r"utili[sz]ation|attrition|deal|tcv|payout|buyback|leverage|rating|emission|tonne|ton|mtpa|mt|crore|million|"
    r"billion|bps|percent|%)\b",
    re.I,
)


def is_checkable(claim: str, metric: str | None, target: dict | None) -> bool:
    return bool(metric or target or _OUTCOME_NOUNS.search(claim))


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


# Batches the provider failed on in the last extract_claims() call (rate limits, quota). A run
# with failures has unread transcript and must not be cached or quoted as a measurement.
last_extraction = {"batches": 0, "failed": 0}


async def extract_claims(
    candidates: list[dict], *, model: str | None = None, batch_size: int = 12, parallel: int = 1
) -> list[Claim]:
    import asyncio

    batches = [candidates[i : i + batch_size] for i in range(0, len(candidates), batch_size)]
    last_extraction.update(batches=len(batches), failed=0)
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
                last_extraction["failed"] += 1
                return []
        items = _parse_json(resp.text).get("claims") or []
        out = []
        for n, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            quote = str(it.get("quote") or "").strip()
            src = _match_quote(quote, batch)
            if not src:
                continue  # quote not in the batch → not a claim we can stand behind
            cat = str(it.get("category") or "other").lower()
            claims_text = str(it.get("claim") or "").strip()
            if len(claims_text) < 15:
                continue
            metric = str(it["metric"]).strip() if it.get("metric") else None
            target = _clean_target(it.get("target"))
            if not is_checkable(claims_text, metric, target):
                continue  # an intention, not a commitment a filing could settle
            out.append(
                Claim(
                    id=f"c{bi}_{n}",
                    claim=claims_text,
                    quote=src["sentence"],
                    category=cat if cat in CATEGORIES else "other",
                    metric=metric,
                    period=(str(it["period"]).strip() if it.get("period") else None),
                    target=target,
                    outcome=(str(it["outcome"]).strip() if it.get("outcome") else None),
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
