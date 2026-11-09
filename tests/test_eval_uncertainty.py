"""Confidence intervals on eval numbers, and pacing for free-tier LLM providers."""

import httpx
import pytest

from eval.metrics import bootstrap_ci, cohen_kappa, mean, wilson_ci
from eval.wtt import summarise
from finsight.llm import _retry
from finsight.llm.base import LLMError


class TestIntervals:
    def test_wilson_matches_the_reference_value(self):
        lo, hi = wilson_ci(61, 64)  # 95.3 %
        assert lo == pytest.approx(0.8707, abs=1e-3) and hi == pytest.approx(0.9839, abs=1e-3)

    def test_wilson_is_sound_at_the_edges(self):
        lo, hi = wilson_ci(64, 64)  # a "perfect" 1.000 on 64 items is not certainty
        assert hi == 1.0 and 0.94 < lo < 0.95
        assert wilson_ci(0, 10)[0] == 0.0
        assert wilson_ci(0, 0) is None

    def test_bootstrap_is_seeded_and_brackets_the_estimate(self):
        rr = [1.0, 0.5, 1.0, 0.0, 1.0, 0.33, 1.0, 1.0, 0.5, 1.0]
        a, b = bootstrap_ci(rr, mean), bootstrap_ci(rr, mean)
        assert a == b and a[0] <= mean(rr) <= a[1]
        assert bootstrap_ci([1.0], mean) is None

    def test_wtt_summary_carries_intervals(self):
        labels = ["MET", "MISSED", "PARTIAL", "MET", "UNVERIFIABLE", "MET", "MISSED", "MET"]
        system = ["MET", "MISSED", "MET", "MET", "UNVERIFIABLE", "MET", "MISSED", "PARTIAL"]
        rows = [
            {"id": f"c{i}", "matched": True, "human": h, "system": s, "similarity": 0.9}
            for i, (h, s) in enumerate(zip(labels, system, strict=True))
        ] + [{"id": "c9", "matched": False, "human": "MET", "system": None, "similarity": 0.1}]
        s = summarise(rows, {"p": 8})
        assert s["ci95"]["verdict_accuracy"] == wilson_ci(6, 8)
        assert s["ci95"]["claim_recall"] == wilson_ci(8, 9)
        lo, hi = s["ci95"]["kappa"]
        assert lo <= cohen_kappa(labels, system) <= hi


class TestPacing:
    def test_budget_admits_until_the_minute_is_full_then_waits(self):
        b = _retry.TokenBudget(1000)
        assert b._wait_for(600, now=0.0) == 0.0
        assert b._wait_for(300, now=10.0) == 0.0
        wait = b._wait_for(400, now=20.0)  # 900 used: the first 600 must expire, at t=60
        assert wait == pytest.approx(40.0)
        assert b._wait_for(400, now=61.0) == 0.0

    def test_a_call_larger_than_the_budget_is_capped_not_stuck(self):
        b = _retry.TokenBudget(500)
        assert b._wait_for(5000, now=0.0) == 0.0

    def test_estimate_counts_prompt_and_reserved_completion(self):
        payload = {"messages": [{"role": "user", "content": "x" * 3500}], "max_tokens": 600}
        assert _retry.TokenBudget.estimate(payload) == 1600

    def test_requests_per_minute_are_paced_too(self):
        b = _retry.TokenBudget(0, rpm=2)
        assert b._wait_for(10, now=0.0) == 0.0 and b._wait_for(10, now=5.0) == 0.0
        assert b._wait_for(10, now=6.0) == pytest.approx(54.0)  # third call waits for the first
        assert b._wait_for(10, now=60.0) == 0.0

    def test_budget_is_off_unless_configured(self, monkeypatch):
        monkeypatch.delenv("LLM_TOKENS_PER_MINUTE", raising=False)
        monkeypatch.delenv("LLM_REQUESTS_PER_MINUTE", raising=False)
        assert _retry.budget() is None
        monkeypatch.setenv("LLM_TOKENS_PER_MINUTE", "7000")
        assert _retry.budget().tpm == 7000
        monkeypatch.setenv("LLM_REQUESTS_PER_MINUTE", "4")
        assert _retry.budget().rpm == 4

    def test_a_daily_quota_fails_fast_instead_of_sleeping_for_hours(self, monkeypatch):
        slept = []
        monkeypatch.setattr(_retry.time, "sleep", slept.append)
        transport = httpx.MockTransport(lambda req: httpx.Response(429, headers={"retry-after": "7200"}))
        with httpx.Client(transport=transport) as client, pytest.raises(LLMError, match="quota exhausted"):
            _retry.post_with_retry(client, "https://x/chat", json={"messages": []})
        assert slept == []

    def test_a_per_minute_429_waits_the_hinted_time(self, monkeypatch):
        slept = []
        monkeypatch.setattr(_retry.time, "sleep", slept.append)
        replies = iter([httpx.Response(429, headers={"retry-after": "12"}), httpx.Response(200, json={})])
        transport = httpx.MockTransport(lambda req: next(replies))
        with httpx.Client(transport=transport) as client:
            assert _retry.post_with_retry(client, "https://x/chat", json={"messages": []}).status_code == 200
        assert slept == [12.0]
