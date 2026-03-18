"""
Prompt templates and parsing utilities for the two-stage
Walking-the-Talk credibility pipeline.
"""

import json
import re

from finsight.models.enums import ClaimCategory

# ---------------------------------------------------------------------------
# Dynamic category list from enum
# ---------------------------------------------------------------------------

_CATEGORY_LIST = ", ".join(e.value for e in ClaimCategory)

# ---------------------------------------------------------------------------
# Stage 1: Extract forward-looking claims from a concall chunk
# ---------------------------------------------------------------------------

STAGE1_EXTRACT_CLAIMS_PROMPT = f"""You are a financial analyst. Extract all forward-looking claims, promises, and guidance from the following earnings call transcript excerpt.

Categories: {_CATEGORY_LIST}

For each claim found, output a JSON array with objects containing:
- "claim": the exact forward-looking statement
- "category": one of the categories listed above
- "claimed_value": the numeric target or qualitative promise (e.g. "20% growth", "debt-free by FY26")
- "context_snippet": a short surrounding quote for traceability

Transcript excerpt:
{{chunk_text}}

Respond ONLY with a JSON array. No preamble, no explanation."""

# ---------------------------------------------------------------------------
# Stage 2: Verify claims against actual results
# ---------------------------------------------------------------------------

STAGE2_VERIFY_CLAIMS_PROMPT = """You are a financial auditor verifying whether management delivered on their promises.

Below are claims extracted from a previous earnings call, followed by the actual financial results.

**Claims to verify:**
{claims_json}

**Actual results:**
{actuals_text}

For each claim, determine:
- "verdict": one of MET, MISSED, or PARTIAL
- "actual_value": what actually happened
- "explanation": brief comparison

Also provide:
- "overall_score": 0-100 credibility score
- "narrative_summary": 2-3 sentence assessment

Respond ONLY with a JSON object in this format:
{{
  "verified_claims": [
    {{
      "claim": "<original claim>",
      "category": "<category>",
      "verdict": "MET|MISSED|PARTIAL",
      "actual_value": "<what happened>",
      "explanation": "<brief comparison>"
    }}
  ],
  "overall_score": <0-100>,
  "narrative_summary": "<assessment>"
}}"""


# ---------------------------------------------------------------------------
# Parsing utilities
# ---------------------------------------------------------------------------

def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from DeepSeek R1 output.

    Handles: closed tags, unclosed <think>, orphan </think>, multiple blocks.
    """
    # Pass 1: remove properly closed <think>...</think>
    result = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Pass 2: remove unclosed <think> to end of string
    result = re.sub(r"<think>.*$", "", result, flags=re.DOTALL)
    # Pass 3: remove orphan </think>
    result = result.replace("</think>", "")
    return result.strip()


def parse_json_array(text: str) -> list:
    """Extract first JSON array from text, handling markdown fences and preamble."""
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return []
    try:
        return json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return []


def parse_json_object(text: str) -> dict:
    """Extract first JSON object from text, handling markdown fences and preamble."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return {}


def deduplicate_claims(claims: list[dict]) -> list[dict]:
    """Remove duplicate claims keyed on (category, claim prefix).

    Keeps the first occurrence. Key is (category.lower(), claim[:80].lower().strip()).
    """
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for c in claims:
        cat = str(c.get("category", "")).lower()
        claim_prefix = str(c.get("claim", ""))[:80].lower().strip()
        key = (cat, claim_prefix)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result
