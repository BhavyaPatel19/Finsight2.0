"""
Stage 2b: the verdict.

- The LLM reads the claim and its evidence chunks and answers with a verdict,
  the actual value, and the *exact quote* it relied on. A quote that is not
  in the cited chunk downgrades the verdict to UNVERIFIABLE.
- When the claim's target and the extracted actual are both numbers in the
  same unit, the verdict is computed, not trusted.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from finsight.llm import LLMError, agenerate
from finsight.verification.claims import Claim, _match_quote

logger = logging.getLogger(__name__)

VERDICTS = ("MET", "MISSED", "PARTIAL", "UNVERIFIABLE")

VERIFY_PROMPT = """You are auditing whether a company delivered on a commitment made on an earlier earnings call.

CLAIM (made earlier): {claim}
  metric: {metric} · period: {period} · target: {target}

EVIDENCE from the later period's filings (each block has an id):
{evidence}
{baseline}
Rules:
- Only REPORTED RESULTS count as evidence (figures that were achieved, e.g. "revenue grew 3.1%", "margin was 21%", a fact-sheet row). A sentence that itself makes a promise or gives guidance ("we expect…", "guidance for FY27 is…", "will…") is NOT an outcome — never grade a claim against another promise, and never treat a restated or later-period guidance as contradicting the claim.
- Read periods carefully: evidence about a different period than the claim's is not evidence for the claim.
- MET: the evidence shows the commitment was achieved (a range target is MET when the actual falls inside it; "above X" when actual ≥ X).
- MISSED: the evidence shows it was not achieved.
- PARTIAL: achieved in part or in direction but not in full (e.g. margin improved but less than promised; a qualitative promise only partly delivered).
- A directional claim ("improve from current levels", "lower than last year", "maintain") is judged against the BASELINE figure from when the claim was made: better in the promised direction is MET, unchanged is PARTIAL for an improvement promise (MET for "maintain"), worse is MISSED. Without a baseline figure such a claim is UNVERIFIABLE.
- UNVERIFIABLE: the evidence does not contain the reported result needed (including when it only contains promises or guidance). Do NOT guess. Use this whenever the number or fact is simply not there.
- "actual_value": the actual figure or outcome as stated in the evidence, with unit; null if UNVERIFIABLE.
- "actual_number": the actual as a plain number in the target's unit if the target is numeric, else null.
- "evidence_id" and "evidence_quote": the block id and the exact sentence you relied on (copied verbatim — it will be checked); null if UNVERIFIABLE.

