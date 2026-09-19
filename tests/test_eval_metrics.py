"""Ranking metrics and RRF fusion — pure functions, no models."""
import math

import pytest

from eval.metrics import cohen_kappa, hit_at_k, mean, ndcg_at_k, precision_at_k, reciprocal_rank
from finsight.rag.retrieval import chunk_id, reciprocal_rank_fusion


class TestRankingMetrics:
    def test_hit_at_k(self):
        assert hit_at_k([0, 0, 1], 3) == 1.0
        assert hit_at_k([0, 0, 1], 2) == 0.0
        assert hit_at_k([], 5) == 0.0

    def test_reciprocal_rank(self):
        assert reciprocal_rank([0, 1, 0], 3) == 0.5
        assert reciprocal_rank([1, 1], 2) == 1.0
        assert reciprocal_rank([0, 0, 0, 1], 3) == 0.0  # beyond cutoff

    def test_ndcg_perfect_and_worst(self):
        assert ndcg_at_k([1, 0, 0], 3, n_relevant=1) == 1.0
        assert ndcg_at_k([0, 0, 1], 3, n_relevant=1) == pytest.approx(1 / math.log2(4))
        assert ndcg_at_k([0, 0, 0], 3, n_relevant=1) == 0.0
        assert ndcg_at_k([0, 0, 0], 3) == 0.0  # nothing relevant anywhere

    def test_ndcg_multiple_relevant(self):
        # two relevant at ranks 1 and 3 vs ideal at 1 and 2
        got = ndcg_at_k([1, 0, 1], 3, n_relevant=2)
        ideal = 1 + 1 / math.log2(3)
        assert got == pytest.approx((1 + 1 / math.log2(4)) / ideal)

    def test_precision_and_mean(self):
        assert precision_at_k([1, 0, 1, 0, 0], 5) == 0.4
        assert mean([]) == 0.0 and mean([1, 2, 3]) == 2.0


class TestKappa:
    def test_perfect_agreement(self):
        assert cohen_kappa(["MET", "MISSED", "PARTIAL"], ["MET", "MISSED", "PARTIAL"]) == 1.0

    def test_chance_level_is_zero(self):
        # labeler B ignores A entirely; balanced labels → kappa ≈ 0
        a = ["MET", "MET", "MISSED", "MISSED"]
        b = ["MET", "MISSED", "MET", "MISSED"]
        assert cohen_kappa(a, b) == pytest.approx(0.0)

    def test_rejects_bad_input(self):
        with pytest.raises(ValueError):
            cohen_kappa(["MET"], [])


def _hit(doc, idx, page=None):
    meta = {"document_id": doc, "chunk_index": idx}
    if page is not None:
        meta["page_number"] = page
    return {"text": f"chunk {doc}-{idx}", "metadata": meta}


class TestRRF:
    def test_shared_hit_outranks_single_list_hits(self):
        dense = [_hit(1, 0), _hit(1, 1), _hit(2, 0)]
        bm25 = [_hit(3, 0), _hit(1, 1)]
        fused = reciprocal_rank_fusion(dense, bm25)
        assert chunk_id(fused[0]) == "doc_1_chunk_1"  # appears in both lists
        assert {chunk_id(h) for h in fused} == {"doc_1_chunk_0", "doc_1_chunk_1", "doc_2_chunk_0", "doc_3_chunk_0"}
        assert all("rrf_score" in h for h in fused)

    def test_prefers_hit_with_page_metadata(self):
        without_page = _hit(1, 0)
        with_page = _hit(1, 0, page=7)
        fused = reciprocal_rank_fusion([without_page], [with_page])
        assert fused[0]["metadata"]["page_number"] == 7

    def test_empty_inputs(self):
        assert reciprocal_rank_fusion([], []) == []
