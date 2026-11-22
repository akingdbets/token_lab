"""
멀티턴 3단계: window_budget, query_select, rolling_summary, frozen_summary 와 replay 의 상태 처리.
가짜 LLM·가짜 토큰 카운터로 네트워크 없이 돈다.

검증: 예산 준수·overflow 표시, 고정 요약 접두부 불변, 재압축 기록, 정보 누출 금지(요약기·선택 함수),
요약 실패 처리(캐시 미저장·재시도·체인 표시·0점 집계), 상태 재구성(이어 돌리기), query_select 가 직전 턴을 남기는지,
프롬프트 v1/v2 기준 궤적 분리, 예산별 비교표·접두부 지표, 필수 인자.

    python -m unittest tests.test_mt_summary_budget
"""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import LLMResult  # noqa: E402
from multiturn import replay as rp  # noqa: E402
from multiturn.history_compressors import (  # noqa: E402
    Summarizer, expand_budgets, get_history_compressor, select_history,
)
from multiturn.history_compressors.budget import history_tokens  # noqa: E402
from multiturn.prompt import load_mt_prompt  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_replay import (  # noqa: E402
    PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, fake_count_tokens, fake_grade, make_cfg,
)

SYS = {"role": "system", "content": "SYS"}


def doc_turn(i, body, answer):
    return [{"role": "user", "content": f"<documentation>\n## Document: p{i}.md\n\n{body}\n</documentation>\n\n"
                                        f"Question: question {i}\n\nAnswer format: f"},
            {"role": "assistant", "content": answer}]


def history(n, filler=60):
    h = [SYS]
    for i in range(n):
        h += doc_turn(i, f"Fact {i}: the value of key{i} is {i * 11}. " + "Padding words here. " * filler,
                      f"answer {i}")
    return h


