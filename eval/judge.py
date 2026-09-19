"""
LLM-as-judge for generated answers, implemented on finsight.llm so the
prompts are in the repo and any provider can judge.

faithfulness  – decompose the answer into atomic claims, verify each claim
                against the retrieved context only; score = supported / total.
correctness   – compare the answer with the human reference: correct,
                partial or incorrect (numbers must match to be "correct").
"""
from __future__ import annotations

import json
import re

from finsight.llm import LLMError, generate

CLAIMS_PROMPT = """Break the ANSWER below into its atomic factual claims — one fact per claim, each self-contained (repeat the subject, keep numbers and units exactly). Ignore hedges and citations. If the answer says the information was not found, return an empty list.

ANSWER:
{answer}

Return JSON: {{"claims": ["...", "..."]}}"""

VERIFY_PROMPT = """You are checking whether each CLAIM is supported by the CONTEXT. A claim is "supported" only if the context states it (numbers must match; equivalent phrasing is fine). Use nothing but the context.

CONTEXT:
{context}

CLAIMS:
{claims}

Return JSON: {{"verdicts": [{{"claim": "...", "supported": true|false, "reason": "..."}}]}} in the same order as the claims."""

CORRECTNESS_PROMPT = """Compare a generated ANSWER with the REFERENCE answer to the same QUESTION.

QUESTION: {question}
REFERENCE: {reference}
ANSWER: {answer}

Grade:
- "correct": the answer states the same facts/numbers as the reference (extra correct detail is fine)
- "partial": some but not all of the reference facts, or right facts with a wrong/missing number
- "incorrect": contradicts the reference, answers a different question, or says the information was not found when the reference has it

Return JSON: {{"grade": "correct|partial|incorrect", "reason": "..."}}"""


def _json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _call(prompt: str, model: str | None, max_tokens: int = 1024) -> dict:
    try:
        r = generate(prompt, model=model, max_tokens=max_tokens, temperature=0.0, json_mode=True, think=False)
        return _json(r.text)
    except LLMError as e:
        return {"error": str(e)}


def judge_faithfulness(answer: str, contexts: list[str], model: str | None = None) -> dict:
    """{"claims": n, "supported": k, "score": k/n | None, "verdicts": [...]}"""
    claims = _call(CLAIMS_PROMPT.format(answer=answer), model, max_tokens=600).get("claims") or []
    claims = [c for c in claims if isinstance(c, str) and c.strip()]
    if not claims:
        return {"claims": 0, "supported": 0, "score": None, "verdicts": []}
    context = "\n\n---\n\n".join(contexts)
    verdicts = _call(
        VERIFY_PROMPT.format(context=context, claims="\n".join(f"- {c}" for c in claims)), model, max_tokens=1200
    ).get("verdicts") or []
    supported = sum(1 for v in verdicts if isinstance(v, dict) and v.get("supported") is True)
    return {"claims": len(claims), "supported": supported, "score": supported / len(claims), "verdicts": verdicts}


def judge_correctness(question: str, reference: str, answer: str, model: str | None = None) -> dict:
    out = _call(CORRECTNESS_PROMPT.format(question=question, reference=reference, answer=answer), model, max_tokens=300)
    grade = str(out.get("grade", "")).lower()
    if grade not in ("correct", "partial", "incorrect"):
        grade = "unknown"
    return {"grade": grade, "reason": out.get("reason", out.get("error", ""))}
