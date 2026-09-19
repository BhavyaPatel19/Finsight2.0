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
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)
