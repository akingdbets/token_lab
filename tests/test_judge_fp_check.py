"""
judge_fp_check (틀린 답 세트로 judge FP 확인) 의 판정 집계 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from judge_fp_check import label, rates, read_set  # noqa: E402


class JudgeFpCheckTest(unittest.TestCase):
    def test_human_overrides_expected(self):
        self.assertEqual(label({"expected": "X", "human": ""}), "X")
        self.assertEqual(label({"expected": "X", "human": "o"}), "O")

    def test_rates(self):
        rows = [{"label": "X", "judge": "O"}, {"label": "X", "judge": "X"}, {"label": "X", "judge": "?"},
                {"label": "O", "judge": "X"}, {"label": "O", "judge": "O"}]
        r = rates(rows)
        self.assertEqual((r["fp"], r["n_expected_x"], r["fp_rate"]), (1, 2, 0.5))
        self.assertEqual((r["fn"], r["n_expected_o"], r["unread"]), (1, 2, 1))

    def test_committed_set_is_consistent(self):
        rows = read_set(ROOT / "docs" / "results" / "judge_fp_set_v1.csv")
        qids = {r["qid"] for r in rows}
        self.assertEqual(len(qids), 25)
        self.assertTrue(all(r["expected"] in ("O", "X") and r["how"] for r in rows))
        # 문항마다 틀리게 만든 fact 가 하나 이상
        self.assertTrue(all(any(r["expected"] == "X" for r in rows if r["qid"] == q) for q in qids))


if __name__ == "__main__":
    unittest.main()
