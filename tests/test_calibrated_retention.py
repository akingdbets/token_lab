"""
보정 유지율 (experiment.calibrated_retention) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from experiment import answer_core_in_context, calibrated_retention, memory_suspect  # noqa: E402


class MemorySuspectTest(unittest.TestCase):
    def test_core_missing_but_correct_is_suspect(self):
        item = {"answer": "DUMMY_HASH", "key_entities": ["DUMMY_HASH"]}
        self.assertTrue(answer_core_in_context("it checks DUMMY_HASH here", item))
        self.assertFalse(answer_core_in_context("nothing relevant", item))
        self.assertTrue(memory_suspect(False, 1.0))
        self.assertTrue(memory_suspect(False, 0.5))
        self.assertFalse(memory_suspect(False, 0.4))
        self.assertFalse(memory_suspect(True, 1.0))
        self.assertFalse(memory_suspect(False, None))


class CalibratedRetentionTest(unittest.TestCase):
    def test_floor_is_subtracted_on_paired_items(self):
        none = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0}
        empty = {"a": 0.0, "b": 0.0, "c": 1.0, "d": None}     # d 는 짝에서 빠짐
        comp = {"a": 1.0, "b": 0.0, "c": 1.0, "d": 0.0}
        r = calibrated_retention(none, empty, comp)
        self.assertEqual(r["n_paired"], 3)
        self.assertAlmostEqual(r["gap"], 0.6667, places=4)
        # (2/3 - 1/3) / (1 - 1/3) = 50%
        self.assertEqual(r["calibrated_retention_pct"], 50.0)

    def test_small_gap_is_null(self):
        none = {"a": 1.0, "b": 1.0}
        r = calibrated_retention(none, {"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 0.0})
        self.assertEqual(r["gap"], 0.0)
        self.assertIsNone(r["calibrated_retention_pct"])

    def test_no_pairs(self):
        self.assertIsNone(calibrated_retention({}, {}, {"a": 1.0})["calibrated_retention_pct"])


if __name__ == "__main__":
    unittest.main()
