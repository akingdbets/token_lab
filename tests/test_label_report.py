import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import label_report as LR  # noqa: E402


def write_csv(path: Path, rows: list[dict], encoding="utf-8-sig"):
    with open(path, "w", encoding=encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class LabelReportTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_error_section_counts_crosstab_and_recovery(self):
        base = {"qtype": "fact", "질문": "", "정답": "", "모델 답변": "", "근거 인용문 원문": "", "압축 후 같은 구절": "",
                "메모": ""}
        rows = [{"qid": "q1", "압축기": "llmlingua2_r30", "사람 분류": "3", **base},
                {"qid": "q2", "압축기": "llmlingua2_r30", "사람 분류": "1 정답 구절 삭제", **base},
                {"qid": "q3", "압축기": "llmlingua2_r50", "사람 분류": "", **base}]
        write_csv(self.d / "err.csv", rows, encoding="cp949")
        write_csv(self.d / "err_key.csv", [{"qid": "q1", "압축기": "llmlingua2_r30", "자동 분류": "A"},
                                           {"qid": "q2", "압축기": "llmlingua2_r30", "자동 분류": "C"},
                                           {"qid": "q3", "압축기": "llmlingua2_r50", "자동 분류": "B (code)"}])
        run = self.d / "run"
        run.mkdir()
        (run / "trials.jsonl").write_text("\n".join(json.dumps(t) for t in [
            {"qid": "q1", "compressor": "llmlingua2_r30", "answer_accuracy": 1.0},
            {"qid": "q2", "compressor": "llmlingua2_r30", "answer_accuracy": 0.0}]), encoding="utf-8")
        text = "\n".join(LR.error_section(self.d / "err.csv", [("luna", run)], self.d / "err_key.csv"))
        self.assertIn("**2 / 3**", text)
        self.assertIn("| 사람 분류 | llmlingua2_r30 | 합 |", text)   # 라벨이 있는 압축기 열만
        self.assertIn("| 3 표기 분해 | 1 | 1 |", text)
        self.assertIn("| 1 정답 구절 삭제 | 0 | 1 |", text)           # 교차표: 자동 A 0, C 1
        self.assertIn("| 3 표기 분해 | 1 | 1/1 (100%) |", text)
        self.assertIn("|  전체 | 2 | 1/2 (50%) |", text)

    def test_error_class_rejects_unknown_value(self):
        with self.assertRaises(SystemExit):
            LR.error_class("7", "x")

    def test_judge_section_agreement_kappa_and_lists(self):
        sheet = [{"row_id": f"T{i}", "담당자": "A", "qid": f"q{i}", "유형": "fact", "설정": "기본", "압축 조건": "none",
                  "fact_idx": "0", "질문": "", "핵심 사실": f"fact {i}", "참고 정답": "", "모델 답변": "ans",
                  "human": h, "메모": ""} for i, h in enumerate(["O", "O", "X", "X", ""])]
        key = [{"row_id": f"T{i}", "judge": j, "run": "r", "compressor": "none", "answer_accuracy": "1.0",
                "partial": "0"} for i, j in enumerate(["O", "X", "X", "O", "O"])]
        write_csv(self.d / "sheet.csv", sheet)
        write_csv(self.d / "key.csv", key)
        text = "\n".join(LR.judge_section(self.d / "sheet.csv", self.d / "key.csv"))
        self.assertIn("**4 / 5**", text)
        # 사람 O,O,X,X / judge O,X,X,O: 일치 2/4, FP 1 (T3), FN 1 (T1), κ 0
        self.assertIn("| 전체 | 4 | 0.500 (2/4) | 1 | 1 | 0.000 |", text)
        self.assertIn("| judge YES 행 | 2 | 0.500 (1/2) | 1 | 0 | - |", text)   # judge 한 값뿐이면 κ 없음
        self.assertIn("### FP (사람 X, judge O): 1", text)
        self.assertIn("| T3 | q3 |", text)


if __name__ == "__main__":
    unittest.main()
