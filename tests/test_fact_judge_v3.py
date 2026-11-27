"""
fact_judge_v3: accept_alternatives 를 더한 per_fact 판정.
대안이 없는 fact 는 v2 per_fact 프롬프트와 글자 그대로 같아야 한다 (네트워크 없음).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grader import (  # noqa: E402
    FACT_JUDGE_PROMPT_HASH,
    FACT_JUDGE_PROMPT_VERSION,
    FACT_JUDGE_SINGLE_PROMPT,
    FACT_JUDGE_V3_PROMPT_HASH,
    FACT_JUDGE_V3_VERSION,
    grade_answer_accuracy,
    single_fact_prompt,
)
from test_grader import FakeJudge  # noqa: E402

Q, REF, CAND = "How do I return 201 for new items?", "Return JSONResponse directly.", "Inject Response and set status_code."


class RecordingJudge(FakeJudge):
    def __init__(self, answer="YES"):
        super().__init__(per_fact=lambda fact: answer)
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        return super().ask(prompt)


class V3PromptTest(unittest.TestCase):
    def test_no_alternatives_is_identical_to_v2(self):
        v2 = FACT_JUDGE_SINGLE_PROMPT.format(question=Q, reference_answer=REF, candidate_answer=CAND, fact="F1")
        self.assertEqual(single_fact_prompt(Q, REF, "F1", CAND), v2)
        self.assertEqual(single_fact_prompt(Q, REF, "F1", CAND, []), v2)
        self.assertEqual(single_fact_prompt(Q, REF, "F1", CAND, ["  "]), v2)

    def test_v3_without_alternatives_sends_same_prompts_as_v2(self):
        facts = ["fact one", "fact two"]
        j2, j3 = RecordingJudge(), RecordingJudge()
        g2 = grade_answer_accuracy(Q, REF, facts, CAND, j2, mode="per_fact")
        g3 = grade_answer_accuracy(Q, REF, facts, CAND, j3, mode="per_fact",
                                   judge_version=FACT_JUDGE_V3_VERSION, alternatives=[[], []])
        self.assertEqual(j2.prompts, j3.prompts)
        self.assertEqual(g2.answer_accuracy, g3.answer_accuracy)
        self.assertEqual((g2.judge_prompt_version, g2.judge_prompt_hash), (FACT_JUDGE_PROMPT_VERSION, FACT_JUDGE_PROMPT_HASH))
        self.assertEqual((g3.judge_prompt_version, g3.judge_prompt_hash), (FACT_JUDGE_V3_VERSION, FACT_JUDGE_V3_PROMPT_HASH))

    def test_alternatives_inserted_after_fact_only_for_that_fact(self):
        j = RecordingJudge()
        grade_answer_accuracy(Q, REF, ["Return JSONResponse directly.", "Not validated by response model."], CAND, j,
                              mode="per_fact", judge_version=FACT_JUDGE_V3_VERSION,
                              alternatives=[["Inject a Response parameter and set response.status_code."], []])
        p0, p1 = j.prompts
        self.assertIn("Alternative answers that are also correct", p0)
        self.assertIn("- Inject a Response parameter and set response.status_code.", p0)
        self.assertLess(p0.index("Fact:\nReturn JSONResponse directly.\n"), p0.index("Alternative answers"))
        self.assertLess(p0.index("Alternative answers"), p0.index("Does the candidate answer convey"))
        self.assertEqual(p1, single_fact_prompt(Q, REF, "Not validated by response model.", CAND))

    def test_guards(self):
        j = RecordingJudge()
        with self.assertRaises(ValueError):          # v3 는 per_fact 만
            grade_answer_accuracy(Q, REF, ["f"], CAND, j, mode="batch", judge_version=FACT_JUDGE_V3_VERSION)
        with self.assertRaises(ValueError):          # v2 에 대안을 넘기면 조용히 무시하지 않는다
            grade_answer_accuracy(Q, REF, ["f"], CAND, j, mode="per_fact", alternatives=[["a"]])
        with self.assertRaises(ValueError):          # 길이 불일치
            grade_answer_accuracy(Q, REF, ["f", "g"], CAND, j, mode="per_fact",
                                  judge_version=FACT_JUDGE_V3_VERSION, alternatives=[["a"]])
        with self.assertRaises(ValueError):
            grade_answer_accuracy(Q, REF, ["f"], CAND, j, mode="per_fact", judge_version="fact_judge_v9")


if __name__ == "__main__":
    unittest.main()
