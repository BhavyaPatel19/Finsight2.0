"""
CrediSentiment service — combines:
  Feature 1: Division-level FinBERT sentiment analysis
  Feature 2: 'Walking the Talk' LLM credibility comparison
"""

import asyncio
import json
import logging
import re

from sqlmodel import Session, select

from finsight.config import (
    WTT_ACTUALS_TOP_K,
    WTT_BATCH_SIZE,
    WTT_MAX_CLAIMS,
    WTT_MAX_CLAIMS_CHUNKS,
    WTT_MODEL,
    WTT_PARALLEL,
)
from finsight.credisentiment.prompts import (
    STAGE1_BATCH_EXTRACT_PROMPT,
    STAGE2_VERIFY_CLAIMS_PROMPT,
    deduplicate_claims,
    parse_json_array,
    parse_json_object,
    strip_think_tags,
)
from finsight.llm import LLMError, agenerate
from finsight.ml.finbert import analyze_batch, split_financial_sentences
from finsight.models import (
    ComparisonChunk,
    DivisionSentiment,
    Document,
    DocumentSection,
    PageMetadata,
    WalkTheTalkResult,
)
from finsight.rag.service import process_for_rag

# ---------------------------------------------------------------------------
# Feature 1 — Division-level FinBERT Sentiment
# ---------------------------------------------------------------------------


def _get_division_texts(session: Session, document_id: int) -> dict[str, str]:
    """
    Group document text by top-level section headings (divisions).
    Uses DocumentSection + PageMetadata tables populated during RAG indexing.
    Falls back to splitting the raw text by common heading patterns.
    """
    # Try structured sections first
    stmt = (
        select(DocumentSection)
        .where(
            DocumentSection.document_id == document_id,
            DocumentSection.level == 1,  # top-level sections only
        )
        .order_by(DocumentSection.start_page)
    )
    sections = list(session.exec(stmt).all())

    if sections:
        division_texts: dict[str, str] = {}
        for sec in sections:
            end_page = sec.end_page or sec.start_page + 5  # default span
            page_stmt = (
                select(PageMetadata)
                .where(
                    PageMetadata.document_id == document_id,
                    PageMetadata.page_number >= sec.start_page,
                    PageMetadata.page_number <= end_page,
                )
                .order_by(PageMetadata.page_number)
            )
            pages = list(session.exec(page_stmt).all())
            text = "\n".join(p.text for p in pages if p.text)
            if text.strip():
                division_texts[sec.title] = text
        if division_texts:
            return division_texts

    # Fallback: use PageMetadata section_title grouping
    page_stmt = select(PageMetadata).where(PageMetadata.document_id == document_id).order_by(PageMetadata.page_number)
    pages = list(session.exec(page_stmt).all())

    if pages:
        division_texts = {}
        for p in pages:
            key = p.section_title or "General"
            if key not in division_texts:
                division_texts[key] = ""
            division_texts[key] += "\n" + (p.text or "")
        # Filter out empty
        return {k: v.strip() for k, v in division_texts.items() if v.strip()}

    # Last resort: read raw text and split by headings
    doc = session.get(Document, document_id)
    if doc and doc.text_path:
        try:
            text = open(doc.text_path, encoding="utf-8").read()
        except Exception:
            return {"Full Document": text if "text" in dir() else ""}
        # Split on lines that look like headings (ALL CAPS, short)
        parts = re.split(r"\n([A-Z][A-Z &/\-]{4,})\n", text)
        if len(parts) > 2:
            divisions = {}
            for i in range(1, len(parts), 2):
                heading = parts[i].strip()
                body = parts[i + 1] if i + 1 < len(parts) else ""
                if body.strip():
                    divisions[heading] = body.strip()
            if divisions:
                return divisions
        return {"Full Document": text[:15000]}

    return {}


def _run_finbert_on_text(text: str) -> dict:
    """Run FinBERT in batches of 32 with dynamic padding; return aggregated scores."""
    sentences = split_financial_sentences(text, min_length=15)
    sentences = sentences[:500]  # cap for performance
    if not sentences:
        sentences = [text[:512]]

    try:
        batch_results = analyze_batch(sentences, batch_size=32)
    except Exception:
        return {
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 0.0,
            "overall": 0.0,
            "count": 0,
        }

    n = len(batch_results)
    if n == 0:
        return {"positive": 0.0, "negative": 0.0, "neutral": 0.0, "overall": 0.0, "count": 0}

    pos_sum = sum(r["positive"] for r in batch_results)
    neg_sum = sum(r["negative"] for r in batch_results)
    neu_sum = sum(r["neutral"] for r in batch_results)

    return {
        "positive": round(pos_sum / n, 4),
        "negative": round(neg_sum / n, 4),
        "neutral": round(neu_sum / n, 4),
        "overall": round((pos_sum - neg_sum) / n, 4),
        "count": n,
    }


