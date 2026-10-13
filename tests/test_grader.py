"""
grader.grade_answer_accuracy 의 key_facts judge 응답 검증·재요청·폴백 테스트.

LLM 은 mock 으로 대체한다 (네트워크 호출 없음).

    python -m unittest discover -s tests
    python -m pytest tests          (pytest 가 있으면)
"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grader import (  # noqa: E402
    FACT_JUDGE_PROMPT_HASH,
    FACT_JUDGE_PROMPT_VERSION,
    _build_output_example,
    _parse_fact_judgement,
    grade_answer_accuracy,
)

FACTS = [f"fact number {i}" for i in range(5)]


@dataclass
class FakeResult:
    text: str
    prompt_tokens: int = 10
    completion_tokens: int = 5


class FakeJudge:
    """
    batch/재요청 응답은 replies 를 순서대로 돌려준다.
    fact 별 개별 판정(YES/NO 프롬프트)은 per_fact(fact) 로 답한다.
    """

    def __init__(self, replies=(), per_fact=lambda fact: "YES"):
        self.replies = list(replies)
        self.per_fact = per_fact
        self.batch_prompts: list[str] = []
        self.chat_calls: list[list[dict]] = []
        self.single_facts: list[str] = []

    def ask(self, prompt: str) -> FakeResult:
        if prompt.rstrip().endswith("Reply with exactly one word: YES or NO."):
            fact = prompt.split("Fact:\n", 1)[1].split("\n", 1)[0]
            self.single_facts.append(fact)
            return FakeResult(self.per_fact(fact))
        self.batch_prompts.append(prompt)
        return FakeResult(self.replies.pop(0))

    def chat(self, messages: list[dict]) -> FakeResult:
        self.chat_calls.append(messages)
        return FakeResult(self.replies.pop(0))


def reply(pairs) -> str:
    """[(index, satisfied), ...] -> judge JSON 응답 문자열."""
    return json.dumps({"results": [{"index": i, "satisfied": s} for i, s in pairs]})


def grade(judge, facts=FACTS, mode="batch"):
    return grade_answer_accuracy(
        question="Q?",
        reference_answer="A.",
        key_facts=facts,
        candidate_answer="candidate",
        judge_llm=judge,
        mode=mode,
    )


class PromptTest(unittest.TestCase):

    def test_prompt_numbers_facts_and_example_covers_all_indices(self):
        judge = FakeJudge([reply((i, True) for i in range(5))])
        grade(judge)
        prompt = judge.batch_prompts[0]

        for i, fact in enumerate(FACTS):
            self.assertIn(f"[{i}] {fact}", prompt)
            self.assertIn(f'{{"index": {i}, "satisfied": <true|false>}}', prompt)
        self.assertNotIn('"index": 5', prompt)
        self.assertIn("Return exactly 5 results, one per index", prompt)

    def test_example_is_dynamic(self):
        self.assertEqual(_build_output_example(1).count('"index"'), 1)
        self.assertEqual(_build_output_example(8).count('"index"'), 8)

    def test_version_and_hash_recorded(self):
        g = grade(FakeJudge([reply((i, True) for i in range(5))]))
        self.assertEqual(g.judge_prompt_version, "fact_judge_v2")
        self.assertEqual(g.judge_prompt_version, FACT_JUDGE_PROMPT_VERSION)
        self.assertEqual(g.judge_prompt_hash, FACT_JUDGE_PROMPT_HASH)
        self.assertEqual(len(g.judge_prompt_hash), 12)


class BatchTest(unittest.TestCase):

    def test_five_facts_five_results_pass_through(self):
        judge = FakeJudge([reply([(0, True), (1, False), (2, True), (3, True), (4, False)])])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "batch")
        self.assertEqual(g.judge_retries, 0)
        self.assertEqual(g.judge_missing_before_fix, [])
        self.assertEqual(g.judge_calls, 1)
        self.assertEqual([r.satisfied for r in g.fact_results], [True, False, True, True, False])
        self.assertEqual((g.satisfied_count, g.total_count), (3, 5))
        self.assertAlmostEqual(g.answer_accuracy, 0.6)
        self.assertEqual(judge.chat_calls, [])
        self.assertEqual(judge.single_facts, [])

    def test_code_fenced_json_is_accepted(self):
        raw = "```json\n" + reply((i, True) for i in range(5)) + "\n```"
        g = grade(FakeJudge([raw]))
        self.assertEqual(g.judge_mode, "batch")
        self.assertEqual(g.satisfied_count, 5)

    def test_two_of_five_then_retry_succeeds(self):
        judge = FakeJudge([
            reply([(0, True), (1, True)]),
            reply([(0, True), (1, True), (2, False), (3, True), (4, True)]),
        ])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "retry")
        self.assertEqual(g.judge_retries, 1)
        self.assertEqual(g.judge_missing_before_fix, [2, 3, 4])
        self.assertEqual(g.judge_calls, 2)
        self.assertEqual([r.satisfied for r in g.fact_results], [True, True, False, True, True])
        self.assertAlmostEqual(g.answer_accuracy, 0.8)
        self.assertEqual(judge.single_facts, [])

        # 재요청은 첫 대화를 이어서 보내고, 누락 index 를 명시한다
        retry_msgs = judge.chat_calls[0]
        self.assertEqual([m["role"] for m in retry_msgs], ["user", "assistant", "user"])
        self.assertIn("missing index [2, 3, 4]", retry_msgs[-1]["content"])
        self.assertIn("Return exactly 5 results", retry_msgs[-1]["content"])

    def test_retry_with_only_missing_indices_is_merged(self):
        judge = FakeJudge([
            reply([(0, True), (1, False)]),
            reply([(2, True), (3, False), (4, True)]),
        ])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "retry")
        self.assertEqual([r.satisfied for r in g.fact_results], [True, False, True, False, True])

    def test_retry_fails_then_per_fact_fallback_fills_all(self):
        verdicts = {f"fact number {i}": v for i, v in enumerate(["YES", "NO", "YES", "yes.", "No"])}
        judge = FakeJudge(
            [reply([(0, True), (1, True)]), reply([(0, True), (1, True), (2, True)])],
            per_fact=lambda fact: verdicts[fact],
        )
        g = grade(judge)

        self.assertEqual(g.judge_mode, "per_fact_fallback")
        self.assertEqual(g.judge_retries, 1)
        self.assertEqual(g.judge_missing_before_fix, [2, 3, 4])
        self.assertEqual(g.judge_calls, 2 + 5)
        self.assertEqual(judge.single_facts, FACTS)
        self.assertEqual(len(g.fact_results), 5)
        self.assertEqual([r.satisfied for r in g.fact_results], [True, False, True, True, False])
        self.assertAlmostEqual(g.answer_accuracy, 0.6)
        # 토큰은 모든 호출의 합
        self.assertEqual(g.judge_prompt_tokens, 10 * 7)
        self.assertEqual(g.judge_completion_tokens, 5 * 7)

    def test_invalid_json_then_invalid_again_falls_back(self):
        judge = FakeJudge(["not json at all", "still not json"])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "per_fact_fallback")
        self.assertEqual(g.judge_missing_before_fix, [0, 1, 2, 3, 4])
        self.assertEqual(g.satisfied_count, 5)

    def test_duplicate_index_triggers_retry(self):
        judge = FakeJudge([
            reply([(0, True), (1, True), (1, False), (2, True), (3, True), (4, True)]),
            reply([(0, True), (1, False), (2, True), (3, True), (4, True)]),
        ])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "retry")
        self.assertEqual(g.judge_missing_before_fix, [1])
        self.assertIn("duplicated index [1]", judge.chat_calls[0][-1]["content"])
        self.assertEqual([r.satisfied for r in g.fact_results], [True, False, True, True, True])

    def test_out_of_range_index_triggers_retry(self):
        judge = FakeJudge([
            reply([(0, True), (1, True), (2, True), (3, True), (5, True)]),
            reply([(0, True), (1, True), (2, True), (3, True), (4, False)]),
        ])
        g = grade(judge)

        self.assertEqual(g.judge_mode, "retry")
        self.assertEqual(g.judge_missing_before_fix, [4])
        self.assertIn("out-of-range index [5]", judge.chat_calls[0][-1]["content"])
        self.assertEqual(g.satisfied_count, 4)

    def test_out_of_range_in_all_five_is_still_retried(self):
        # 5개 다 있지만 범위 밖 index 가 섞여 있으면 첫 응답을 그대로 믿지 않는다
        judge = FakeJudge([
            reply([(0, True), (1, True), (2, True), (3, True), (4, True), (-1, False)]),
            reply((i, True) for i in range(5)),
        ])
        g = grade(judge)
        self.assertEqual(g.judge_mode, "retry")
        self.assertEqual(g.judge_missing_before_fix, [])

    def test_retry_with_duplicates_falls_back(self):
        judge = FakeJudge([
            reply([(0, True), (1, True)]),
            reply([(0, True), (1, True), (2, True), (2, False), (3, True), (4, True)]),
        ], per_fact=lambda fact: "NO")
        g = grade(judge)

        self.assertEqual(g.judge_mode, "per_fact_fallback")
        self.assertEqual(g.satisfied_count, 0)


class PerFactModeTest(unittest.TestCase):

    def test_per_fact_mode_calls_once_per_fact(self):
        judge = FakeJudge(per_fact=lambda fact: "NO" if fact.endswith("2") else "YES")
        g = grade(judge, mode="per_fact")

        self.assertEqual(g.judge_mode, "per_fact")
        self.assertEqual(g.judge_retries, 0)
        self.assertEqual(g.judge_calls, 5)
        self.assertEqual(judge.batch_prompts, [])
        self.assertEqual(judge.single_facts, FACTS)
        self.assertEqual([r.satisfied for r in g.fact_results], [True, True, False, True, True])

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            grade(FakeJudge(), mode="bogus")


class NotFoundTest(unittest.TestCase):

    def grade_answer(self, answer, mode):
        judge = FakeJudge(replies=[reply([(i, True) for i in range(len(FACTS))])])
        g = grade_answer_accuracy(question="Q?", reference_answer="A.", key_facts=FACTS,
                                  candidate_answer=answer, judge_llm=judge, mode=mode)
        return g, judge

    def test_not_found_skips_judge_in_both_modes(self):
        for answer in ("NOT FOUND", "not found", "  Not Found.  ", "NOT FOUND.", ".not  found\n"):
            for mode in ("batch", "per_fact"):
                with self.subTest(answer=answer, mode=mode):
                    g, judge = self.grade_answer(answer, mode)
                    self.assertEqual(judge.batch_prompts, [])
                    self.assertEqual(judge.single_facts, [])
                    self.assertEqual(judge.chat_calls, [])
                    self.assertEqual(g.judge_calls, 0)
                    self.assertEqual(g.judge_skipped, "not_found")
                    self.assertEqual(g.judge_mode, "skipped")
                    self.assertEqual(g.answer_accuracy, 0.0)
                    self.assertEqual((g.satisfied_count, g.total_count), (0, len(FACTS)))
                    self.assertEqual([r.fact for r in g.fact_results], FACTS)
                    self.assertTrue(all(not r.satisfied for r in g.fact_results))

    def test_not_found_without_judge_llm_is_fine(self):
        g = grade_answer_accuracy(question="Q?", reference_answer="A.", key_facts=FACTS,
                                  candidate_answer="NOT FOUND", judge_llm=None)
        self.assertEqual(g.judge_skipped, "not_found")

    def test_answer_that_only_mentions_not_found_is_judged(self):
        for answer in ("NOT FOUND in the first page, but the value is 5", "The value is not found"):
            with self.subTest(answer=answer):
                g, judge = self.grade_answer(answer, "batch")
                self.assertEqual(len(judge.batch_prompts), 1)
                self.assertIsNone(g.judge_skipped)
                self.assertEqual(g.answer_accuracy, 1.0)


class ParseTest(unittest.TestCase):

    def test_parse_reports_problems(self):
        raw = json.dumps({"results": [
            {"index": 0, "satisfied": True},
            {"index": 0, "satisfied": True},
            {"index": 7, "satisfied": False},
            {"index": "2", "satisfied": True},
            {"index": True, "satisfied": True},
            {"index": 3, "satisfied": "yes"},
            "junk",
        ]})
        p = _parse_fact_judgement(raw, 4)

        self.assertFalse(p.ok)
        self.assertEqual(p.values, {})
        self.assertEqual(p.duplicates, [0])
        self.assertEqual(p.missing, [1, 2, 3])
        self.assertEqual(p.out_of_range, [7])
        self.assertEqual(p.invalid, 4)

    def test_parse_complete(self):
        p = _parse_fact_judgement(reply([(1, False), (0, True)]), 2)
        self.assertTrue(p.ok)
        self.assertEqual(p.values, {0: True, 1: False})


if __name__ == "__main__":
    unittest.main()
