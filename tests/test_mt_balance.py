"""
API 잔액 부족 처리: OpenAI 429 insufficient_quota, DeepSeek 402 는 재시도하지 않고 실행을 멈춘다. 실패한 시행은 행을 쓰지 않고
--resume 으로 이어서 끝낸다 (가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_mt_balance
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import llm as llm_mod  # noqa: E402
from llm import LLM, InsufficientBalanceError, balance_error_of  # noqa: E402
from multiturn import replay as rp  # noqa: E402
from multiturn.history_compressors import Summarizer  # noqa: E402
from multiturn.response_cache import CachedLLM, cache_key  # noqa: E402
from test_mt_replay import PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, fake_grade, make_cfg  # noqa: E402
from test_mt_summary_budget import FakeSummaryLLM  # noqa: E402

OPENAI_QUOTA = ('{"error": {"message": "You exceeded your current quota, please check your plan and billing details.", '
                '"type": "insufficient_quota", "code": "insufficient_quota"}}')
DEEPSEEK_402 = '{"error": {"message": "Insufficient Balance", "type": "unknown_error"}}'


def quota_error(provider="OpenAI"):
    if provider == "DeepSeek":
        return InsufficientBalanceError("DeepSeek", 402, "deepseek-flash", "https://api.deepseek.com", DEEPSEEK_402)
    return InsufficientBalanceError("OpenAI", 429, "gpt-6-luna", "https://api.openai.com", OPENAI_QUOTA)


class Switch:
    """on 이면 n 번째 호출부터 잔액 부족을 낸다."""

    def __init__(self, after: int):
        self.after, self.n, self.on = after, 0, True

    def hit(self) -> bool:
        self.n += 1
        return self.on and self.n > self.after


class PoorLLM(FakeLLM):
    def __init__(self, switch, **kw):
        super().__init__(**kw)
        self.switch = switch

    def chat(self, messages, stream_ttft=False):
        if self.switch.hit():
            raise quota_error("OpenAI")
        return super().chat(messages, stream_ttft)


class PoorJudge(FakeJudge):
    def __init__(self, switch):
        super().__init__()
        self.switch = switch

    def chat(self, messages, stream_ttft=False):
        if self.switch.hit():
            raise quota_error("DeepSeek")
        return super().chat(messages, stream_ttft)


class PoorSummaryLLM(FakeSummaryLLM):
    def __init__(self, switch):
        super().__init__()
        self.switch = switch

    def chat(self, messages, stream_ttft=False):
        if self.switch.hit():
            raise quota_error("OpenAI")
        return super().chat(messages, stream_ttft)


class FakeResponse:
    def __init__(self, status, text):
        self.status_code, self.text, self.ok = status, text, status < 400

    def json(self):
        return json.loads(self.text)

    def close(self):
        pass


class DetectTest(unittest.TestCase):
    def test_classify(self):
        self.assertIsNotNone(balance_error_of(429, OPENAI_QUOTA, "m", "https://api.openai.com"))
        self.assertIsNotNone(balance_error_of(402, DEEPSEEK_402, "m", "https://api.deepseek.com"))
        self.assertIsNone(balance_error_of(429, '{"error": {"code": "rate_limit_exceeded"}}', "m", "https://api.openai.com"))
        self.assertIsNone(balance_error_of(500, "server error", "m", "https://api.openai.com"))
        self.assertEqual(balance_error_of(402, DEEPSEEK_402, "m", "https://api.deepseek.com").provider, "DeepSeek")

    def _llm(self):
        return LLM(backend="openai", base_url="https://api.openai.com", api_key="k", model="gpt-6-luna", max_retries=3)

    def test_quota_not_retried(self):
        l = self._llm()
        with mock.patch.object(llm_mod.requests, "post", return_value=FakeResponse(429, OPENAI_QUOTA)) as post, \
             mock.patch.object(llm_mod.time, "sleep") as sleep:
            with self.assertRaises(InsufficientBalanceError) as cm:
                l.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(post.call_count, 1)                 # 재시도 없음
        sleep.assert_not_called()
        self.assertEqual((cm.exception.provider, cm.exception.status), ("OpenAI", 429))

    def test_rate_limit_still_retried(self):
        l = self._llm()
        with mock.patch.object(llm_mod.requests, "post",
                               return_value=FakeResponse(429, '{"error": {"code": "rate_limit_exceeded"}}')) as post, \
             mock.patch.object(llm_mod.time, "sleep"):
            with self.assertRaises(llm_mod.requests.HTTPError):
                l.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(post.call_count, 3)                 # 일시적 오류는 그대로 재시도

    def test_failure_not_cached(self):
        with tempfile.TemporaryDirectory() as d:
            sw = Switch(0)
            c = CachedLLM(PoorLLM(sw), path=Path(d) / "c.sqlite", enabled=True)
            msgs = [{"role": "user", "content": "q"}]
            with self.assertRaises(InsufficientBalanceError):
                c.chat(msgs, sample_idx=0)
            self.assertIsNone(c.get(cache_key(c.llm, msgs, 0)))
            sw.on = False
            res, hit = c.chat(msgs, sample_idx=0)
            self.assertFalse(hit)
            c.close()


class ReplayStopResumeTest(unittest.TestCase):
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

    def _cfg(self, **kw):
        base = dict(compressors=["none", "window(1)", "rolling_summary(r=0.5)"], samples=2, concurrency=3,
                    summary_model="gpt-6-luna", summary_reasoning_effort="server_default", summary_max_tokens=1000)
        base.update(kw)
        return make_cfg(**base)

    def _replay(self, cfg, answer_llm, judge_llm, sum_llm, run="mt_bal"):
        path = self.root / "c.sqlite"
        answer = CachedLLM(rp.configure_answer_llm(answer_llm, cfg), path=path, enabled=True)
        judge = CachedLLM(judge_llm, path=path, enabled=True)
        summ = Summarizer(CachedLLM(rp.configure_summary_llm(sum_llm, cfg), path=path, enabled=True))
        self.caches += [answer, judge, summ.cached]
        return rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / run,
                         reference_root=self.root / "refs", grade_fn=fake_grade_with_judge, sleep=lambda s: None,
                         summarizer=summ)

    def _rows(self, run="mt_bal"):
        p = self.root / run / "turn_trials.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def _segments(self, run="mt_bal"):
        return [json.loads(l) for l in (self.root / run / "run_segments.jsonl").read_text(encoding="utf-8").splitlines()]

    def _stop_then_resume(self, where: str, after: int, provider: str):
        cfg = self._cfg()
        a_sw, j_sw, s_sw = Switch(10 ** 9), Switch(10 ** 9), Switch(10 ** 9)
        {"answer": a_sw, "judge": j_sw, "summary": s_sw}[where].after = after
        rep = self._replay(cfg, PoorLLM(a_sw), PoorJudge(j_sw), PoorSummaryLLM(s_sw))
        with self.assertRaises(rp.ReplayStoppedError) as cm:
            rep.run()
        self.assertEqual(cm.exception.balance.provider, provider)
        rows = self._rows()
        total = len(SCENARIO["turns"]) * 3 * cfg.samples
        self.assertLess(len(rows), total)
        self.assertFalse(any(r.get("summary_failed") for r in rows))       # 잔액 부족을 요약 실패로 치지 않는다
        self.assertTrue(all(r.get("answer_accuracy") is not None for r in rows))
        errs = [json.loads(l) for l in (self.root / "mt_bal" / "errors.jsonl").read_text(encoding="utf-8").splitlines()]
        bal = [e for e in errs if e.get("kind") == "insufficient_balance"]
        self.assertEqual(len(bal), 1)
        self.assertEqual(bal[0]["provider"], provider)
        seg = self._segments()
        self.assertEqual([s["event"] for s in seg], ["start", "end"])
        self.assertEqual(seg[1]["status"], "stopped_insufficient_balance")
        stopped_rows = len(rows)
        # 잔액을 채움 -> 같은 run 을 이어서 끝낸다
        for sw in (a_sw, j_sw, s_sw):
            sw.on = False
        rep2 = self._replay(cfg, PoorLLM(a_sw), PoorJudge(j_sw), PoorSummaryLLM(s_sw))
        summary = rep2.run()
        rows = self._rows()
        keys = [(r["scenario_id"], r["turn"], r["compressor"], r["sample_idx"]) for r in rows]
        self.assertEqual(len(rows), total)
        self.assertEqual(len(set(keys)), total)                              # 중복 없이 이어 붙음
        self.assertFalse(any(r.get("summary_failed") for r in rows))
        seg = self._segments()
        self.assertEqual([(s["segment"], s["event"]) for s in seg], [(1, "start"), (1, "end"), (2, "start"), (2, "end")])
        self.assertEqual(seg[2]["rows_before"], stopped_rows)
        self.assertTrue(seg[2]["resumed"])
        self.assertEqual((seg[3]["status"], seg[3]["rows_after"], seg[3]["rows_appended"], seg[3]["duplicate_keys"]),
                         ("finished", total, total - stopped_rows, 0))
        self.assertIn("compressors", summary)

    def test_answer_quota(self):
        self._stop_then_resume("answer", 20, "OpenAI")

    def test_judge_quota(self):
        self._stop_then_resume("judge", 6, "DeepSeek")

    def test_summary_quota(self):
        self._stop_then_resume("summary", 1, "OpenAI")

    def test_references_only_then_resume(self):
        """--references-only: 기준 궤적·채점만 만들고 멈춘다. 이어서 돌리면 trial 만 돈다."""
        cfg = self._cfg()
        off = Switch(10 ** 9)
        rep = self._replay(cfg, PoorLLM(off), PoorJudge(off), PoorSummaryLLM(off))
        out = rep.run(references_only=True)
        self.assertTrue(out["references_only"])
        self.assertEqual(self._rows(), [])
        ref = json.loads((self.root / "mt_bal" / "reference_grades.json").read_text(encoding="utf-8"))
        self.assertEqual(len(ref["s1"]), len(SCENARIO["turns"]))
        self.assertEqual(self._segments()[-1]["status"], "references_only")
        rep2 = self._replay(cfg, PoorLLM(off), PoorJudge(off), PoorSummaryLLM(off))
        summary = rep2.run()
        self.assertEqual(len(self._rows()), len(SCENARIO["turns"]) * 3 * cfg.samples)
        hits = summary["compress_length_hits"]["rolling_summary(r=0.5)[sre=server_default]"]
        self.assertEqual(hits["length_hits"], 0)
        self.assertGreater(hits["calls"], 0)

    def test_reference_quota(self):
        """기준 궤적 단계에서 잔액 부족: trial 없이 멈추고, 이어서 처음부터 끝낸다."""
        cfg = self._cfg()
        a_sw = Switch(2)
        rep = self._replay(cfg, PoorLLM(a_sw), PoorJudge(Switch(10 ** 9)), PoorSummaryLLM(Switch(10 ** 9)))
        with self.assertRaises(rp.ReplayStoppedError):
            rep.run()
        self.assertEqual(self._rows(), [])
        a_sw.on = False
        rep2 = self._replay(cfg, PoorLLM(a_sw), PoorJudge(Switch(10 ** 9)), PoorSummaryLLM(Switch(10 ** 9)))
        rep2.run()
        self.assertEqual(len(self._rows()), len(SCENARIO["turns"]) * 3 * cfg.samples)


def fake_grade_with_judge(question, reference, key_facts, candidate, judge_llm, mode="per_fact", **kw):
    """채점 중 잔액 부족을 재현하려고 judge 를 실제로 한 번 부른다 (응답은 쓰지 않는다)."""
    judge_llm.chat([{"role": "user", "content": f"judge: {question} | {candidate}"}])
    return fake_grade(question, reference, key_facts, candidate, judge_llm, mode=mode)


class PreflightTest(unittest.TestCase):
    def test_stops_on_quota_and_connection(self):
        class Ok:
            model, base_url = "gpt-6-luna", "https://api.openai.com"

            def chat(self, m):
                return llm_mod.LLMResult(text="OK", prompt_tokens=5, completion_tokens=1, latency=0.0, model=self.model)

        class Poor(Ok):
            model, base_url = "deepseek-flash", "https://api.deepseek.com"

            def chat(self, m):
                raise quota_error("DeepSeek")

        class Down(Ok):
            model, base_url = "deepseek-flash", "https://api.deepseek.com"

            def chat(self, m):
                raise llm_mod.requests.ConnectionError("tls timeout")

        out = rp.preflight_check([("answer", Ok()), ("summary", Ok())], log=lambda *_: None)
        self.assertEqual(len(out), 1)                                       # 같은 (모델, 주소) 는 한 번만
        with self.assertRaises(SystemExit) as cm:
            rp.preflight_check([("answer", Ok()), ("judge", Poor())], log=lambda *_: None)
        self.assertIn("잔액 부족", str(cm.exception))
        with self.assertRaises(SystemExit) as cm:
            rp.preflight_check([("judge", Down())], log=lambda *_: None)
        self.assertIn("연결되지 않습니다", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