def analyze_division_sentiment(session: Session, document_id: int) -> list[DivisionSentiment]:
    """
    Run FinBERT division-level sentiment on a document.
    Auto-indexes for RAG if not already done to get section structure.
    """
    doc = session.get(Document, document_id)
    if not doc:
        return []

    # Ensure document is RAG-indexed (populates PageMetadata / DocumentSection)
    if doc.status != "indexed":
        result = process_for_rag(session, document_id)
        if result.get("status") == "error":
            return []
        # Refresh doc
        session.refresh(doc)

    # Get text grouped by division
    division_texts = _get_division_texts(session, document_id)
    if not division_texts:
        # Fallback: whole document as single division
        if doc.text_path:
            try:
                full = open(doc.text_path, encoding="utf-8").read()
                division_texts = {"Full Document": full[:15000]}
            except Exception:
                return []

    # Delete old results for this document
    old = session.exec(select(DivisionSentiment).where(DivisionSentiment.document_id == document_id)).all()
    for o in old:
        session.delete(o)
    session.commit()

    # Run FinBERT on each division
    results = []
    for div_name, text in division_texts.items():
        scores = _run_finbert_on_text(text)
        row = DivisionSentiment(
            document_id=document_id,
            symbol=doc.symbol,
            division_name=div_name,
            positive_score=scores["positive"],
            negative_score=scores["negative"],
            neutral_score=scores["neutral"],
            overall_score=scores["overall"],
            sentence_count=scores["count"],
        )
        session.add(row)
        results.append(row)

    session.commit()
    for r in results:
        session.refresh(r)

    return results


# ---------------------------------------------------------------------------
# Feature 2 — "Walking the Talk" two-stage claim verification
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# Forward-looking keywords for pre-filtering claim-rich chunks
_CLAIM_KEYWORDS = [
    "target",
    "guidance",
    "expect",
    "plan to",
    "aim",
    "goal",
    "outlook",
    "project",
    "intend",
    "forecast",
    "aspire",
    "commit",
    "promise",
    "anticipate",
    "envision",
    "strategy",
    "initiative",
    "fy2",
    "fy 2",
    "growth",
    "increase",
    "expand",
    "reduce",
    "achieve",
    "deliver",
    "milestone",
    "pipeline",
    "launch",
    "capex",
    "margin",
    "debt-free",
    "dividend",
]


def _effective_parallel() -> int:
    """Concurrent LLM calls. A local Ollama serves one request at a time by
    default, so parallel requests just queue and time each other out."""
    from finsight.llm import get_provider

    if get_provider().name == "ollama":
        return 1
    return max(1, WTT_PARALLEL)


async def _call_wtt_llm(
    prompt: str,
    max_tokens: int = 2048,
    json_mode: bool = True,
) -> str:
    """WTT-specific async LLM call via the configured provider.

    Uses WTT_MODEL when set, else the provider default. Returns "" on
    failure so the JSON parsers yield nothing rather than a bogus verdict.
    """
    try:
        resp = await agenerate(
            prompt,
            model=WTT_MODEL or None,
            max_tokens=max_tokens,
            temperature=0.0,
            json_mode=json_mode,
            think=False,  # structured extraction; a reasoning trace only slows it down and leaks into JSON
        )
        return resp.text
    except LLMError as e:
        logger.error("WTT LLM call failed: %s", e)
        return ""


def _score_chunk_for_claims(text: str) -> float:
    """Score a chunk by forward-looking keyword density (0-1)."""
    text_lower = text.lower()
    hits = sum(1 for kw in _CLAIM_KEYWORDS if kw in text_lower)
    return hits / len(_CLAIM_KEYWORDS)


def _prefilter_claims_chunks(chunks: list[str], max_n: int = WTT_MAX_CLAIMS_CHUNKS) -> list[str]:
    """Keep only the top N most claim-rich chunks by keyword scoring."""
    scored = [(chunk, _score_chunk_for_claims(chunk)) for chunk in chunks]
    # Filter out chunks with zero score (no forward-looking language)
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_n]]


def _batch_chunks(chunks: list[str], batch_size: int = WTT_BATCH_SIZE) -> list[str]:
    """Combine chunks into batched prompt texts with separators."""
    batches = []
    for i in range(0, len(chunks), batch_size):
        group = chunks[i : i + batch_size]
        parts = []
        for j, chunk in enumerate(group):
            parts.append(f"---EXCERPT {j + 1}---\n{chunk}")
        batches.append("\n\n".join(parts))
    return batches


