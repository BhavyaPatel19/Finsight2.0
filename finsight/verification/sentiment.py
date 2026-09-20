"""
Division-level FinBERT sentiment on the v2 index.

A "division" is a section when the document has them (annual reports, press
releases), else a speaker (transcripts: management vs. each analyst), else the
whole document. Every sentence of every prose chunk is scored, in batches —
nothing is truncated.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from finsight.corpus.chunker import split_sentences
from finsight.ml.finbert import analyze_batch
from finsight.retrieval import index as ix

logger = logging.getLogger(__name__)

MIN_SENTENCE_CHARS = 20
MAX_DIVISIONS = 12


def division_sentences(document_id: int) -> dict[str, list[str]]:
    """{division_name: [sentence, …]} from the document's prose chunks, de-duplicated across overlaps."""
    chunks = [
        c
        for c in ix.all_chunks()
        if c["metadata"].get("document_id") == document_id and c["metadata"].get("kind") == "prose"
    ]
    if not chunks:
        return {}
    have_sections = any(c["metadata"].get("section") for c in chunks)
    have_speakers = any(c["metadata"].get("speaker") for c in chunks)
    groups: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for c in sorted(chunks, key=lambda c: c["metadata"].get("chunk_index", 0)):
        m = c["metadata"]
        if have_sections and m.get("section"):
            name = m["section"]
        elif have_speakers and m.get("speaker"):
            name = m["speaker"]
        else:
            name = "Full document"
        for s in split_sentences(c["text"]):
            key = s.strip().lower()
            if len(s) < MIN_SENTENCE_CHARS or key in seen:
                continue
            seen.add(key)
            groups[name].append(s)
    # keep the largest divisions; fold the rest into "Other"
    if len(groups) > MAX_DIVISIONS:
        ranked = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
        kept = dict(ranked[:MAX_DIVISIONS])
        kept["Other"] = [s for _, ss in ranked[MAX_DIVISIONS:] for s in ss]
        groups = kept
    return dict(groups)


def score_divisions(document_id: int) -> list[dict]:
    """[{division_name, positive_score, negative_score, neutral_score, overall_score, sentence_count}]"""
    groups = division_sentences(document_id)
    out = []
    for name, sentences in groups.items():
        if not sentences:
            continue
        try:
            probs = analyze_batch(sentences, batch_size=32)
        except Exception as e:  # model unavailable — report nothing rather than zeros that look like data
            logger.warning("FinBERT failed for %s/%s: %s", document_id, name, e)
            continue
        n = len(probs)
        pos = sum(p["positive"] for p in probs) / n
        neg = sum(p["negative"] for p in probs) / n
        neu = sum(p["neutral"] for p in probs) / n
        out.append(
            {
                "division_name": name,
                "positive_score": round(pos, 4),
                "negative_score": round(neg, 4),
                "neutral_score": round(neu, 4),
                "overall_score": round(pos - neg, 4),
                "sentence_count": n,
            }
        )
    return out