Return JSON: {{"verdict": "MET|MISSED|PARTIAL|UNVERIFIABLE", "actual_value": ..., "actual_number": ..., "evidence_id": ..., "evidence_quote": ..., "explanation": "one sentence"}}"""


@dataclass
class Verdict:
    claim_id: str
    verdict: str
    actual_value: str | None
    actual_number: float | None
    evidence_id: str | None
    evidence_quote: str | None
    evidence_page: int | None
    evidence_doc_type: str | None
    explanation: str
    method: str  # "llm" | "numeric" | "downgraded:quote-not-found" | "llm-error"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("|", " ")).strip().lower()


def _parse(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        return json.loads(text[a : b + 1])
    except json.JSONDecodeError:
        return {}


_LOWER_BETTER = re.compile(
    r"\b(tax|etr|cost|expense|attrition|debt|leverage|dso|days sales|onsite mix|churn|capex intensity)\b", re.I
)
_HIGHER_BETTER = re.compile(
    r"\b(growth|revenue|margin|profit|eps|cash flow|fcf|roe|roce|hiring|freshers|headcount|deal|tcv|dividend|utili[sz]ation|payout)\b",
    re.I,
)


def direction(metric: str | None) -> str:
    """'higher' when exceeding the target is good, 'lower' when undershooting is good, else 'neutral'."""
    m = metric or ""
    if _LOWER_BETTER.search(m):
        return "lower"
    if _HIGHER_BETTER.search(m):
        return "higher"
    return "neutral"


def numeric_verdict(target: dict | None, actual: float | None, metric: str | None = None) -> str | None:
    """Deterministic verdict for numeric targets. None when it cannot be computed.

    A range is MET inside it, and also when beaten in the good direction
    (growth above the top of a growth range is a beat, not a miss). Just
    outside on the bad side is PARTIAL (10% of the range width, ≥ 0.5 units),
    further is MISSED. Slack floor is 0.1 units so a 1–3% range does not stretch to 0.5%.
    """
    if not target or actual is None:
        return None
    kind = target.get("kind")
    unit = (target.get("unit") or "").lower()
    if "change" in unit or (kind in ("min", "max") and (target.get("value") or 0) == 0):
        # "lower than last year" / "at least no worse": a direction, not a level — the sign of the
        # model's actual_number is ambiguous here, so the verdict is left to the judge.
        return None
    d = direction(metric)
    if kind == "range":
        lo, hi = target["low"], target["high"]
        if lo is None or hi is None:
            return None
        if lo <= actual <= hi:
            return "MET"
        if actual > hi:
            if d == "higher":
                return "MET"
            slack = max(abs(hi - lo) * 0.10, 0.1)
            return "PARTIAL" if actual <= hi + slack else "MISSED"
        if d == "lower":
            return "MET"
        slack = max(abs(hi - lo) * 0.10, 0.1)
        return "PARTIAL" if actual >= lo - slack else "MISSED"
    v = target.get("value")
    if v is None:
        return None
    if kind == "min":
        return "MET" if actual >= v else ("PARTIAL" if actual >= v * 0.95 else "MISSED")
    if kind == "max":
        return "MET" if actual <= v else ("PARTIAL" if actual <= v * 1.05 else "MISSED")
    if kind == "point":
        tol = max(abs(v) * 0.05, 0.25)
        if abs(actual - v) <= tol:
            return "MET"
        beat = (actual > v and d == "higher") or (actual < v and d == "lower")
        if beat:
            return "MET"
        return "PARTIAL" if abs(actual - v) <= tol * 3 else "MISSED"
    return None


_Q = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
_FORWARD_ONLY = re.compile(
    r"\b(expect(s|ed)?|guidance|guide|will|shall|target(s)?|aim|outlook|plan(s|ned)?|anticipate|forecast)\b", re.I
)
_REPORTED = re.compile(
    r"\b(was|were|stood at|came in|reported|delivered|grew|declined|increased|decreased|reduced|closed|signed|onboarded|hired|"
    r"achieved|improved|expanded|generated|returned|paid|crossed|remained|ended|recruited)\b",
    re.I,
)


def claim_period_end(period: str | None) -> tuple[int, int] | None:
    """('FY27' → (27, 4)), ('Q1 FY26' → (26, 1)); None when the period is not a single FY/quarter."""
    if not period:
        return None
    m = re.search(
        r"\b(?:Q([1-4])\s*)?(?:FY|fiscal(?: year)?|financial year)\s*'?(?:20)?(\d{2})\b(?:\s*Q([1-4]))?", period, re.I
    )
    if not m:
        return None
    if re.search(r"\b(and beyond|onwards|medium|long)\b", period, re.I):
        return None
    fy = int(m.group(2))
    q = int(m.group(1) or m.group(3) or 4)
    return fy, q


def period_has_ended(period: str | None, latest_reported: tuple[int, int] | None) -> bool | None:
    """True/False when both sides are known; None when the claim's period cannot be parsed."""
    end = claim_period_end(period)
    if end is None or latest_reported is None:
        return None
    return latest_reported >= end


def is_forward_looking(text: str) -> bool:
    """A sentence that promises rather than reports (no reported-result verb, at least one forward cue)."""
    return bool(_FORWARD_ONLY.search(text)) and not _REPORTED.search(text)


def _target_text(t: dict | None) -> str:
    if not t:
        return "qualitative"
    u = t.get("unit") or ""
    if t["kind"] == "range":
        return f"between {t['low']} and {t['high']} {u}".strip()
    return {"min": "at least", "max": "at most", "point": "about"}[t["kind"]] + f" {t['value']} {u}".rstrip()


def _blocks(items: list[dict]) -> str:
    return "\n\n".join(
        f"[{e['id']}] ({e.get('doc_type')}, page {e.get('page')}{', ' + e['speaker'] if e.get('speaker') else ''})\n{e['text']}"
        for e in items
    )