def _retrieve_relevant_actuals(
    claims: list[dict],
    actuals_document_id: int,
    top_k: int = WTT_ACTUALS_TOP_K,
) -> str:
    """Use ChromaDB semantic search to find actuals chunks relevant to claims."""
    from finsight.credisentiment.vectorstore import query_by_document_id
    from finsight.rag.service import get_embedding_model

    model = get_embedding_model()

    # Build search queries from claim summaries grouped by category
    categories: dict[str, list[str]] = {}
    for c in claims:
        cat = c.get("category", "other")
        claim_text = c.get("claim", "")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(claim_text)

    # One query per category (search with concatenated claims)
    seen_ids: set[str] = set()
    all_texts: list[str] = []

    for cat, cat_claims in categories.items():
        query_text = f"{cat}: " + "; ".join(cat_claims[:3])
        prefixed = f"Represent this sentence for searching relevant passages: {query_text}"
        embedding = model.encode(prefixed, convert_to_numpy=True, normalize_embeddings=True).tolist()
        results = query_by_document_id(embedding, actuals_document_id, n_results=top_k)
        for r in results:
            rid = r.get("id", "")
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_texts.append(r.get("text", ""))

    return "\n\n---\n\n".join(all_texts)


def get_document_chunks(session: Session, document_id: int) -> list[str]:
    """Load all CrediSentiment chunks for a document, ordered by chunk_index."""
    stmt = (
        select(ComparisonChunk).where(ComparisonChunk.document_id == document_id).order_by(ComparisonChunk.chunk_index)
    )
    chunks = list(session.exec(stmt).all())
    return [c.text for c in chunks]


