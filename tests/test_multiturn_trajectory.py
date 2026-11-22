"""
multiturn/trajectory.py: JSONL 저장·로드, 기록 재구성(추론 제외), 실행 요약 (네트워크 없음).

    python -m unittest tests.test_multiturn_trajectory
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm import LLMResult  # noqa: E402
from multiturn.trajectory import (  # noqa: E402
    TrajectoryStep, append_step, history_before_turn, load_steps, prompt_hash,
    reasoning_effort_for_llm, sampling_record, summarize_steps,
)

SYSTEM = "You are helpful."


def _res(text, reasoning=None, rt=None, finish="stop"):
    return LLMResult(text=text, prompt_tokens=100, completion_tokens=20, latency=0.5, model="gpt-6.1-sol",
                     reasoning_tokens=rt, reasoning_text=reasoning, finish_reason=finish,
                     cached_tokens=0, raw_usage={"prompt_tokens": 100})


def _step(turn, user, res, step_in_turn=0, cache_hit=False, cost=None, **kw):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    kw.setdefault("mode", "free_run")
    return TrajectoryStep.from_result(
        res, cache_hit=cache_hit, cost=cost, run_id="r1", scenario_id="s1", sample_idx=0,
        compressor="none", turn=turn, step_in_turn=step_in_turn,
        user_input=user, messages_sent=msgs, **kw)


class TrajectoryTest(unittest.TestCase):
    def test_roundtrip_and_hash(self):
        s = _step(0, "q0", _res("a0", reasoning="secret thoughts", rt=5))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "trajectory.jsonl"
            append_step(p, s)
            append_step(p, _step(1, "q1", _res("a1")))
            loaded = load_steps(p)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0], s)
            self.assertEqual(len(load_steps(p, turn=1)), 1)
        self.assertEqual(s.prompt_hash, prompt_hash(s.messages_sent))
        self.assertEqual(s.response_reasoning, "secret thoughts")
        self.assertEqual(s.reasoning_tokens, 5)

    def test_bad_mode(self):
        with self.assertRaises(ValueError):
            _step(0, "q", _res("a"), mode="other")

    def test_history_excludes_reasoning(self):
        steps = [
            _step(1, "q1", _res("a1")),
            _step(0, "q0", _res("draft", reasoning="R0")),
            _step(0, "q0", _res("a0 final", reasoning="R0b"), step_in_turn=1),
            _step(2, "q2", _res("a2")),
        ]
        h = history_before_turn(steps, 2)
        self.assertEqual(h, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "q0"}, {"role": "assistant", "content": "a0 final"},
            {"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
        ])
        self.assertNotIn("R0", str(h))
        self.assertEqual(history_before_turn(steps, 0), [{"role": "system", "content": SYSTEM}])

    def test_history_rejects_mixed_samples(self):
        a = _step(0, "q", _res("a"))
        b = _step(0, "q", _res("a"))
        b.sample_idx = 1
        with self.assertRaises(ValueError):
            history_before_turn([a, b], 1)

    def test_summary(self):
        steps = [
            _step(0, "q", _res("a", rt=10), cost={"usd": 0.01, "cost_source": "api"}),
            _step(1, "q", _res("", rt=500, finish="length"), cost={"usd": 0.02, "cost_source": "api"}),
            _step(2, "q", _res("b", rt=0), cache_hit=True, cost={"usd": 0.03, "cost_source": "no_cache_info"}),
            _step(3, "q", _res("c", rt=None)),
        ]
        s = summarize_steps(steps)
        self.assertEqual((s["reasoning_ran"], s["reasoning_zero"], s["reasoning_unknown"]), (2, 1, 1))
        self.assertEqual(s["finish_length"], 1)
        self.assertEqual(s["empty_response"], 1)
        self.assertEqual(s["empty_response_rate"], 0.25)
        self.assertEqual(s["cache_hits"], 1)
        self.assertAlmostEqual(s["cost_usd_experimental"], 0.06)
        self.assertAlmostEqual(s["cost_usd_actual"], 0.03)


class _FakeLLM:
    def __init__(self, effort):
        self.effort = effort

    def sampling_info(self):
        return {"reasoning_effort": self.effort or None, "temperature": None, "temperature_requested": 0.0,
                "seed": 42, "max_tokens": 4096, "max_tokens_param": "max_completion_tokens"}


class ReasoningSettingTest(unittest.TestCase):
    def test_explicit_choices(self):
        self.assertEqual(reasoning_effort_for_llm("server_default"), "")
        self.assertEqual(reasoning_effort_for_llm("low"), "low")
        for bad in ("", None, "default"):
            with self.assertRaises(ValueError):
                reasoning_effort_for_llm(bad)

    def test_sampling_record(self):
        rec = sampling_record(_FakeLLM(""), _res("a", rt=33), "server_default")
        self.assertEqual(rec["reasoning_effort_requested"], "server_default")
        self.assertIsNone(rec["reasoning_effort_sent"])
        self.assertEqual(rec["reasoning_tokens"], 33)
        self.assertIsNone(rec["temperature_sent"])


if __name__ == "__main__":
    unittest.main()
