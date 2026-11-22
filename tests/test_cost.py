"""
cost.py: 단가표 기반 비용 계산과 재계산 (가짜 토큰 값, 네트워크 없음).

    python -m unittest tests.test_cost
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cost import compute_cost, cost_from_fields, find_price, load_pricing, recompute_costs  # noqa: E402
from llm import LLMResult  # noqa: E402

M = 1_000_000


def _res(**kw):
    base = dict(text="a", prompt_tokens=0, completion_tokens=0, latency=0.1, model="gpt-6.1-sol")
    base.update(kw)
    return LLMResult(**base)


class PricingFileTest(unittest.TestCase):
    def test_values(self):
        p = load_pricing()
        self.assertEqual(p["gpt-6.1-sol"]["input"], 2.0)
        self.assertEqual(p["gpt-6.1-sol"]["cache_read"], 0.10)
        self.assertEqual(p["gpt-6.1-sol"]["cache_write"], 2.50)
        self.assertEqual(p["gpt-6.1-sol"]["output"], 10.0)
        self.assertEqual(p["deepseek-flash"], {**p["deepseek-flash"], "input": 0.30, "cache_read": 0.006,
                                               "cache_write": None, "output": 1.20})

    def test_prefix_match(self):
        key, _ = find_price("gpt-6.1-sol-2026-11-01", load_pricing())
        self.assertEqual(key, "gpt-6.1-sol")
        self.assertEqual(find_price("unknown-model", load_pricing()), (None, None))


class ComputeTest(unittest.TestCase):
    def test_full_cache_info(self):
        c = compute_cost(_res(prompt_tokens=1_000_000, completion_tokens=100_000,
                              cached_tokens=600_000, cache_write_tokens=200_000))
        # 200k*2 + 600k*0.1 + 200k*2.5 + 100k*10 (per 1M)
        self.assertAlmostEqual(c.usd, (200_000 * 2 + 600_000 * 0.1 + 200_000 * 2.5 + 100_000 * 10) / M)
        self.assertEqual(c.cost_source, "api")

    def test_no_cache_info(self):
        c = compute_cost(_res(prompt_tokens=1000, completion_tokens=10))
        self.assertAlmostEqual(c.usd, (1000 * 2 + 10 * 10) / M)
        self.assertEqual(c.cost_source, "no_cache_info")

    def test_no_cache_write_info(self):
        c = compute_cost(_res(prompt_tokens=1000, completion_tokens=0, cached_tokens=400))
        self.assertAlmostEqual(c.usd, (600 * 2 + 400 * 0.1) / M)
        self.assertEqual(c.cost_source, "no_cache_write_info")

    def test_reasoning_not_double_counted(self):
        a = compute_cost(_res(prompt_tokens=0, completion_tokens=500, reasoning_tokens=400,
                              cached_tokens=0, cache_write_tokens=0))
        self.assertAlmostEqual(a.usd, 500 * 10 / M)

    def test_deepseek_no_write_price(self):
        c = compute_cost(_res(model="deepseek-flash", prompt_tokens=2000, completion_tokens=100,
                              cached_tokens=1792))
        self.assertAlmostEqual(c.usd, (208 * 0.30 + 1792 * 0.006 + 100 * 1.20) / M)
        self.assertEqual(c.cost_source, "api")      # 쓰기 단가가 없는 모델은 쓰기 정보가 없어도 api

    def test_estimate_and_no_pricing(self):
        c = compute_cost(_res(prompt_tokens=100, completion_tokens=1, cached_tokens=50, usage_source="estimate"))
        self.assertEqual(c.cost_source, "estimate")
        self.assertAlmostEqual(c.usd, (100 * 2 + 10) / M)
        n = compute_cost(_res(model="other"))
        self.assertIsNone(n.usd)
        self.assertEqual(n.cost_source, "no_pricing")


class RecomputeTest(unittest.TestCase):
    def test_recompute_with_new_pricing(self):
        rows = [{"model": "gpt-6.1-sol", "prompt_tokens": 1000, "completion_tokens": 0,
                 "cached_tokens": None, "cache_write_tokens": None, "usage_source": "api", "cost": {"usd": 999}}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            pricing = {"gpt-6.1-sol": {"input": 4.0, "cache_read": 0.1, "cache_write": 2.5, "output": 10.0}}
            self.assertEqual(recompute_costs(p, pricing=pricing), 1)
            out = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
        self.assertAlmostEqual(out["cost"]["usd"], 1000 * 4 / M)
        self.assertEqual(out["cost"]["cost_source"], "no_cache_info")

    def test_cost_from_fields_matches_compute(self):
        r = _res(prompt_tokens=3000, completion_tokens=50, cached_tokens=1024, cache_write_tokens=0)
        self.assertEqual(compute_cost(r), cost_from_fields("gpt-6.1-sol", 3000, 50, 1024, 0))


if __name__ == "__main__":
    unittest.main()
