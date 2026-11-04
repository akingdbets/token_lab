import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import judge_sensitivity as JS  # noqa: E402


def trial(qid, comp, facts, not_found=False):
    sat = sum(facts)
    return {"qid": qid, "compressor": comp, "answer_accuracy": sat / max(len(facts), 1) if facts or not_found else None,
            "total_facts": len(facts) or 1, "not_found": not_found,
            "fact_results": [] if not_found else [{"fact": "f", "satisfied": s} for s in facts]}


class JudgeSensitivityTest(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        ts = []
        for i in range(10):
            ts.append(trial(f"q{i}", "none", [True, True]))
            ts.append(trial(f"q{i}", "rule", [True, False] if i < 4 else [True, True]))
            ts.append(trial(f"q{i}", "llmlingua2_r30", [], not_found=True) if i < 5 else trial(f"q{i}", "llmlingua2_r30", [True, True]))
        (self.run / "trials.jsonl").write_text("\n".join(map(json.dumps, ts)), encoding="utf-8")

    def test_expected_correction_skips_not_found(self):
        out = JS.analyze(self.run, [("1/2", 0.5), ("1/1", 1.0)], boot=200, draws=20)
        r0, half, one = (out["rates"][k]["res"] for k in ("보정 전", "1/2", "1/1"))
        self.assertAlmostEqual(r0["rule"]["acc"], 0.8)               # 4 문항이 0.5
        self.assertAlmostEqual(half["rule"]["acc"], 0.9)             # judge X 사실의 절반이 O
        self.assertAlmostEqual(one["rule"]["acc"], 1.0)
        self.assertAlmostEqual(one["llmlingua2_r30"]["acc"], 0.5)    # NOT FOUND 0점은 그대로
        self.assertEqual(one["rule"]["keep_share"], 1.0)
        self.assertEqual(out["facts_neg"]["rule"], 4)

    def test_holm(self):
        self.assertEqual(JS.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


if __name__ == "__main__":
    unittest.main()
