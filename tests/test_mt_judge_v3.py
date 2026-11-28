"""
replay 채점 버전 연결: multiturn-v2 (schema_version 2) 는 fact_judge_v3 + accept_alternatives, v1 은 예전 그대로
(가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_mt_judge_v3
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
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_replay import PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, make_cfg  # noqa: E402

calls: list = []


def recording_grade(question, reference, key_facts, candidate, judge_llm, mode="per_fact", **kw):
    calls.append({"question": question, "key_facts": list(key_facts), "mode": mode, **kw})
    ok = "ALPHA42" in candidate and not candidate.startswith("NOT FOUND")
    flags = [ok] * len(key_facts)
    return SimpleNamespace(answer_accuracy=1.0 if ok else 0.0, satisfied_count=sum(flags), total_count=len(flags),
                           fact_results=[SimpleNamespace(fact=f, satisfied=x) for f, x in zip(key_facts, flags)],
                           judge_mode=mode, judge_skipped=None, judge_failed=[], judge_prompt_tokens=100,
                           judge_completion_tokens=10, judge_usage_source="api")


def v2_scenario(sid="v2s"):
    s = json.loads(json.dumps(SCENARIO))
    s["scenario_id"], s["schema_version"] = sid, 2
    for t in s["turns"]:
        t["fact_meta"] = [{"source": "doc", "accept_alternatives": [f"alt {t['turn']}"], "tags": []},
                          {"source": "user", "accept_alternatives": [], "tags": []}]
    return s


class JudgeVersionTest(unittest.TestCase):
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
        cfg = make_cfg(compressors=["none", "window(1)"], judge_mode="per_fact")
        answer = CachedLLM(rp.configure_answer_llm(FakeLLM(), cfg), path=self.root / "c.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / "c.sqlite", enabled=True)
        self.caches += [answer, judge]
        rep = rp.Replay(cfg, [scenario], FakeCorpus(), answer, judge, self.root / run,
                        reference_root=self.root / "refs", grade_fn=recording_grade, sleep=lambda s: None)
        summary = rep.run()
        rows = [json.loads(l) for l in (self.root / run / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        return rep, summary, rows

    def test_v1_calls_unchanged(self):
        _, summary, rows = self._run(SCENARIO, "v1")
        self.assertTrue(calls)
        for c in calls:                                    # 채점 버전·대안 인자를 넘기지 않는다 (예전 호출 그대로)
            self.assertEqual(set(c), {"question", "key_facts", "mode"})
        self.assertTrue(all(r["judge_version"] == "fact_judge_v2" for r in rows))
        self.assertEqual(summary["judge_versions"], {"fact_judge_v2": len(rows)})
        self.assertEqual(summary["config"]["judge"]["versions"], {"fact_judge_v2": 1})
        ref = json.loads((self.root / "v1" / "reference_grades.json").read_text(encoding="utf-8"))
        self.assertNotIn("judge_version", ref["s1"]["0"])              # v1 기준 채점 기록도 예전 형식
        # 채점 버전 필드를 지운 예전 행으로 집계하면 judge_versions 키만 빠지고 나머지는 같다
        cfg = make_cfg(compressors=["none", "window(1)"], judge_mode="per_fact")
        old = rp.summarize_replay([{k: v for k, v in r.items() if k != "judge_version"} for r in rows], cfg, n_scenarios=1)
        new = rp.summarize_replay(rows, cfg, n_scenarios=1)
        self.assertNotIn("judge_versions", old)
        new.pop("judge_versions")
        self.assertEqual(json.loads(json.dumps(old)), json.loads(json.dumps(new)))

    def test_v2_uses_v3_with_alternatives(self):
        _, summary, rows = self._run(v2_scenario(), "v2")
        self.assertTrue(calls)
        for c in calls:
            self.assertEqual(c["judge_version"], "fact_judge_v3")
            self.assertEqual(len(c["alternatives"]), len(c["key_facts"]))
            self.assertEqual(c["alternatives"][1], [])
            self.assertTrue(c["alternatives"][0][0].startswith("alt "))
        q_to_alt = {c["question"]: c["alternatives"][0][0] for c in calls}
        self.assertEqual(q_to_alt["What is alpha?"], "alt 0")         # 턴별 fact_meta 가 그 턴 채점에 간다
        self.assertEqual(q_to_alt["Sum again?"], "alt 5")
        self.assertTrue(all(r["judge_version"] == "fact_judge_v3" for r in rows))
        self.assertEqual(summary["judge_versions"], {"fact_judge_v3": len(rows)})
        self.assertEqual(summary["config"]["judge"]["versions"], {"fact_judge_v3": 1})
        ref = json.loads((self.root / "v2" / "reference_grades.json").read_text(encoding="utf-8"))
        self.assertEqual(ref["v2s"]["0"]["judge_version"], "fact_judge_v3")

    def test_saved_reference_grade_with_other_version_is_regraded(self):
        rep, _, _ = self._run(v2_scenario(), "v2b")
        p = self.root / "v2b" / "reference_grades.json"
        ref = json.loads(p.read_text(encoding="utf-8"))
        for g in ref["v2s"].values():
            g.pop("judge_version")                      # v2 판정으로 저장된 기록이라고 가정
        p.write_text(json.dumps(ref), encoding="utf-8")
        calls.clear()
        rep.build_references()
        self.assertEqual(len(calls), len(SCENARIO["turns"]))           # 버전이 달라 다시 채점
        calls.clear()
        rep.build_references()
        self.assertEqual(calls, [])                                     # 같은 버전이면 재사용

    def test_real_grader_accepts_v3_kwargs(self):
        """실제 grade_answer_accuracy 가 replay 가 넘기는 인자를 받는다 (judge 응답은 가짜)."""
        from grader import grade_answer_accuracy

        class YesJudge:
            model = "deepseek-flash"

            def chat(self, messages, stream_ttft=False):
                from llm import LLMResult
                self.seen = getattr(self, "seen", []) + [messages]
                return LLMResult(text="YES", prompt_tokens=10, completion_tokens=1, latency=0.0, model=self.model)

            def ask(self, prompt, system=None, stream_ttft=False):
                return self.chat([{"role": "user", "content": prompt}])

        turn = v2_scenario()["turns"][0]
        j = YesJudge()
        g = grade_answer_accuracy(turn["question"], turn["answer"], turn["key_facts"], "ALPHA42", j,
                                  mode="per_fact", **rp.judge_kwargs(v2_scenario(), turn))
        self.assertEqual(g.judge_prompt_version, "fact_judge_v3")
        self.assertEqual(g.answer_accuracy, 1.0)
        prompts = [json.dumps(m, ensure_ascii=False) for m in j.seen]
        self.assertEqual(len(prompts), 2)
        self.assertIn("alt 0", prompts[0])               # 대안이 있는 fact 는 v3 프롬프트에 대안이 들어간다
        self.assertNotIn("alt 0", prompts[1])            # 대안이 없는 fact 는 v2 와 같은 프롬프트 (grader 설계)


if __name__ == "__main__":
    unittest.main()
