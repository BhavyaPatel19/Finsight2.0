import json

from eval.bench import bench_generation, pct


def test_pct():
    assert pct([1, 2, 3, 4, 5], 50) == 3 and pct([1, 2, 3, 4, 5], 95) == 5 and pct([], 50) == 0.0


def test_generation_cost(tmp_path):
    rows = [
        {"latency_ms": 1000, "usage": {"prompt_tokens": 4000, "completion_tokens": 200}},
        {"latency_ms": 3000, "usage": {"prompt_tokens": 4000, "completion_tokens": 400}},
    ]
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"model": "openai/gpt-oss-120b", "provider": "groq", "rows": rows}))
    out = bench_generation(p)
    assert out["n"] == 2 and out["prompt_tokens"]["mean"] == 4000 and out["latency_ms"]["p50"] == 1000
    assert abs(out["usd_per_answer"]["mean"] - ((4000 * 0.15 + 300 * 0.60) / 1e6)) < 1e-5
    p.write_text(json.dumps({"model": "qwen3:14b", "provider": "ollama", "rows": rows}))
    assert bench_generation(p)["usd_per_answer"] == "n/a (local model)"
