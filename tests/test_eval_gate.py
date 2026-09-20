from eval.gate import check


def _report(hit1=0.8, hit5=0.99, mrr=0.9, cov=1.0):
    return {"modes": {"v2": {"hit@1": hit1, "hit@5": hit5, "mrr": mrr}}, "coverage": {"coverage": cov}}


T = {"mode": "v2", "hit@1": 0.70, "hit@5": 0.95, "mrr": 0.82, "coverage": 1.0}


def test_passes_above_thresholds():
    assert check(_report(), T) == []


def test_each_metric_can_fail():
    assert check(_report(hit5=0.90), T) == ["v2 hit@5 = 0.900 < 0.950"]
    assert any("coverage" in f for f in check(_report(cov=0.98), T))
    assert any("mrr" in f for f in check(_report(mrr=0.5), T))


def test_missing_mode():
    assert check({"modes": {"dense": {}}}, T)[0].startswith("mode 'v2' not in report")
