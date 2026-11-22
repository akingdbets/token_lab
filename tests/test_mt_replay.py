"""
multiturn/replay.py: 가짜 LLM·가짜 grader 로 끝까지 실행, 이어 돌리기, sample_idx 별 캐시 분리,
기준 궤적 오답 표시(depends_on_reference_ok), 필수 인자, 백오프, 비열등 판정 계산, 오프라인 추정.
네트워크 없음. 토큰 수는 글자 수 기반 가짜 함수로 바꾼다.

    python -m unittest tests.test_mt_replay
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm import LLMResult  # noqa: E402
from multiturn import estimate as est_mod  # noqa: E402
from multiturn import replay as rp  # noqa: E402
from multiturn.mt_stats import bootstrap_diff, non_inferiority, pair_rows  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402


def fake_count_tokens(text):
    return max(1, len(text) // 4)


def fake_count_message_tokens(messages, add_generation_prompt=True):
    return sum(fake_count_tokens(m["content"]) + 4 for m in messages) + (3 if add_generation_prompt else 0)


PATCHES = [mock.patch.object(rp, "count_tokens", fake_count_tokens),
           mock.patch.object(rp, "count_message_tokens", fake_count_message_tokens),
           mock.patch.object(est_mod, "count_tokens", fake_count_tokens),
           mock.patch.object(est_mod, "count_message_tokens", fake_count_message_tokens)]


class FakeCorpus:
    PAGES = {"a.md": "# A\n\nAlpha value is 42.\n" + "filler line\n" * 400,
             "b.md": "# B\n\nBeta value is 7.\n" + "filler line\n" * 400}

    def get(self, doc_id):
        return SimpleNamespace(text=self.PAGES[doc_id])

    def page_ref(self, doc_id):
        return doc_id

    def expanded_text(self, doc_id):
        return self.PAGES[doc_id]


def _t(i, tt, deps, pages, q):
    return {"turn": i, "turn_type": tt, "type": "fact", "question": q, "answer": "x", "key_facts": ["f1", "f2"],
            "key_entities": ["Alpha"], "evidence_pages": pages, "depends_on": deps,
            "evidence": [{"quote": "Alpha", "page": "a.md", "fact_idx": 0}, {"quote": "Alpha", "page": "a.md", "fact_idx": 1}]}


SCENARIO = {"scenario_id": "s1", "title": "t", "topic": "t", "status": "draft", "turns": [
    _t(0, "new", [], ["a.md"], "What is alpha?"),
    _t(1, "new", [], ["b.md"], "What is beta?"),
    _t(2, "recall", [0], [], "Recall alpha?"),
    _t(3, "recall", [1], [], "Recall beta?"),
    _t(4, "synthesis", [0, 1], [], "Sum?"),
    _t(5, "synthesis", [2, 3], [], "Sum again?"),
]}
# 질문 글자까지 같으면 요청이 같아 응답 캐시를 공유하므로, 두 번째 시나리오는 질문을 바꾼다
SCENARIO2 = json.loads(json.dumps(SCENARIO).replace('"s1"', '"s2"').replace('?"', '? (2)"'))


class FakeLLM:
    """답변: 기록에 'Alpha value is 42' 가 있으면 정답 토큰을 넣는다. sample_idx 는 캐시 키에만 쓰인다."""

    def __init__(self, fail_on: set | None = None):
        self.model, self.backend, self.base_url = "gpt-6-luna", "openai", "https://api.openai.com"
        self.temperature, self.reasoning_effort, self.max_tokens = 0.0, "none", None
        self.unsupported: set[str] = set()
        self.calls = []
        self.fail_on = fail_on or set()

    def sampling_info(self):
        return {"model": self.model, "temperature": None if "temperature" in self.unsupported else self.temperature,
                "temperature_requested": self.temperature, "seed": 42,
                "reasoning_effort": self.reasoning_effort or None,
                "reasoning_effort_requested": self.reasoning_effort or None,
                "max_tokens": self.max_tokens, "max_tokens_param": "max_tokens"}

    def chat(self, messages, stream_ttft=False):
        q = messages[-1]["content"]
        if any(f in q for f in self.fail_on):
            raise RuntimeError("simulated failure")
        self.calls.append(messages)
        knows_alpha = any("Alpha value is 42" in m["content"] for m in messages)
        text = f"ALPHA42 n={len(self.calls)}" if knows_alpha else "NOT FOUND"   # grader 는 NOT FOUND 만 있는 답을 본다
        return LLMResult(text=text, prompt_tokens=fake_count_message_tokens(messages), completion_tokens=50,
                         latency=0.01, model=self.model, cached_tokens=0, cache_write_tokens=0,
                         reasoning_tokens=30, finish_reason="stop")


class FakeJudge(FakeLLM):
    def __init__(self):
        super().__init__()
        self.model = "deepseek-flash"


def fake_grade(question, reference, key_facts, candidate, judge_llm, mode="per_fact"):
    acc = 1.0 if "ALPHA42" in candidate else 0.0
    if candidate.startswith("NOT FOUND"):
        acc = 0.0
    return SimpleNamespace(answer_accuracy=acc, satisfied_count=int(acc * 2), total_count=2, judge_mode=mode,
                           judge_skipped=None, judge_failed=[], judge_prompt_tokens=100, judge_completion_tokens=10,
                           judge_usage_source="api")


def make_cfg(**kw):
    base = dict(model="gpt-6-luna", reasoning_effort="server_default", max_completion_tokens=2048,
                compressors=["none", "window(1)"], samples=2, reference_sample=0, concurrency=3, boot=200)
    base.update(kw)
    return rp.ReplayConfig(**base)


class ReplayTest(unittest.TestCase):
    def setUp(self):
        for p in PATCHES:
            p.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.caches = []

    def tearDown(self):
        for p in reversed(PATCHES):
            p.stop()
        for c in self.caches:
            c.close()
        self.tmp.cleanup()

    def _replay(self, llm, cfg=None, scenarios=(SCENARIO,), run="mt_test"):
        cfg = cfg or make_cfg()
        answer = CachedLLM(rp.configure_answer_llm(llm, cfg), path=self.root / "cache.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / "cache.sqlite", enabled=True)
        self.caches += [answer, judge]
        return rp.Replay(cfg, list(scenarios), FakeCorpus(), answer, judge, self.root / run,
                         reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None)

    def test_end_to_end_summary(self):
        llm = FakeLLM()
        summary = self._replay(llm, scenarios=(SCENARIO, SCENARIO2)).run()
        out = self.root / "mt_test"
        rows = [json.loads(l) for l in (out / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2 * 6 * 2 * 2)
        self.assertTrue((out / "summary.json").exists())
        self.assertTrue((out / "trajectory.jsonl").exists())
        # temperature 는 처음부터 보내지 않고, 출력 한도와 추론 설정은 명시값
        self.assertIn("temperature", llm.unsupported)
        self.assertEqual((llm.max_tokens, llm.reasoning_effort), (2048, ""))
        self.assertEqual(summary["config"]["replay"]["reasoning_effort"], "server_default")
        self.assertEqual(summary["config"]["replay"]["max_completion_tokens"], 2048)
        # none 의 reference sample 은 기준 궤적과 같은 요청 -> 응답 캐시 적중
        none_ref = [r for r in rows if r["compressor"] == "none" and r["sample_idx"] == 0]
        self.assertTrue(all(r["cache_hit"] for r in none_ref))
        # window(1) 은 턴 0, 1 에서 기록이 none 과 같아(잘릴 것이 없음) 같은 요청 -> 적중. 턴 2 부터는 요청이 달라 적중 없음
        self.assertFalse(any(r["cache_hit"] for r in rows if r["compressor"] == "window(1)" and r["turn"] >= 2))
        # window(1): 턴 2 (recall, 턴 0 의존) 는 기록에서 a.md 가 사라져 NOT FOUND
        w2 = [r for r in rows if r["compressor"] == "window(1)" and r["turn"] == 2]
        self.assertTrue(all(r["not_found"] and r["answer_accuracy"] == 0.0 for r in w2))
        self.assertTrue(all(r["entity_retention"] == 0.0 for r in w2))
        n2 = [r for r in rows if r["compressor"] == "none" and r["turn"] == 2]
        self.assertTrue(all(r["answer_accuracy"] == 1.0 for r in n2))
        block = summary["compressors"]["window(1)"]
        for key in ("all", "depends_on_reference_ok", "all_by_turn_type", "by_turn"):
            self.assertIn(key, block)
        self.assertIn("recall", block["all_by_turn_type"])
        self.assertGreater(block["all"]["input_reduction_pct"], 0)
        self.assertIn("paired_bootstrap_turn", block["all"])
        self.assertEqual(block["all"]["cluster_bootstrap_scenario"]["n_units"], 2)
        self.assertIn("non_inferior", block["all"]["non_inferiority"])
        self.assertIn("recall", summary["not_found_rate_by_turn_type"]["window(1)"])
        self.assertTrue(any("군집" in n for n in summary["notes"]))
        self.assertEqual(summary["noise_none_vs_none"]["all"]["n_pairs"], 12)
        self.assertEqual(summary["answer_health"]["none"]["reasoning_ran"], 24)
        # 비용 비교 기준과 예산 블록
        self.assertEqual(block["all"]["cost_basis"], "simulated_prefix_cache")
        bud = summary["budget"]
        self.assertGreater(bud["answer_usd_actual_total"], 0)
        self.assertLess(bud["replay_usd_actual_by_compressor"]["none"], block["all"]["cost_usd_measured"]["none"])
        self.assertTrue(any("0원" in n for n in bud["notes"]))
        self.assertIn("tokenizer_check", summary)

    def test_depends_on_reference_ok(self):
        # 기준 궤적의 턴 1 (b.md 만 첨부) 답변은 ALPHA42 를 포함 (기록에 a.md 가 있음) -> 정답. 턴 0 도 정답.
        # 턴 1 기준 답이 틀리도록 grader 를 바꾼다
        def grade(q, ref, facts, cand, judge, mode="per_fact"):
            g = fake_grade(q, ref, facts, cand, judge, mode)
            if q == "What is beta?":
                g.answer_accuracy = 0.5
            return g
        rep = self._replay(FakeLLM())
        rep.grade_fn = grade
        rep.run()
        rows = [json.loads(l) for l in (self.root / "mt_test" / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        ok = {r["turn"]: r["depends_on_reference_ok"] for r in rows}
        self.assertEqual(ok, {0: True, 1: True, 2: True, 3: False, 4: False, 5: False})
        grades = json.loads((self.root / "mt_test" / "reference_grades.json").read_text(encoding="utf-8"))
        self.assertEqual(grades["s1"]["1"]["answer_accuracy"], 0.5)

    def test_reference_failure_stops_run(self):
        """기준 궤적을 만들지 못하면 replay 를 시작하지 않는다 (기준이 없는 비교를 막음)."""
        with self.assertRaises(RuntimeError):
            self._replay(FakeLLM(fail_on={"Sum again?"})).run()
        self.assertFalse((self.root / "mt_test" / "turn_trials.jsonl").exists())

    def test_resume_after_trial_failures(self):
        llm = FakeLLM()
        rep = self._replay(llm)
        rep.build_references()
        llm.fail_on = {"Recall beta?"}       # 기준 궤적은 이미 있고, replay 의 턴 3 만 실패
        summary = rep.run()
        out = self.root / "mt_test"
        rows = [json.loads(l) for l in (out / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(summary["failed_trials_this_run"], 2 * 2 - 1)   # none sample0 은 캐시 적중이라 성공
        self.assertTrue((out / "errors.jsonl").exists())
        n_before, calls_before = len(rows), len(llm.calls)
        llm.fail_on = set()
        rep2 = self._replay(llm)
        rep2.run()
        rows = [json.loads(l) for l in (out / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 6 * 2 * 2)
        self.assertEqual(len(rows) - n_before, 3)
        self.assertEqual(len(llm.calls) - calls_before, 3)               # 끝난 trial 은 다시 부르지 않는다
        self.assertEqual(len({rp.Replay.trial_key(r) for r in rows}), len(rows))

    def test_sample_idx_cache_separation(self):
        llm = FakeLLM()
        self._replay(llm, cfg=make_cfg(compressors=["none"], samples=3)).run()
        # 기준 궤적 6 + none sample 1, 2 의 6턴씩 = 18 회. sample 0 은 기준 궤적 캐시 적중
        self.assertEqual(len(llm.calls), 6 + 6 * 2)
        rows = [json.loads(l) for l in (self.root / "mt_test" / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        by = {}
        for r in rows:
            by.setdefault((r["turn"], r["prompt_hash"]), set()).add(r["response"])
        self.assertTrue(all(len(v) == 3 for v in by.values()))       # 같은 요청이라도 sample 마다 다른 응답
        # 다시 돌리면 (새 run) 전부 캐시 적중
        n = len(llm.calls)
        self._replay(llm, cfg=make_cfg(compressors=["none"], samples=3), run="mt_again").run()
        self.assertEqual(len(llm.calls), n)

    def test_reference_reused(self):
        llm = FakeLLM()
        self._replay(llm).build_references()
        refs = list((self.root / "refs").rglob("*.jsonl"))
        self.assertEqual(len(refs), 1)
        n = len(llm.calls)
        self._replay(llm, run="mt_other").build_references()
        self.assertEqual(len(llm.calls), n)

    def test_reference_health_warning(self):
        class LengthLLM(FakeLLM):
            def chat(self, messages, stream_ttft=False):
                r = super().chat(messages, stream_ttft)
                r.finish_reason, r.text = "length", ""
                return r
        _, _, warnings = self._replay(LengthLLM()).build_references()
        self.assertEqual(sum("finish_reason=length" in w for w in warnings), 6)
        self.assertEqual(sum("비었습니다" in w for w in warnings), 6)


class ArgsTest(unittest.TestCase):
    BASE = ["--scenarios", "x", "--model", "m"]

    def test_required_args(self):
        ap = rp.build_parser()
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                ap.parse_args(self.BASE + ["--max-completion-tokens", "100"])
            with self.assertRaises(SystemExit):
                ap.parse_args(self.BASE + ["--reasoning-effort", "server_default"])
            with self.assertRaises(SystemExit):
                ap.parse_args(self.BASE + ["--reasoning-effort", "bogus", "--max-completion-tokens", "1"])
        a = ap.parse_args(self.BASE + ["--reasoning-effort", "server_default", "--max-completion-tokens", "100",
                                       "--compressors", "none,window(2),per_message(rule>rule)"])
        cfg = rp.config_from_args(a)
        self.assertEqual(cfg.compressors, ["none", "window(2)", "per_message(rule>rule)"])

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            make_cfg(reasoning_effort="")
        with self.assertRaises(ValueError):
            make_cfg(max_completion_tokens=0)
        with self.assertRaises(ValueError):
            make_cfg(compressors=["window(1)"])
        with self.assertRaises(ValueError):
            make_cfg(reference_sample=2)

    def test_backoff(self):
        calls = {"n": 0}
        waits = []

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise requests.HTTPError("429", response=SimpleNamespace(status_code=429))
            return "ok"
        self.assertEqual(rp.with_backoff(flaky, make_cfg(), sleep=waits.append), "ok")
        self.assertEqual(len(waits), 2)
        self.assertGreater(waits[1], waits[0])

        def bad_request():
            raise requests.HTTPError("400", response=SimpleNamespace(status_code=400))
        with self.assertRaises(requests.HTTPError):
            rp.with_backoff(bad_request, make_cfg(), sleep=waits.append)


def _row(sid, turn, comp, sample, acc):
    return {"scenario_id": sid, "turn": turn, "compressor": comp, "sample_idx": sample, "answer_accuracy": acc}


class GuardTest(unittest.TestCase):
    """조용한 대체 금지와 토크나이저 확인."""

    def test_llmlingua_family_requires_package(self):
        from multiturn.history_compressors import MissingDependencyError, get_history_compressor
        with mock.patch("multiturn.history_compressors.simple.importlib.import_module",
                        side_effect=ModuleNotFoundError("No module named 'llmlingua'")):
            for name in ("per_message(llmlingua2)", "per_message(rule>llmlingua2)",
                         "window(2)>per_message(llmlingua2_r30)", "per_message(llmlingua2_repair_v1_r50)"):
                with self.assertRaises(MissingDependencyError, msg=name):
                    get_history_compressor(name)
            get_history_compressor("per_message(rule)")          # llmlingua 가 필요 없는 압축기는 그대로

    def test_replay_stops_at_start_without_llmlingua(self):
        from multiturn.history_compressors import MissingDependencyError
        cfg = make_cfg(compressors=["none", "per_message(llmlingua2)"])
        llm = FakeLLM()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("multiturn.history_compressors.simple.importlib.import_module",
                            side_effect=ModuleNotFoundError("No module named 'llmlingua'")):
                answer = CachedLLM(llm, path=Path(d) / "c.sqlite", enabled=True)
                judge = CachedLLM(FakeJudge(), path=Path(d) / "c.sqlite", enabled=True)
                with self.assertRaises(MissingDependencyError):
                    rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, Path(d) / "mt_x",
                              reference_root=Path(d) / "refs", grade_fn=fake_grade)
                answer.close(); judge.close()
        self.assertEqual(llm.calls, [])                              # API 를 한 번도 부르지 않았다

    def test_fallback_error_is_not_silent(self):
        from compressors import REGISTRY, Compressor, CompressResult
        from multiturn.history_compressors import CompressorFallbackError, get_history_compressor

        class Falls(Compressor):
            name, targets = "falls", ("context",)

            def compress(self, parts):
                return CompressResult(system=parts.system, context=parts.context, question=parts.question,
                                      info={"status": "fallback_error", "error_type": "OSError", "error": "no model"})
        with mock.patch.dict(REGISTRY, {"falls": Falls()}):
            hc = get_history_compressor("per_message(falls)")
        hist = [{"role": "system", "content": "S"},
                {"role": "user", "content": "<documentation>\nX\n</documentation>\n\nQuestion: q"},
                {"role": "assistant", "content": "a"}]
        with self.assertRaises(CompressorFallbackError):
            hc.compress_history(hist, "CUR")

    def test_tokenizer_check(self):
        ok = rp.check_tokenizer("gpt-6-luna", allow_approx=False, tokenizer="tiktoken:o200k_base") \
            if _has_tiktoken() else None
        if ok is not None:
            self.assertTrue(ok["ok"])
        with self.assertRaises(rp.TokenizerMismatchError):
            rp.check_tokenizer("gpt-6-luna", allow_approx=False, tokenizer="Qwen/Qwen2.5-7B-Instruct")
        with self.assertRaises(rp.TokenizerMismatchError):
            rp.check_tokenizer("unknown-model", allow_approx=False, tokenizer="tiktoken:o200k_base")
        r = rp.check_tokenizer("gpt-6-luna", allow_approx=True, tokenizer="Qwen/Qwen2.5-7B-Instruct")
        self.assertTrue(r["approx"])
        self.assertEqual(r["expected"], "tiktoken:o200k_base")
        with mock.patch.dict(sys.modules, {"tiktoken": None}):       # tiktoken 이 없으면 맞는 이름이어도 멈춘다
            with self.assertRaises(rp.TokenizerMismatchError):
                rp.check_tokenizer("gpt-6-luna", allow_approx=False, tokenizer="tiktoken:o200k_base")

    def test_cli_requires_allow_flag(self):
        a = rp.build_parser().parse_args(["--scenarios", "x", "--model", "m", "--reasoning-effort", "low",
                                          "--max-completion-tokens", "10"])
        self.assertFalse(a.allow_approx_tokenizer)


def _has_tiktoken():
    try:
        import tiktoken  # noqa: F401
        return True
    except ImportError:
        return False


class StatsTest(unittest.TestCase):
    def test_pairing_and_noninferiority(self):
        rows = []
        for sid in ("a", "b", "c"):
            for t in range(4):
                for s in range(2):
                    rows.append(_row(sid, t, "none", s, 1.0))
                    rows.append(_row(sid, t, "comp", s, 0.95))
        pairs = pair_rows(rows, "comp")
        self.assertEqual(len(pairs), 24)
        r = bootstrap_diff(pairs, unit="turn", boot=200)
        self.assertEqual((r["diff"], r["diff_ci"], r["n_units"]), (-0.05, [-0.05, -0.05], 12))
        self.assertTrue(non_inferiority(r, 0.10)["non_inferior"])        # -0.05 > -0.10
        self.assertFalse(non_inferiority(r, 0.04)["non_inferior"])       # -0.05 < -0.04
        c = bootstrap_diff(pairs, unit="scenario", boot=200)
        self.assertEqual(c["n_units"], 3)

    def test_noise_pairs_against_reference_sample(self):
        rows = [_row("a", 0, "none", s, acc) for s, acc in enumerate((1.0, 0.0, 1.0))]
        pairs = pair_rows(rows, "none", base="none", base_sample=0)
        self.assertEqual([(b["sample_idx"], c["sample_idx"]) for b, c in pairs], [(0, 1), (0, 2)])

    def test_failed_grades_excluded(self):
        rows = [_row("a", 0, "none", 0, 1.0), _row("a", 0, "comp", 0, None)]
        self.assertEqual(pair_rows(rows, "comp"), [])


class EstimateTest(unittest.TestCase):
    def setUp(self):
        for p in PATCHES:
            p.start()

    def tearDown(self):
        for p in reversed(PATCHES):
            p.stop()

    def test_prefix_cache(self):
        c = est_mod.PrefixCache()
        big = {"role": "user", "content": "x" * 8000}
        self.assertEqual(c.cached_tokens([big, {"role": "user", "content": "q1"}]), 0)
        self.assertGreater(c.cached_tokens([big, {"role": "user", "content": "q2"}]), 1000)
        self.assertEqual(c.cached_tokens([{"role": "user", "content": "short"}]), 0)

    def test_estimate_matrix(self):
        cfg = make_cfg(compressors=["none", "window(1)"], samples=3)
        e = est_mod.estimate(cfg, [SCENARIO], FakeCorpus(), judge_model="deepseek-flash")
        self.assertEqual(e["reference"]["requests"], 6)
        none, win = e["compressors"]["none"], e["compressors"]["window(1)"]
        self.assertEqual((none["requests"], none["actual_requests"]), (18, 12))
        self.assertEqual(win["actual_requests"], 18)
        self.assertLess(win["input_tokens"], none["input_tokens"])
        u = none["answer_usd_actual"]
        self.assertLessEqual(u["prefix_cache"], u["no_cache"])
        self.assertEqual(none["judge_calls"], 6 * 3 * 2)                  # per_fact: key_fact 2개
        self.assertIsNotNone(e["budget_judge_usd"])
        # 압축기 비교는 실험상 비용: none 도 81 trial 전부 (reference sample 은 기준 궤적 호출 값) 로 센다
        self.assertGreater(none["answer_usd_experimental"]["no_cache"], none["answer_usd_actual"]["no_cache"])
        self.assertEqual(none["cost_reduction_pct_vs_none"]["no_cache"], 0.0)
        self.assertGreater(win["cost_reduction_pct_vs_none"]["no_cache"], 0)
        self.assertTrue(any("0원" in n for n in e["notes"]))

    def test_estimate_stops_on_missing_llmlingua(self):
        from multiturn.history_compressors import MissingDependencyError
        cfg = make_cfg(compressors=["none", "per_message(llmlingua2)"])
        with mock.patch("multiturn.history_compressors.simple.importlib.import_module",
                        side_effect=ModuleNotFoundError("No module named 'llmlingua'")):
            with self.assertRaises(MissingDependencyError):
                est_mod.estimate(cfg, [SCENARIO], FakeCorpus(), judge_model="deepseek-flash")


if __name__ == "__main__":
    unittest.main()
