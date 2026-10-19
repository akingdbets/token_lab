"""
closed_book_check 의 문항 판정·집계 테스트 (LLM 은 mock, 네트워크 호출 없음).

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from closed_book_check import check_item, is_unknown, subset_report, summarize  # noqa: E402


@dataclass
class Res:
    text: str
    prompt_tokens: int = 20
    completion_tokens: int = 5
    usage_source: str = "api"
    finish_reason: str | None = "stop"
    model: str = "m"


class Answer:
    def __init__(self, text):
        self.text = text

    def ask(self, prompt):
        assert "Answer the question from your own knowledge" in prompt
        return Res(self.text)


class Judge:
    def __init__(self):
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        return Res("YES")


ITEM = {"id": "c1", "split": "dev", "type": "fact", "question": "Q?", "answer": "15",
        "key_entities": ["15"], "key_facts": ["expiry is 15 minutes", "uses timedelta"]}


class ClosedBookCheckTest(unittest.TestCase):
    def test_unknown_skips_judge(self):
        j = Judge()
        row = check_item(ITEM, Answer("UNKNOWN."), j)
        self.assertTrue(row["unknown"])
        self.assertFalse(row["knows"])
        self.assertEqual((row["cb_accuracy"], j.calls), (0.0, 0))

    def test_answered_is_judged_per_fact(self):
        j = Judge()
        row = check_item(ITEM, Answer("It expires after 15 minutes."), j)
        self.assertTrue(row["knows"])
        self.assertEqual((row["cb_accuracy"], j.calls, row["satisfied_facts"]), (1.0, 2, 2))

    def test_empty_answer_is_not_judged(self):
        j = Judge()
        row = check_item(ITEM, Answer(""), j)
        self.assertTrue(row["empty"])
        self.assertEqual((row["cb_accuracy"], j.calls), (None, 0))
        # 예전 기록처럼 빈 답변에 judge 점수가 남아 있어도 집계에서 뺀다
        old = {**row, "cb_accuracy": 1.0}
        old.pop("empty")
        s = summarize([old])
        self.assertEqual((s["all"]["cb_accuracy"], s["all"]["cb_ge_0_5"], s["all"]["empty"]), (None, 0, 1))

    def test_is_unknown(self):
        self.assertTrue(is_unknown(" unknown"))
        self.assertFalse(is_unknown("15 minutes"))

    def test_summarize_by_split_and_type(self):
        rows = [check_item(ITEM, Answer("15 minutes"), Judge()),
                check_item({**ITEM, "id": "c2", "type": "code"}, Answer("UNKNOWN"), Judge())]
        s = summarize(rows)
        self.assertEqual((s["all"]["n"], s["all"]["knows"], s["all"]["unknown_rate"]), (2, 1, 0.5))
        self.assertEqual(s["dev"]["fact"]["cb_accuracy"], 1.0)
        self.assertEqual(s["dev"]["code"]["cb_accuracy"], 0.0)

    def test_subset_report_excludes_closed_book_items(self):
        cb = [{"qid": "c1", "knows": True, "cb_accuracy": 1.0, "response": "x"},
              {"qid": "c2", "knows": False, "cb_accuracy": 0.5, "response": "x"},
              {"qid": "c3", "knows": False, "cb_accuracy": 0.0, "response": "x"}]
        trials = [{"qid": q, "compressor": c, "answer_accuracy": a} for q, c, a in [
            ("c1", "none", 1.0), ("c1", "rule", 0.0),
            ("c2", "none", 1.0), ("c2", "rule", 1.0),
            ("c3", "none", 1.0), ("c3", "rule", 0.5)]]
        rep = subset_report(trials, cb)
        self.assertEqual(rep["all"]["answer_accuracy"]["rule"], 0.5)
        self.assertEqual((rep["exclude_A"]["n"], rep["exclude_A"]["excluded"]), (2, ["c1"]))
        self.assertEqual(rep["exclude_A"]["retention_pct"]["rule"], 75.0)
        self.assertEqual(rep["exclude_B_ge_0_5"]["excluded"], ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()