class FakeSummaryLLM(FakeLLM):
    """요약 요청을 받으면 짧은 요약을 돌려준다. fail=True 면 빈 요약."""

    def __init__(self, fail=False, length=False, size=5):
        super().__init__()
        self.fail, self.length, self.size = fail, length, size

    def chat(self, messages, stream_ttft=False):
        self.calls.append(messages)
        text = "" if self.fail else f"- (turn x) summary #{len(self.calls)} " + "fact " * self.size
        return LLMResult(text=text, prompt_tokens=sum(len(m["content"]) // 4 for m in messages), completion_tokens=40,
                         latency=0.0, model=self.model, reasoning_tokens=20,
                         finish_reason="length" if self.length else "stop")


def summarizer(tmp: Path, llm=None):
    llm = llm or FakeSummaryLLM()
    return Summarizer(CachedLLM(llm, path=tmp / "sum.sqlite", enabled=True)), llm


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.summs = []

    def tearDown(self):
        for s_ in self.summs:
            s_.cached.close()
        self.tmp.cleanup()

    def summ(self, llm=None):
        s_, l_ = summarizer(self.root, llm)
        self.summs.append(s_)
        return s_, l_


class BudgetCompressorTest(unittest.TestCase):
    def test_expand_budgets(self):
        self.assertEqual(expand_budgets(["none", "window_budget", "window(2)", "query_select(50)"], [10, 20]),
                         ["none", "window_budget(10)", "window_budget(20)", "window(2)", "query_select(50)"])
        with self.assertRaises(ValueError):
            expand_budgets(["rolling_summary"], [])
        with self.assertRaises(KeyError):
            get_history_compressor("window_budget")

    def test_window_budget_respects_budget_and_flags_overflow(self):
        h = history(4)
        per_turn = history_tokens(h[1:3], fake_count_tokens)
        hc = get_history_compressor(f"window_budget({per_turn * 2 + 5})", token_counter=fake_count_tokens)
        r = hc.compress_history(h, "Question: now")
        self.assertEqual(r.info["turns_kept"], 2)
        self.assertFalse(r.info["overflow"])
        self.assertLessEqual(r.info["history_tokens"], per_turn * 2 + 5)
        r = get_history_compressor("window_budget(10)", token_counter=fake_count_tokens).compress_history(h, "Q")
        self.assertEqual(r.info["turns_kept"], 1)                  # 최근 1턴은 넘쳐도 남긴다
        self.assertTrue(r.info["overflow"])
        self.assertEqual(r.messages[1:3], h[-2:])

    def test_query_select_signature_has_no_leak_inputs(self):
        params = list(inspect.signature(select_history).parameters)
        self.assertEqual(params, ["question", "past", "budget", "token_counter", "keep_recent"])
        for banned in ("answer", "key_facts", "evidence", "turn_type", "depends_on", "key_entities"):
            self.assertNotIn(banned, params)

    def test_query_select_keeps_recent_and_selects_relevant(self):
        h = history(5)
        budget = history_tokens(h[-2:], fake_count_tokens) + 120
        hc = get_history_compressor(f"query_select({budget})", token_counter=fake_count_tokens)
        r = hc.compress_history(h, "Question: what is the value of key1?\n\nAnswer format: f")
        self.assertEqual(r.messages[-3:-1], h[-2:])                # 직전 턴 원문
        sel = r.messages[1]["content"]
        self.assertTrue(sel.startswith("<selected_history>"))
        self.assertIn("[turn 1 · document p1.md]", sel)
        self.assertIn("Fact 1: the value of key1 is 11.", sel)
        self.assertLessEqual(r.info["history_tokens"], budget)
        self.assertFalse(r.info["overflow"])
        # 원래 순서대로 배치
        self.assertLess(sel.find("[turn 0"), sel.find("[turn 1")) if "[turn 0" in sel else None
        # 예산이 직전 턴보다 작으면 선택 없이 직전 턴만, overflow
        r = get_history_compressor("query_select(5)", token_counter=fake_count_tokens).compress_history(h, "Question: key1")
        self.assertEqual(r.messages[1:-1], h[-2:])
        self.assertTrue(r.info["overflow"])


class SummaryCompressorTest(_Tmp):
    def _chain(self, name, n_turns, summ, budget_turns=2.5):
        per_turn = history_tokens(history(1)[1:], fake_count_tokens)
        b = int(per_turn * budget_turns)
        hc = get_history_compressor(f"{name}({b})", token_counter=fake_count_tokens, summarizer=summ)
        state = hc.initial_state(0)
        outs = []
        for k in range(n_turns):
            r = hc.compress_history(history(k), f"Question: CURRENT-QUESTION-{k}\n\nAnswer format: f", None, state)
            state = r.state
            outs.append(r)
        return outs, b

    def test_rolling_summary_budget_and_labels(self):
        summ, llm = self.summ()
        outs, b = self._chain("rolling_summary", 7, summ)
        self.assertTrue(any(o.info["summary_calls"] for o in outs))
        for o in outs:
            self.assertLessEqual(o.info["history_tokens"], b)
            self.assertFalse(o.info["overflow"])
        last = outs[-1].messages
        self.assertTrue(last[1]["content"].startswith('<conversation_summary turns="0-'))
        self.assertEqual(sum(m["content"].startswith("<conversation_summary") for m in last), 1)   # 요약 하나
        self.assertGreater(outs[-1].llm_prompt_tokens + sum(o.llm_completion_tokens for o in outs), 0)

    def test_summarizer_never_sees_current_turn(self):
        summ, llm = self.summ()
        self._chain("rolling_summary", 7, summ)
        self._chain("frozen_summary", 7, summ)
        self.assertTrue(llm.calls)
        for msgs in llm.calls:
            text = "\n".join(m["content"] for m in msgs)
            self.assertNotIn("CURRENT-QUESTION", text)
        params = list(inspect.signature(Summarizer.summarize).parameters)
        self.assertEqual(params, ["self", "turns", "previous", "target_tokens", "sample_idx"])

    def test_frozen_prefix_unchanged_and_recompress_recorded(self):
        per_turn = history_tokens(history(1)[1:], fake_count_tokens)
        summ, llm = self.summ(FakeSummaryLLM(size=per_turn // 2))      # 블록이 쌓이면 예산을 넘을 만큼 큰 요약
        outs, b = self._chain("frozen_summary", 9, summ, budget_turns=3.2)
        blocks_seen = {}
        for k in range(1, len(outs)):
            prev, cur = outs[k - 1], outs[k]
            prev_req = prev.messages
            cur_req = cur.messages
            if not cur.info["recompressed"]:
                # 이전 블록 메시지는 글자 그대로 남는다
                pb = [m for m in prev_req if m["content"].startswith("<conversation_summary")]
                cb = [m for m in cur_req if m["content"].startswith("<conversation_summary")]
                self.assertEqual(cb[:len(pb)], pb)
            if not cur.info["summary_calls"]:
                # 재압축도 새 블록도 없는 연속 턴: 이전 요청(현재 턴 메시지 전까지)이 다음 요청의 접두부
                self.assertEqual(cur_req[:len(prev_req) - 1], prev_req[:-1])
                blocks_seen[k] = True
        self.assertTrue(blocks_seen, "새 요약 없이 이어진 턴이 있어야 한다")
        rec = [o for o in outs if o.info["recompressed"]]
        self.assertTrue(rec, "재압축이 한 번은 일어나야 한다")
        self.assertEqual(rec[0].info["recompress_turns"][0], outs.index(rec[0]))

    def test_failure_not_cached_and_retried(self):
        llm = FakeSummaryLLM(fail=True)
        summ, _ = self.summ(llm)
        outs = []
        per_turn = history_tokens(history(1)[1:], fake_count_tokens)
        hc = get_history_compressor(f"rolling_summary({per_turn * 2})", token_counter=fake_count_tokens, summarizer=summ)
        state = hc.initial_state(0)
        for k in range(5):
            r = hc.compress_history(history(k), "Question: q", None, state)
            outs.append(r)
            if r.info.get("summary_failed"):
                break
            state = r.state
        self.assertTrue(outs[-1].info["summary_failed"])
        self.assertEqual(outs[-1].info["summary_attempts"], 3)
        self.assertEqual(len(llm.calls), 3)
        self.assertEqual(outs[-1].messages[1:-1], [])             # 원문으로 대체하지 않는다 (과거 기록 없음)
        # 실패 응답은 캐시에 없다 -> 다시 부르면 새로 호출
        n = len(llm.calls)
        hc.compress_history(history(len(outs) - 1), "Question: q", None, state)
        self.assertEqual(len(llm.calls), n + 3)

    def test_length_counts_as_failure(self):
        summ, llm = self.summ(FakeSummaryLLM(length=True))
        o = summ.summarize([(0, history(1)[1:])], None, 300, 0)
        self.assertTrue(o.failed)
        self.assertEqual(o.reason, "length")


class ReplayStage3Test(unittest.TestCase):
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
        base = dict(compressors=["none", "window_budget", "query_select", "rolling_summary", "frozen_summary"],
                    history_budgets=[1500, 3000], samples=2, summary_model="gpt-6-luna",
                    summary_reasoning_effort="server_default", summary_max_tokens=1000)
        base.update(kw)
        return make_cfg(**base)

    def _replay(self, cfg, llm=None, sum_llm=None, run="mt_s3"):
        llm = llm or FakeLLM()
        sum_llm = sum_llm or FakeSummaryLLM()
        answer = CachedLLM(rp.configure_answer_llm(llm, cfg), path=self.root / "c.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / "c.sqlite", enabled=True)
        summ = Summarizer(CachedLLM(rp.configure_summary_llm(sum_llm, cfg), path=self.root / "c.sqlite", enabled=True))
        self.caches += [answer, judge, summ.cached]
        return rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / run,
                         reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None,
                         summarizer=summ), llm, sum_llm

    def _rows(self, run="mt_s3"):
        rows = {}
        for l in (self.root / run / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            rows[(r["turn"], r["compressor"], r["sample_idx"])] = r
        return rows

    def test_end_to_end_budget_table_and_prefix(self):
        rep, llm, sum_llm = self._replay(self._cfg())
        summary = rep.run()
        rows = self._rows()
        self.assertEqual(len(rows), 6 * (1 + 4 * 2) * 2)
        self.assertEqual(set(summary["budget_table"]), {"1500", "3000"})
        for fam in ("window_budget", "query_select", "rolling_summary[sre=server_default]",
                    "frozen_summary[sre=server_default]"):
            self.assertIn(fam, summary["budget_table"]["1500"])
        r = rows[(3, "rolling_summary(1500)[sre=server_default]", 0)]
        for k in ("prefix_shared_tokens", "prefix_shared_tokens_raw", "overflow", "history_budget", "compress_cost",
                  "summary_calls", "compressor_family"):
            self.assertIn(k, r)
        self.assertEqual(r["history_budget"], 1500)
        # 1,024 기준: 원래 값이 1,024 미만이면 0
        for x in rows.values():
            if x.get("prefix_shared_tokens_raw") is not None and x["prefix_shared_tokens_raw"] < 1024:
                self.assertEqual(x["prefix_shared_tokens"], 0)
        none3 = rows[(3, "none", 1)]
        self.assertGreater(none3["prefix_shared_tokens_raw"], 0)       # none 은 직전 턴 요청이 접두부
        self.assertTrue(sum_llm.calls)
        self.assertGreater(summary["budget"]["summary_calls_usd_experimental"], 0)
        self.assertIn("cache_by_compressor", summary)
        # 요약 비용이 비용 절감률에 들어간다 (compress_cost)
        self.assertGreater(summary["compressors"]["rolling_summary(1500)[sre=server_default]"]["all"]["compress_cost_usd"], 0)
        # 비용 주 지표는 시뮬레이션 캐시 비용, 실측은 참고. overflow 제외 집계
        blk = summary["compressors"]["window_budget(1500)"]["all"]
        for k in ("cost_reduction_pct_sim", "cost_reduction_pct_sim_write", "cost_reduction_pct_measured"):
            self.assertIn(k, blk)
        self.assertEqual(blk["cost_basis"], "simulated_prefix_cache")
        self.assertIsNotNone(blk["excluding_overflow"])
        tb = summary["budget_table"]["1500"]["window_budget"]
        self.assertIn("retention_pct_excluding_overflow", tb)
        self.assertIn("cost_reduction_pct_sim", tb)
        self.assertTrue(any("병렬" in n for n in summary["notes"]))
        self.assertTrue(any("30분" in n and "만료" in n for n in summary["notes"]))   # sim / nocache 해석
        self.assertIn("cost_sim", r)

    def test_state_rebuilt_from_cache_on_resume(self):
        cfg = self._cfg(compressors=["none", "rolling_summary"], history_budgets=[1500])
        rep, llm, sum_llm = self._replay(cfg)
        rep.run()
        n_answer, n_sum = len(llm.calls), len(sum_llm.calls)
        # 체인 중간 턴 기록을 지우고 다시 돌린다 -> 앞 턴은 압축만 다시 (요약은 캐시 적중), 지운 턴만 답변
        p = self.root / "mt_s3" / "turn_trials.jsonl"
        lines = [l for l in p.read_text(encoding="utf-8").splitlines()
                 if not (json.loads(l)["compressor"] == "rolling_summary(1500)[sre=server_default]" and json.loads(l)["turn"] >= 4)]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rep2, _, _ = self._replay(cfg, llm=llm, sum_llm=sum_llm)
        rep2.run()
        self.assertEqual(len(sum_llm.calls), n_sum)                    # 요약은 전부 캐시에서
        self.assertEqual(len(llm.calls) - n_answer, 0)                 # 답변도 같은 요청이라 캐시 적중
        rows = self._rows()
        self.assertTrue(all((k, "rolling_summary(1500)[sre=server_default]", i) in rows for k in range(6) for i in range(2)))

    def test_summary_failure_marks_chain_and_scores_zero(self):
        cfg = self._cfg(compressors=["none", "rolling_summary"], history_budgets=[1500])
        rep, llm, sum_llm = self._replay(cfg, sum_llm=FakeSummaryLLM(fail=True))
        summary = rep.run()
        rows = self._rows()
        fails = [r for r in rows.values() if r["compressor"] == "rolling_summary(1500)[sre=server_default]" and r["summary_failed"]]
        self.assertTrue(fails)
        first = min(r["turn"] for r in fails)
        self.assertTrue(all(r["answer_accuracy"] == 0.0 for r in fails))
        self.assertTrue(all(r["skipped_after_summary_failure"] == (r["turn"] != first) for r in fails))
        self.assertTrue(all(rows[(k, "rolling_summary(1500)[sre=server_default]", 0)]["summary_failed"] for k in range(first, 6)))
        # 답변은 실패 턴부터 부르지 않았다
        sent = [m for m in llm.calls if "Sum again?" in m[-1]["content"]]
        self.assertEqual(len(sent), 1 + 1)                               # 기준 궤적 + none sample 1
        sf = summary["summary_failure"]["rolling_summary(1500)[sre=server_default]"]
        self.assertGreater(sf["rate"], 0)
        block = summary["compressors"]["rolling_summary(1500)[sre=server_default]"]["all"]
        self.assertEqual(block["summary_failed"], len(fails))
        self.assertIsNotNone(block["excluding_summary_failed"])
        # 재시도: 실패 응답은 캐시에 없으므로 이어 돌리면 다시 요약을 부른다
        n = len(sum_llm.calls)
        rep2, _, _ = self._replay(cfg, llm=llm, sum_llm=sum_llm)
        rep2.run()
        self.assertGreater(len(sum_llm.calls), n)

    def test_prompt_versions_do_not_mix_references(self):
        cfg1, cfg2 = make_cfg(prompt_version="v1"), make_cfg(prompt_version="v2")
        llm = FakeLLM()
        k1 = rp.reference_key(cfg1, llm, load_mt_prompt("v1"), SCENARIO)
        k2 = rp.reference_key(cfg2, llm, load_mt_prompt("v2"), SCENARIO)
        self.assertNotEqual(k1, k2)
        self.assertEqual(make_cfg().prompt_version, "v2")
        self.assertIn("<conversation_summary>", load_mt_prompt("v2").system)
        self.assertIn("reply exactly: NOT FOUND", load_mt_prompt("v2").system)
        rep, _, _ = self._replay(self._cfg(compressors=["none"], history_budgets=[]))
        rep.build_references()
        rep_v1, _, _ = self._replay(self._cfg(compressors=["none"], history_budgets=[], prompt_version="v1"), run="mt_v1")
        rep_v1.build_references()
        self.assertEqual(len(list((self.root / "refs").iterdir())), 2)

    def test_required_summary_args(self):
        with self.assertRaises(ValueError):
            make_cfg(compressors=["none", "rolling_summary"], history_budgets=[1000])
        with self.assertRaises(ValueError):
            make_cfg(compressors=["none", "frozen_summary(1000)"], summary_model="m",
                     summary_reasoning_effort="bogus", summary_max_tokens=10)
        with self.assertRaises(ValueError):
            make_cfg(compressors=["none", "window_budget"])                 # 예산 없음
        cfg = make_cfg(compressors=["none", "window_budget"], history_budgets=[100, 200])
        self.assertEqual(cfg.compressors, ["none", "window_budget(100)", "window_budget(200)"])
        a = rp.build_parser().parse_args(["--scenarios", "x", "--model", "m", "--reasoning-effort", "low",
                                          "--max-completion-tokens", "5", "--compressors", "none,query_select",
                                          "--history-budget", "1000,2000"])
        self.assertEqual(rp.config_from_args(a).compressors, ["none", "query_select(1000)", "query_select(2000)"])


class Stage3bTest(ReplayStage3Test):
    """요약 추론 조건 펼치기, 시뮬레이션 캐시 비용, --sequential-chains, 추정의 조건별 요약 비용."""

    def test_summary_efforts_expand_and_use_separate_summarizers(self):
        cfg = self._cfg(compressors=["none", "rolling_summary"], history_budgets=[1500],
                        summary_reasoning_effort="server_default,none")
        self.assertEqual(cfg.compressors, ["none", "rolling_summary(1500)[sre=server_default]",
                                           "rolling_summary(1500)[sre=none]"])
        llm_a, llm_b = FakeSummaryLLM(), FakeSummaryLLM()
        answer = CachedLLM(rp.configure_answer_llm(FakeLLM(), cfg), path=self.root / "c.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / "c.sqlite", enabled=True)
        summ = {e: Summarizer(CachedLLM(rp.configure_summary_llm(l, cfg, e), path=self.root / "c.sqlite", enabled=True))
                for e, l in (("server_default", llm_a), ("none", llm_b))}
        self.caches += [answer, judge] + [x.cached for x in summ.values()]
        self.assertEqual(llm_b.reasoning_effort, "none")
        self.assertEqual(llm_a.reasoning_effort, "")                   # server_default = 보내지 않음
        summary = rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / "mt_e",
                            reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None,
                            summarizer=summ).run()
        self.assertTrue(llm_a.calls and llm_b.calls)                   # 조건마다 따로 요약
        self.assertEqual(set(summary["budget_table"]["1500"]),
                         {"rolling_summary[sre=server_default]", "rolling_summary[sre=none]"})
        with self.assertRaises(ValueError):
            self._cfg(compressors=["none", "rolling_summary(1500)[sre=low]"], history_budgets=[])

    def test_sim_cost_uses_prefix_tokens(self):
        row = {"model": "gpt-6-luna", "prompt_tokens": 10000, "input_tokens_est": 5000,
               "prefix_shared_tokens": 2500, "completion_tokens": 1000}
        c = rp.sim_cost(row)
        self.assertEqual(c["sim_cached_tokens"], 5000)                 # API 단위로 맞춤
        M = 1_000_000
        self.assertAlmostEqual(c["usd_nocache"], (10000 * 0.10 + 1000 * 0.50) / M)
        self.assertAlmostEqual(c["usd_read"], (5000 * 0.10 + 5000 * 0.01 + 1000 * 0.50) / M)
        self.assertAlmostEqual(c["usd_write"], (5000 * 0.125 + 5000 * 0.01 + 1000 * 0.50) / M)
        row["prefix_shared_tokens"] = 0
        self.assertEqual(rp.sim_cost(row)["sim_cached_tokens"], 0)

    def test_sequential_chains_no_cache_in_order(self):
        cfg = self._cfg(compressors=["none"], history_budgets=[1500])
        rep, llm, sum_llm = self._replay(cfg, run="mt_seq")
        rep.build_references()
        n = len(llm.calls)

        out = rep.run_sequential(["none", "frozen_summary(1500)[sre=server_default]"], ["s1"], [0])
        self.assertEqual(len(llm.calls) - n, 6 * 2)                    # 응답 캐시 없이 체인마다 6턴 전부 호출
        rows = [json.loads(l) for l in (self.root / "mt_seq" / "sequential_chains.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["turn"] for r in rows if r["compressor"] == "none"], list(range(6)))
        for r in rows:
            for k in ("sim_cached_tokens", "cached_tokens", "prompt_tokens", "prefix_shared_tokens_raw"):
                self.assertIn(k, r)
        self.assertIn("none", out)
        self.assertIn("measured_hit_rate", out["none"])
        self.assertTrue((self.root / "mt_seq" / "sequential_summary.json").exists())
        self.assertFalse((self.root / "mt_seq" / "turn_trials.jsonl").exists())    # replay 는 돌리지 않는다
        # 같은 순서로 한 번 더 돌려도 응답 캐시를 쓰지 않는다
        rep.run_sequential(["none"], ["s1"], [0])
        self.assertEqual(len(llm.calls) - n, 6 * 3)

    def test_estimate_effort_costs(self):
        from multiturn import estimate as est_mod
        cfg = self._cfg(compressors=["none", "frozen_summary"], history_budgets=[1500],
                        summary_reasoning_effort="server_default,none")
        e = est_mod.estimate(cfg, [SCENARIO], FakeCorpus(), judge_model="deepseek-flash",
                             summary_tokens=100, summary_reasoning_tokens=1000)
        by = e["summary_usd_by_effort"]
        self.assertEqual(set(by), {"server_default", "none"})
        self.assertEqual(by["none"]["reasoning_tokens_assumed"], 0)
        self.assertGreater(by["server_default"]["summary_usd"], by["none"]["summary_usd"])
        self.assertIn("frozen_summary(1500)[sre=none]", e["compressors"])


if __name__ == "__main__":
    unittest.main()
