"""
setup 항목(fact_meta tags "setup") 집계 분리: 주 정확도에서 빼고 setup_accuracy 로 따로 (가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_mt_setup_facts
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from multiturn import replay as rp  # noqa: E402
from multiturn.fact_tags import setup_indices, split_grade  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_replay import PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, make_cfg  # noqa: E402

NEW_ROW_KEYS = ("answer_accuracy_all", "satisfied_facts_all", "total_facts_all", "fact_satisfied",
                "setup_fact_indices", "setup_accuracy", "setup_satisfied", "setup_total")


def grade(flags):
    sat = sum(1 for f in flags if f is True)
    acc = None if any(f is None for f in flags) else sat / len(flags)
    return SimpleNamespace(answer_accuracy=acc, satisfied_count=sat, total_count=len(flags),
                           fact_results=[SimpleNamespace(fact=f"f{i}", satisfied=f) for i, f in enumerate(flags)])


def per_fact_grade(question, reference, key_facts, candidate, judge_llm, mode="per_fact"):
    """f1: 답에 ALPHA42 가 있으면 충족. f2(설정 확인용): 언제나 충족. 채점은 key_fact 전부 한다."""
    calls.append(list(key_facts))
    main = "ALPHA42" in candidate and not candidate.startswith("NOT FOUND")
    flags = [main, True][:len(key_facts)]
    g = grade(flags)
    return SimpleNamespace(**vars(g), judge_mode=mode, judge_skipped=None, judge_failed=[],
                           judge_prompt_tokens=100, judge_completion_tokens=10, judge_usage_source="api")


calls: list = []


def with_meta(scenario, tags_by_turn: dict, sid: str):
    s = json.loads(json.dumps(scenario))
    s["scenario_id"] = sid
    for t in s["turns"]:
        tags = tags_by_turn.get(t["turn"], [[], []])
        t["fact_meta"] = [{"source": "doc", "accept_alternatives": [], "tags": tg} for tg in tags]
    return s


class SplitGradeTest(unittest.TestCase):
    def test_no_setup_keeps_values(self):
        turn = {"key_facts": ["a", "b"]}
        out = split_grade(turn, grade([True, False]))
        self.assertEqual((out["answer_accuracy"], out["satisfied_facts"], out["total_facts"]), (0.5, 1, 2))
        self.assertEqual((out["setup_accuracy"], out["setup_total"]), (None, 0))
        self.assertEqual(out["answer_accuracy_all"], 0.5)

    def test_setup_split(self):
        turn = {"fact_meta": [{"tags": ["setup"]}, {"tags": ["negation"]}, {"tags": []}]}
        self.assertEqual(setup_indices(turn), {0})
        out = split_grade(turn, grade([True, False, True]))
        self.assertEqual((out["answer_accuracy"], out["satisfied_facts"], out["total_facts"]), (0.5, 1, 2))
        self.assertEqual((out["setup_accuracy"], out["setup_satisfied"], out["setup_total"]), (1.0, 1, 1))
        self.assertAlmostEqual(out["answer_accuracy_all"], 2 / 3)
        self.assertEqual(out["fact_satisfied"], [True, False, True])        # 채점 결과는 그대로 남긴다

    def test_all_setup_turn_has_no_main_accuracy(self):
        turn = {"fact_meta": [{"tags": ["setup"]}, {"tags": ["setup"]}]}
        out = split_grade(turn, grade([True, True]))
        self.assertIsNone(out["answer_accuracy"])
        self.assertEqual((out["total_facts"], out["setup_accuracy"]), (0, 1.0))

    def test_judge_failure_only_on_setup(self):
        turn = {"fact_meta": [{"tags": ["setup"]}, {"tags": []}]}
        out = split_grade(turn, grade([None, True]))
        self.assertEqual(out["answer_accuracy"], 1.0)
        self.assertIsNone(out["setup_accuracy"])

    def test_v1_scenarios_have_no_setup(self):
        from multiturn.scenario import load_scenarios
        scens = load_scenarios(ROOT / "data" / "evalsets" / "multiturn-v1")
        self.assertTrue(scens)
        for s in scens:
            for t in s["turns"]:
                self.assertEqual(setup_indices(t), set(), (s["scenario_id"], t["turn"]))


class ReplaySetupTest(unittest.TestCase):
    def setUp(self):
        for p in PATCHES:
            p.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.caches = []
        calls.clear()

    def tearDown(self):
        for p in reversed(PATCHES):
            p.stop()
        for c in self.caches:
            c.close()
        self.tmp.cleanup()

    def _run(self, scenario, run):
        cfg = make_cfg(compressors=["none", "window(1)"])
        answer = CachedLLM(rp.configure_answer_llm(FakeLLM(), cfg), path=self.root / f"{run}.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / f"{run}.sqlite", enabled=True)
        self.caches += [answer, judge]
        summary = rp.Replay(cfg, [scenario], FakeCorpus(), answer, judge, self.root / run,
                            reference_root=self.root / f"refs_{run}", grade_fn=per_fact_grade,
                            sleep=lambda s: None).run()
        rows = [json.loads(l) for l in (self.root / run / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        return summary, rows

    @staticmethod
    def _comparable(summary):
        s = json.loads(json.dumps(summary))
        for k in ("config", "trajectory", "budget", "tokenizer_check", "failed_trials_this_run"):
            s.pop(k, None)
        return s

    def test_v1_results_unchanged(self):
        """setup 태그가 없으면 (fact_meta 가 없거나 다른 태그뿐이어도) 주 정확도와 summary 가 원래 채점 그대로다."""
        plain, rows = self._run(SCENARIO, "plain")
        tagged, _ = self._run(with_meta(SCENARIO, {2: [["negation"], ["confusable"]]}, "s1"), "tagged")
        self.assertEqual(self._comparable(plain), self._comparable(tagged))
        self.assertNotIn("setup_accuracy", plain)
        self.assertFalse(any("setup" in n for n in plain["notes"]))
        for r in rows:
            self.assertEqual(r["answer_accuracy"], r["answer_accuracy_all"])
            self.assertEqual((r["setup_total"], r["setup_accuracy"]), (0, None))
        # 새 행 필드를 지운 예전 형식 행으로 집계해도 summary 가 같다
        old_rows = [{k: v for k, v in r.items() if k not in NEW_ROW_KEYS} for r in rows]
        cfg = make_cfg(compressors=["none", "window(1)"])
        self.assertEqual(json.loads(json.dumps(rp.summarize_replay(old_rows, cfg, n_scenarios=1))),
                         json.loads(json.dumps(rp.summarize_replay(rows, cfg, n_scenarios=1))))

    def test_setup_excluded_from_main_and_reported(self):
        # 턴 2 (recall): f2 가 setup. window(1) 은 기록에서 a.md 가 빠져 f1 을 놓치고 f2(setup) 만 맞힌다
        scen = with_meta(SCENARIO, {2: [[], ["setup"]]}, "s1")
        summary, rows = self._run(scen, "setup")
        self.assertTrue(all(len(c) == 2 for c in calls))                  # 채점은 setup 항목도 한다
        w2 = [r for r in rows if r["compressor"] == "window(1)" and r["turn"] == 2]
        n2 = [r for r in rows if r["compressor"] == "none" and r["turn"] == 2]
        for r in w2:
            self.assertEqual((r["answer_accuracy"], r["answer_accuracy_all"], r["setup_accuracy"]), (0.0, 0.5, 1.0))
            self.assertEqual((r["total_facts"], r["total_facts_all"], r["setup_total"]), (1, 2, 1))
            self.assertEqual(r["fact_satisfied"], [False, True])
        self.assertTrue(all(r["answer_accuracy"] == 1.0 for r in n2))
        # 주 집계: setup 을 빼면 턴 2 는 0 점 (포함했다면 0.5)
        self.assertEqual(summary["compressors"]["window(1)"]["by_turn"]["2"]["accuracy"]["compressed"], 0.0)
        sa = summary["setup_accuracy"]
        self.assertEqual(set(sa), {"none", "window(1)"})
        self.assertEqual((sa["window(1)"]["trials"], sa["window(1)"]["facts"], sa["window(1)"]["accuracy"]), (2, 2, 1.0))
        self.assertEqual(sa["window(1)"]["by_turn_type"], {"recall": 1.0})
        self.assertTrue(any("setup" in n for n in summary["notes"]))
        # 기준 궤적 채점도 주 정확도 기준 (depends_on_reference_ok)
        ref = json.loads((self.root / "setup" / "reference_grades.json").read_text(encoding="utf-8"))
        self.assertEqual(ref["s1"]["2"]["answer_accuracy"], 1.0)
        self.assertEqual(ref["s1"]["2"]["setup_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