async def judge_claim(
    claim: Claim,
    evidence: list[dict],
    *,
    model: str | None = None,
    latest_reported: tuple[int, int] | None = None,
    baseline: list[dict] | None = None,
) -> Verdict:
    # A full-year or quarter commitment cannot have an outcome before that period has ended.
    if period_has_ended(claim.period, latest_reported) is False:
        fy, q = claim_period_end(claim.period)
        return Verdict(
            claim.id,
            "UNVERIFIABLE",
            None,
            None,
            None,
            None,
            None,
            None,
            f"{claim.period} has not ended: the latest reported period is Q{latest_reported[1]} FY{latest_reported[0]:02d}, the claim needs Q{q} FY{fy:02d}.",
            "period-not-ended",
        )
    baseline_text = (
        "\nBASELINE — the metric as reported in the period the claim was made (compare the evidence against this "
        "for 'improve' / 'lower than' / 'maintain' claims):\n" + _blocks(baseline) + "\n"
        if baseline
        else ""
    )
    prompt = VERIFY_PROMPT.format(
        claim=claim.claim,
        metric=claim.metric or "-",
        period=claim.period or "-",
        target=_target_text(claim.target),
        evidence=_blocks(evidence) or "(none)",
        baseline=baseline_text,
    )
    try:
        resp = await agenerate(prompt, model=model, max_tokens=600, temperature=0.0, json_mode=True, think=False)
    except LLMError as e:
        return Verdict(claim.id, "UNVERIFIABLE", None, None, None, None, None, None, f"LLM error: {e}", "llm-error")
    out = _parse(resp.text)
    verdict = str(out.get("verdict") or "UNVERIFIABLE").upper()
    if verdict not in VERDICTS:
        verdict = "UNVERIFIABLE"
    quote = out.get("evidence_quote")
    eid = out.get("evidence_id")
    by_id = {e["id"]: e for e in evidence}
    cited = by_id.get(str(eid).strip("[]")) if eid else None
    method = "llm"
    page = doc_type = None

    if verdict != "UNVERIFIABLE":
        ok = False
        if quote:
            nq = _norm(str(quote))
            if cited and nq and nq in _norm(cited["text"]):
                ok = True
            else:  # the model may have mislabelled the block: accept the quote if it is in any evidence block
                for e in evidence:
                    if nq and nq in _norm(e["text"]):
                        cited, ok = e, True
                        break
            if not ok:  # or trimmed / lightly rephrased it: ≥ 70% of its tokens in one block (as for claims)
                hit = _match_quote(str(quote), [{"sentence": e["text"], **e} for e in evidence])
                if hit is not None:
                    cited, ok = hit, True
        if not ok:
            verdict, method = "UNVERIFIABLE", "downgraded:quote-not-found"
        elif cited.get("kind") not in ("row", "table") and is_forward_looking(str(quote)):
            # the model cited a promise ("we expect…", "guidance is…") as if it were a result
            verdict, method = "UNVERIFIABLE", "downgraded:evidence-is-a-promise"
        else:
            page, doc_type = cited.get("page"), cited.get("doc_type")

    actual_number = out.get("actual_number")
    try:
        actual_number = float(actual_number) if actual_number is not None else None
    except (TypeError, ValueError):
        actual_number = None

    # Ratios a person would compute from two reported figures (FCF / net profit, tax / PBT):
    # if both are in the evidence, the computed value replaces whatever the model said.
    from finsight.verification.derived import derived_actual

    unit = (claim.target or {}).get("unit") or ""
    derived = (
        derived_actual(claim.metric, [e["text"] for e in evidence], claim.period)
        if claim.target and unit == "%"
        else None
    )
    if derived is not None:
        actual_number, note = derived
        if verdict == "UNVERIFIABLE":
            verdict = "MET"  # provisional; the numeric rule below decides
            cited = next((e for e in evidence if e["text"][:80] in note), evidence[0] if evidence else None)
            if cited:
                page, doc_type = cited.get("page"), cited.get("doc_type")
        out["explanation"] = f"{note}. {out.get('explanation') or ''}".strip()
        out["actual_value"] = f"{actual_number}%"
        method = "derived"

    if verdict != "UNVERIFIABLE":
        computed = numeric_verdict(claim.target, actual_number, claim.metric)
        if computed and computed != verdict:
            logger.info(
                "numeric override for %s: llm=%s computed=%s (actual=%s target=%s)",
                claim.id,
                verdict,
                computed,
                actual_number,
                claim.target,
            )
            verdict, method = computed, ("derived" if method == "derived" else "numeric")
        elif computed and method != "derived":
            method = "numeric"

    return Verdict(
        claim_id=claim.id,
        verdict=verdict,
        actual_value=(
            str(out["actual_value"]) if out.get("actual_value") is not None and verdict != "UNVERIFIABLE" else None
        ),
        actual_number=actual_number if verdict != "UNVERIFIABLE" else None,
        evidence_id=cited["id"] if (cited and verdict != "UNVERIFIABLE") else None,
        evidence_quote=(str(quote) if (quote and verdict != "UNVERIFIABLE") else None),
        evidence_page=page,
        evidence_doc_type=doc_type,
        explanation=str(out.get("explanation") or ""),
        method=method,
    )
