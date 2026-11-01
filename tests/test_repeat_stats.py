"""
repeat_stats (반복 실행 평균·표준편차·Wilcoxon·McNemar) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repeat_stats import aggregate, describe, mcnemar_exact, wilcoxon_exact  # noqa: E402


class StatsTest(unittest.TestCase):
    def test_mcnemar_exact(self):
        self.assertIsNone(mcnemar_exact(0, 0))
        self.assertEqual(mcnemar_exact(3, 0), 0.25)          # 2 * (1/8)
        self.assertEqual(mcnemar_exact(5, 5), 1.0)

    def test_wilcoxon_exact_known_values(self):
        # 모두 양수인 n=5: 가장 극단, 양측 p = 2/32
        self.assertEqual(wilcoxon_exact([1, 2, 3, 4, 5])["p"], 0.0625)
        r = wilcoxon_exact([0, 0.5, -0.5, 1])                 # 0 제외, |0.5| 동점 평균 순위 1.5
        self.assertEqual((r["n_nonzero"], r["w_plus"], r["w_minus"]), (3, 4.5, 1.5))
        self.assertIsNone(wilcoxon_exact([0, 0])["p"])

    def test_describe(self):
        d = describe([1.0, 3.0, None])
        self.assertEqual((d["n"], d["mean"], d["min"], d["max"]), (2, 2.0, 1.0, 3.0))
        self.assertAlmostEqual(d["std"], 1.4142, places=4)

    def test_aggregate_pairs_items_across_runs(self):
        def run(rule_accs):
            trials = [{"qid": f"q{i}", "compressor": "none", "answer_accuracy": 1.0} for i in range(3)]
            trials += [{"qid": f"q{i}", "compressor": "rule", "answer_accuracy": a} for i, a in enumerate(rule_accs)]
            summary = {"results": {"none": {"answer_accuracy": 1.0, "by_type": {}},
                                   "rule": {"answer_accuracy": sum(rule_accs) / 3, "by_type": {},
                                            "answer_accuracy_retention_pct": 100 * sum(rule_accs) / 3}}}
            return summary, trials
        res = aggregate([run([1.0, 0.0, 1.0]), run([1.0, 0.5, 1.0])])
        t = res["compressors"]["rule"]["tests"]
        self.assertEqual((t["n_items"], t["items_worse"], t["mean_diff"]), (3, ["q1"], -0.25))
        self.assertEqual(t["mcnemar_pooled"], {"b_base_only": 2, "c_comp_only": 0, "p": 0.5})
        m = res["compressors"]["rule"]["metrics"]["answer_accuracy"]
        self.assertEqual((m["n"], m["mean"]), (2, 0.75))


if __name__ == "__main__":
    unittest.main()
