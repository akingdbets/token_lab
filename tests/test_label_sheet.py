"""
label_sheet (라벨링 시트 생성) 과 judge_agreement --judged (판정 파일 붙이기) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from label_sheet import ASSIGNEES, assign_mixed, build, write_csv  # noqa: E402


def trial(qid, qtype, comp, acc, sats):
    return {"qid": qid, "qtype": qtype, "compressor": comp, "answer_accuracy": acc,
            "response": f"{qid}-{comp}", "fact_results": [{"fact": f"{qid} f{i}", "satisfied": s}
                                                          for i, s in enumerate(sats)]}


class LabelSheetTest(unittest.TestCase):
    def test_none_rows_plus_changed_compressor_rows_without_judge(self):
        trials = [trial("c1", "fact", "none", 1.0, [True, True]),
                  trial("c1", "fact", "rule", 0.5, [True, False]),    # 정확도 바뀜 -> 추가
                  trial("c2", "code", "none", 1.0, [True]),
                  trial("c2", "code", "rule", 1.0, [True]),           # 같음 -> 제외
                  trial("c3", "code", "none", None, [None])]          # judge 못 읽음
        sheet, judged = build(trials)
        self.assertEqual([(r["qid"], r["compressor"]) for r in sheet],
                         [("c1", "none"), ("c1", "none"), ("c1", "rule"), ("c1", "rule"),
                          ("c2", "none"), ("c3", "none")])
        self.assertTrue(all(r["human"] == "" and "judge" not in r for r in sheet))
        self.assertEqual([r["judge"] for r in judged], ["O", "O", "O", "X", "O", "?"])
        # 한 문항은 한 사람
        self.assertEqual(len({r["assignee"] for r in sheet if r["qid"] == "c1"}), 1)

    def test_types_spread_across_assignees(self):
        qtypes = {f"q{i}": t for i, t in enumerate(["fact"] * 4 + ["code"] * 4)}
        out = assign_mixed(qtypes, {q: 1 for q in qtypes})
        for a in ASSIGNEES:
            mine = [qtypes[q] for q, who in out.items() if who == a]
            self.assertEqual(sorted(mine), ["code", "fact"])


class AgreementJudgedTest(unittest.TestCase):
    def test_judged_file_is_joined_and_unread_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            sheet, judged = Path(d, "s.csv"), Path(d, "j.csv")
            rows = [{"qid": "c1", "assignee": "A", "type": "fact", "compressor": "none", "fact_idx": i,
                     "key_fact": "f", "answer": "a", "human": h, "note": ""} for i, h in enumerate("OXO")]
            write_csv(sheet, rows, list(rows[0]))
            write_csv(judged, [{"qid": "c1", "compressor": "none", "fact_idx": i, "jds": v}
                               for i, v in enumerate("OO?")], ["qid", "compressor", "fact_idx", "jds"])
            out = subprocess.run([sys.executable, str(ROOT / "src" / "judge_agreement.py"), str(sheet),
                                  "--judged", str(judged)], capture_output=True, text=True,
                                 encoding="utf-8", env={"PYTHONIOENCODING": "utf-8", "SYSTEMROOT": "C:\\Windows"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("| jds | 2 | 0.500 (1/2) | 1 | 0 |", out.stdout)
        self.assertIn("못 읽은 행 1개", out.stdout)


if __name__ == "__main__":
    unittest.main()
