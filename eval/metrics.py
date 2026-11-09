"""Ranking metrics over binary relevance lists. Pure functions, no I/O."""

from __future__ import annotations

import math


def hit_at_k(rels: list[int], k: int) -> float:
    return 1.0 if any(rels[:k]) else 0.0


def reciprocal_rank(rels: list[int], k: int) -> float:
    for i, r in enumerate(rels[:k]):
        if r:
            return 1.0 / (i + 1)
    return 0.0


def dcg(rels: list[int], k: int) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def ndcg_at_k(rels: list[int], k: int, n_relevant: int | None = None) -> float:
    """Binary nDCG. Ideal DCG assumes min(n_relevant, k) relevant items at the top."""
    ideal_n = min(n_relevant if n_relevant is not None else sum(rels), k)
    if ideal_n == 0:
        return 0.0
    ideal = sum(1.0 / math.log2(i + 2) for i in range(ideal_n))
    return dcg(rels, k) / ideal


def precision_at_k(rels: list[int], k: int) -> float:
    return sum(rels[:k]) / k if k else 0.0


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Agreement between two labelers beyond chance. Returns 1.0 for perfect agreement."""
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty label lists")
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


# ── Uncertainty ─────────────────────────────────────────────────────────────
# Gold sets here are tens of items, so a point estimate alone overstates what a run shows:
# 61/64 and 64/64 are both inside each other's interval. Every headline number gets one.


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95 % Wilson score interval for a proportion k/n — sound at 0 % and 100 %, unlike the
    normal approximation, which is exactly where small gold sets land."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def bootstrap_ci(items: list, stat, n_boot: int = 2000, seed: int = 13, alpha: float = 0.05):
    """Percentile bootstrap interval of ``stat(sample)`` resampling ``items`` with replacement.
    For statistics with no closed form here (MRR, κ). Seeded, so a rerun reports the same
    interval for the same rows. Resamples where ``stat`` raises are skipped."""
    import random

    if len(items) < 2:
        return None
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        sample = [items[rng.randrange(len(items))] for _ in items]
        try:
            vals.append(float(stat(sample)))
        except (ValueError, ZeroDivisionError):
            continue
    if len(vals) < n_boot // 2:
        return None
    vals.sort()
    lo = vals[int(alpha / 2 * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return (round(lo, 4), round(hi, 4))
