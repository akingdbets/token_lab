"""
통계 스크립트 (stats) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stats import compare, fallback_qids, load_trials, mcnemar_exact, paired_stats, percentile  # noqa: E402


def trial(qid, comp, acc, raw=100, tokens=100, prompt=110, completion=10, correct=None, used_original=False):
    return {"run_id": "r", "qid": qid, "qtype": "fact", "compressor": comp, "answer_accuracy": acc,
            "correct": acc == 1.0 if correct is None else correct, "input_tokens_raw": raw, "input_tokens": tokens,
            "prompt_tokens": prompt, "completion_tokens": completion, "compress_sec": 0.5,
            "info": {"trace": {"used_original": used_original}}}


def args(**kw):
    base = dict(binary="full", boot=500, seed=1, level=0.95, price_in=None, price_out=None)
    return Namespace(**{**base, **kw})


class McNemarTest(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(4, 0), 0.125)        # 2 × (1/2)^4
        self.assertAlmostEqual(mcnemar_exact(5, 0), 0.0625)
        self.assertAlmostEqual(mcnemar_exact(3, 3), 1.0)
        self.assertAlmostEqual(mcnemar_exact(1, 9), 2 * 11 / 1024)


class PercentileTest(unittest.TestCase):
    def test_interpolates(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertEqual(percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(percentile([7], 0.025), 7)


class PairedStatsTest(unittest.TestCase):
    def test_point_estimates_match_summary_definitions(self):
        pairs = [(trial("a", "none", 1.0), trial("a", "x", 1.0, raw=100, tokens=50)),
                 (trial("b", "none", 1.0), trial("b", "x", 0.5, raw=300, tokens=250))]
        s = paired_stats(pairs, boot=200, seed=0, level=0.95)
        self.assertEqual(s["answer_accuracy"]["value"], 0.75)
        self.assertEqual(s["retention_pct"]["value"], 75.0)
        self.assertEqual(s["diff"]["value"], -0.25)
        self.assertEqual(s["input_reduction_pct"]["value"], 25.0)    # 토큰 합 400 → 300
        lo, hi = s["answer_accuracy"]["ci"]
        self.assertLessEqual(lo, 0.75)
        self.assertGreaterEqual(hi, 0.75)

    def test_same_seed_same_interval(self):
        pairs = [(trial(str(i), "none", 1.0), trial(str(i), "x", i % 2)) for i in range(20)]
        a = paired_stats(pairs, boot=300, seed=7, level=0.9)
        b = paired_stats(pairs, boot=300, seed=7, level=0.9)
        self.assertEqual(a, b)


class CompareTest(unittest.TestCase):
    def test_mcnemar_counts_and_cost(self):
        trials = [trial("a", "none", 1.0, prompt=1000), trial("a", "x", 0.5, prompt=600),
                  trial("b", "none", 1.0, prompt=1000), trial("b", "x", 1.0, prompt=600),
                  trial("c", "none", 0.0, prompt=1000), trial("c", "x", 1.0, prompt=600)]
        res = compare(trials, ["x"], args(price_in=2.0, price_out=0.0))
        m = res["x"]["mcnemar"]
        self.assertEqual((m["none_only"], m["compressor_only"]), (1, 1))
        self.assertEqual(res["x"]["cost"]["prompt_tokens_mean"], 600)
        self.assertEqual(res["none"]["cost"]["usd_per_1k_queries"], 2.0)       # 1000 토큰 × 1000 질의 × $2/1M
        self.assertEqual(res["x"]["cost"]["usd_saved_per_1k_queries"], 0.8)
        self.assertEqual(res["x"]["cost"]["usd_saved_pct"], 40.0)

    def test_binary_correct_uses_ox_field(self):
        trials = [trial("a", "none", 0.5, correct=True), trial("a", "x", 0.5, correct=False)]
        self.assertEqual(compare(trials, ["x"], args(binary="correct"))["x"]["mcnemar"]["none_only"], 1)
        self.assertEqual(compare(trials, ["x"], args(binary="full"))["x"]["mcnemar"]["none_only"], 0)

    def test_unpaired_and_missing_accuracy_are_skipped(self):
        trials = [trial("a", "none", 1.0), trial("a", "x", None), trial("b", "x", 1.0)]
        self.assertNotIn("x", compare(trials, ["x"], args()))


class LoadTest(unittest.TestCase):
    def write(self, d: Path, rows):
        d.mkdir()
        (d / "trials.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def test_merges_runs_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = Path(tmp, "a"), Path(tmp, "b"), Path(tmp, "c")
            self.write(a, [trial("q1", "none", 1.0)])
            self.write(b, [trial("q2", "none", 1.0)])
            self.write(c, [trial("q1", "none", 1.0)])
            self.assertEqual(len(load_trials([a, b])), 2)
            with self.assertRaises(SystemExit):
                load_trials([a, c])

    def test_fallback_qids(self):
        trials = [trial("a", "x", 1.0, used_original=True), trial("b", "x", 1.0),
                  trial("c", "none", 1.0, used_original=True)]
        self.assertEqual(fallback_qids(trials), {"a"})


if __name__ == "__main__":
    unittest.main()