async def walk_the_talk(
    session: Session,
    claims_document_id: int,
    actuals_document_id: int,
) -> WalkTheTalkResult | None:
    """
    Optimized two-stage async pipeline using Qwen 2.5:
      Stage 1: Pre-filter → batch → parallel extract claims
      Stage 2: Semantic retrieval of actuals → verify claims
    Target: 3-5 minutes instead of hours.
    """
    claims_doc = session.get(Document, claims_document_id)
    actuals_doc = session.get(Document, actuals_document_id)
    if not claims_doc or not actuals_doc:
        return None

    if claims_doc.cs_status != "indexed" or actuals_doc.cs_status != "indexed":
        return None

    claims_chunks = get_document_chunks(session, claims_document_id)
    actuals_chunks = get_document_chunks(session, actuals_document_id)
    if not claims_chunks or not actuals_chunks:
        return None

    logger.info(
        "WTT: %d claims chunks, %d actuals chunks (model=%s)",
        len(claims_chunks),
        len(actuals_chunks),
        WTT_MODEL or "provider-default",
    )

    # ------------------------------------------------------------------
    # Stage 1: Pre-filter → batch → parallel extract claims
    # ------------------------------------------------------------------
    filtered = _prefilter_claims_chunks(claims_chunks)
    logger.info("WTT Stage 1: %d/%d chunks after pre-filter", len(filtered), len(claims_chunks))

    if not filtered:
        return None

    batched_prompts = _batch_chunks(filtered)
    parallel = _effective_parallel()
    logger.info("WTT Stage 1: %d batched prompts, %d parallel", len(batched_prompts), parallel)

    semaphore = asyncio.Semaphore(parallel)

    def _parse_claims_response(raw: str) -> list[dict]:
        """Parse LLM response into list of claim dicts with 'claim' field."""
        clean = strip_think_tags(raw)
        obj = parse_json_object(clean)

        candidates: list[dict] = []
        if "claims" in obj and isinstance(obj["claims"], list):
            candidates = [c for c in obj["claims"] if isinstance(c, dict)]
        else:
            # Flatten category-keyed objects
            for key, val in obj.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            if "category" not in item:
                                item["category"] = key
                            candidates.append(item)
            if not candidates:
                arr = parse_json_array(clean)
                candidates = [c for c in arr if isinstance(c, dict)]

        # Only keep items that have a proper 'claim' sentence (>20 chars)
        return [c for c in candidates if isinstance(c.get("claim"), str) and len(c["claim"]) > 20]

    async def _extract_batch(batch_text: str) -> list[dict]:
        async with semaphore:
            prompt = STAGE1_BATCH_EXTRACT_PROMPT.format(chunks_text=batch_text)
            raw = await _call_wtt_llm(prompt, max_tokens=2048)
            claims = _parse_claims_response(raw)
            if claims:
                return claims
            # Retry once without JSON mode if no valid claims
            logger.info("WTT Stage 1: retrying batch without JSON mode")
            raw = await _call_wtt_llm(prompt, max_tokens=2048, json_mode=False)
            return _parse_claims_response(raw)

    tasks = [_extract_batch(bp) for bp in batched_prompts]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_claims: list[dict] = []
    for i, result in enumerate(batch_results):
        if isinstance(result, Exception):
            logger.warning("WTT Stage 1 batch %d failed: %s", i, result)
            continue
        all_claims.extend(result)

    unique_claims = deduplicate_claims(all_claims)
    logger.info("WTT Stage 1: %d total claims → %d unique", len(all_claims), len(unique_claims))

    if not unique_claims:
        return None

    # ------------------------------------------------------------------
    # Stage 2: Batched verification — 7 claims per LLM call
    # ------------------------------------------------------------------
    # Cap claims for reasonable processing time (WTT_MAX_CLAIMS; silently limits recall)
    if len(unique_claims) > WTT_MAX_CLAIMS:
        unique_claims = unique_claims[:WTT_MAX_CLAIMS]
        logger.info("WTT: capped to %d claims for Stage 2", len(unique_claims))
    STAGE2_BATCH = 7
    claim_batches = [unique_claims[i : i + STAGE2_BATCH] for i in range(0, len(unique_claims), STAGE2_BATCH)]
    logger.info("WTT Stage 2: %d claim batches of %d", len(claim_batches), STAGE2_BATCH)

    # Pre-retrieve actuals for each batch (sequential — embedding model not thread-safe)
    batch_actuals: list[str] = []
    for bc in claim_batches:
        actuals_text = _retrieve_relevant_actuals(bc, actuals_document_id, top_k=WTT_ACTUALS_TOP_K)
        if len(actuals_text) > 4000:
            actuals_text = actuals_text[:4000]
        batch_actuals.append(actuals_text)
    logger.info("WTT Stage 2: pre-retrieved actuals for %d batches", len(batch_actuals))

    stage2_semaphore = asyncio.Semaphore(min(2, parallel))  # fewer parallel for longer prompts

    async def _verify_batch(batch_claims: list[dict], actuals_text: str) -> list[dict]:
        async with stage2_semaphore:
            prompt = STAGE2_VERIFY_CLAIMS_PROMPT.format(
                claims_json=json.dumps(batch_claims, indent=2),
                actuals_text=actuals_text,
            )
            raw = await _call_wtt_llm(prompt, max_tokens=4096)
            clean = strip_think_tags(raw)
            result = parse_json_object(clean)
            verified = result.get("verified_claims", result.get("claims", []))
            logger.info("WTT Stage 2 batch: %d/%d claims verified", len(verified), len(batch_claims))
            return verified

    verify_tasks = [_verify_batch(bc, ba) for bc, ba in zip(claim_batches, batch_actuals, strict=True)]
    verify_results = await asyncio.gather(*verify_tasks, return_exceptions=True)

    claims_list: list[dict] = []
    for i, vr in enumerate(verify_results):
        if isinstance(vr, Exception):
            logger.warning("WTT Stage 2 batch %d failed: %s", i, vr)
            continue
        claims_list.extend([c for c in vr if isinstance(c, dict)])

    # Compute overall score from verdicts
    if claims_list:
        met = sum(1 for c in claims_list if str(c.get("verdict", "")).upper() == "MET")
        partial = sum(1 for c in claims_list if str(c.get("verdict", "")).upper() == "PARTIAL")
        total = len(claims_list)
        overall_score = round((met + 0.5 * partial) / total * 100, 2) if total > 0 else 50
    else:
        overall_score = 50

    # Generate narrative summary from a final LLM call
    narrative_prompt = f"""Based on these verification results, write a 2-3 sentence executive summary of management credibility.
Verified claims: {json.dumps(claims_list, indent=2)}
Overall score: {overall_score}/100
Respond with ONLY the summary text, no JSON."""
    narrative = await _call_wtt_llm(narrative_prompt, max_tokens=256, json_mode=False)
    narrative = strip_think_tags(narrative).strip('"').strip()
    if not narrative or narrative.startswith("[LLM error"):
        narrative = f"Credibility score: {overall_score}/100 based on {len(claims_list)} verified claims."
    logger.info("WTT Stage 2: %d claims verified, score=%.1f", len(claims_list), overall_score)

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------
    old = session.exec(
        select(WalkTheTalkResult).where(
            WalkTheTalkResult.claims_document_id == claims_document_id,
            WalkTheTalkResult.actuals_document_id == actuals_document_id,
        )
    ).all()
    for o in old:
        session.delete(o)
    session.commit()

    symbol = claims_doc.symbol or actuals_doc.symbol or "UNKNOWN"
    row = WalkTheTalkResult(
        claims_document_id=claims_document_id,
        actuals_document_id=actuals_document_id,
        symbol=symbol,
        overall_score=round(overall_score, 2),
        claims_json=json.dumps(claims_list),
        narrative_summary=narrative,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    logger.info("WTT complete: score=%.1f, %d claims verified", overall_score, len(claims_list))
    return row
