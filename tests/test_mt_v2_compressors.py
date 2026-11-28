"""
멀티턴 v2 압축기 준비: 비율 예산, v2 세트, presummary, fact_notes, 토큰 기준 summary (--cost-mode).
가짜 LLM·가짜 토큰 카운터로 네트워크 없이 돈다.

검증
    비율 예산    window_budget(r=0.5) 가 그 턴 원본 기록 × r 을 예산으로 쓴다 (체인 안에서도 원본 기준). 이름·펼치기·비교표 키
    v2 세트      --compressors v2 가 정한 9종으로 펼쳐지고, 뺀 압축기(window(n), frozen_summary, on_arrival(llmlingua2)) 는 없다
    presummary   과거 문서만 페이지 요약으로 바꾼다 (직전 keep_recent 턴·현재 턴 원문). 요약이 없으면 멈춘다. 압축 LLM 토큰 0.
                 구축 스크립트: 필요한 페이지만, 있으면 건너뜀, 설정이 다르면 멈춤, 압축률 기록
    fact_notes   과거 턴 문서 블록을 메모로, 문서 없는 턴은 메모 없음. 정보 누출 금지(인자·실제 보낸 메시지),
                 메모 재사용(같은 턴·sample 은 한 번 호출), 토큰은 만든 턴 trial 에 귀속, 목표 길이가 프롬프트에 들어감
    summary      기본 cost-mode none 이면 캐시 지표 없음, 토큰 항목 분해, 턴 유형(시나리오 값 그대로)·recall 거리별 정확도

    python -m unittest tests.test_mt_v2_compressors
"""

from __future__ import annotations

import inspect
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import LLMResult  # noqa: E402
from multiturn import build_presummaries as bp  # noqa: E402
from multiturn import replay as rp  # noqa: E402
from multiturn.history_compressors import (  # noqa: E402
    COMPRESSOR_SETS, MissingPresummaryError, NotesExtractor, NotesFailedError, PresummaryStore, budget_of,
    expand_budgets, expand_sets, get_history_compressor, parse_budget_list,
)
from multiturn.history_compressors.budget import history_tokens  # noqa: E402
from multiturn.history_compressors.notes import load_section_prompt  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_replay import (  # noqa: E402
    PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, fake_count_tokens, fake_grade, make_cfg,
)
from test_mt_summary_budget import FakeSummaryLLM, history  # noqa: E402

SYS = {"role": "system", "content": "SYS"}


def doc_user(page, body, q):
    return f"<documentation>\n## Document: {page}\n\n{body}\n</documentation>\n\nQuestion: {q}\n\nAnswer format: f"


class FakeNotesLLM(FakeLLM):
    """메모 요청: 문서에서 'value is' 가 든 줄을 뽑아 턴 표시를 붙여 돌려준다. fail=True 면 빈 출력."""

    def __init__(self, fail=False):
        super().__init__()
        self.fail = fail

    def chat(self, messages, stream_ttft=False):
        self.calls.append(messages)
        u = messages[-1]["content"]
        turn = re.search(r"^Turn (\d+)", u, re.M).group(1)
        facts = [ln.strip() for ln in u.split("\n") if "value is" in ln]
        text = "" if self.fail else "\n".join(f"- (turn {turn}) {f}" for f in facts) or f"- (turn {turn}) nothing"
        return LLMResult(text=text, prompt_tokens=sum(len(m["content"]) // 4 for m in messages), completion_tokens=40,
                         latency=0.0, model=self.model, reasoning_tokens=25, finish_reason="stop")


class FakePresumLLM(FakeLLM):
    def chat(self, messages, stream_ttft=False):
        self.calls.append(messages)
        u = messages[-1]["content"]
        facts = [ln.strip() for ln in u.split("\n") if "value is" in ln]
        return LLMResult(text="- " + "; ".join(facts), prompt_tokens=len(u) // 4, completion_tokens=30, latency=0.0,
                         model=self.model, reasoning_tokens=10, finish_reason="stop")


def write_store(root: Path, pages: dict) -> PresummaryStore:
    root.mkdir(parents=True, exist_ok=True)
    (root / "_manifest.json").write_text(json.dumps({"model": "fake", "target_ratio": 0.25}), encoding="utf-8")
    for page, text in pages.items():
        (root / page).parent.mkdir(parents=True, exist_ok=True)
        (root / page).write_text(text, encoding="utf-8")
    return PresummaryStore(root)


class _Tmp(unittest.TestCase):
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

    def cached(self, llm, name="c.sqlite"):
        c = CachedLLM(llm, path=self.root / name, enabled=True)
        self.caches.append(c)
        return c


# ---------------- 비율 예산 · v2 세트 ----------------

class RatioBudgetTest(unittest.TestCase):
    def test_parse_and_expand(self):
        self.assertEqual(parse_budget_list("2000, r=0.25,r=.5"), [2000, "r=0.25", "r=0.5"])
        self.assertEqual(parse_budget_list("r=0.25,0.5,0.75"), ["r=0.25", "r=0.5", "r=0.75"])   # 지시 표기
        self.assertEqual(parse_budget_list("r=0.5,4000"), ["r=0.5", 4000])
        with self.assertRaises(KeyError):
            parse_budget_list("0.5")                     # r= 없이 시작하는 소수는 모호하므로 거부
        self.assertEqual(expand_budgets(["window_budget", "none"], [2000, "r=0.5"]),
                         ["window_budget(2000)", "window_budget(r=0.5)", "none"])
        self.assertEqual(budget_of("rolling_summary(r=0.75)[sre=none]"), "r=0.75")
        self.assertEqual(budget_of("window_budget(2000)"), 2000)
        for bad in ("window_budget(r=0)", "window_budget(r=1.5)", "window_budget(r=x)"):
            with self.assertRaises((KeyError, ValueError)):
                get_history_compressor(bad)

    def test_window_budget_ratio_uses_raw_history(self):
        h = history(4)
        raw = history_tokens(h[1:], fake_count_tokens)
        r = get_history_compressor("window_budget(r=0.5)", token_counter=fake_count_tokens).compress_history(h, "Q")
        self.assertEqual(r.info["history_budget"], round(raw * 0.5))
        self.assertEqual(r.info["history_budget_ratio"], 0.5)
        self.assertLessEqual(r.info["history_tokens"], r.info["history_budget"])
        self.assertEqual(r.info["turns_kept"], 2)

    def test_ratio_in_chain_is_relative_to_original(self):
        """체인 안에서도 앞 단계(per_message(rule))가 줄이기 전의 원본 기록 기준."""
        h = [SYS]
        for i in range(4):
            h += [{"role": "user", "content": doc_user(f"p{i}.md", "**bold** [link](http://x) " * 40, f"q{i}")},
                  {"role": "assistant", "content": f"a{i}"}]
        raw = history_tokens(h[1:], fake_count_tokens)
        c = get_history_compressor("per_message(rule)>window_budget(r=0.5)", token_counter=fake_count_tokens)
        r = c.compress_history(h, "Q")
        stage = r.info["2:window_budget(r=0.5)"]
        self.assertEqual(stage["history_budget"], round(raw * 0.5))

    def test_rolling_summary_ratio(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        from multiturn.history_compressors import Summarizer
        summ = Summarizer(CachedLLM(FakeSummaryLLM(), path=Path(tmp.name) / "s.sqlite", enabled=True))
        self.addCleanup(summ.cached.close)
        c = get_history_compressor("rolling_summary(r=0.3)", token_counter=fake_count_tokens, summarizer=summ)
        state = c.initial_state(0)
        h = history(4)
        r = c.compress_history(h, "Q", None, state)
        self.assertEqual(r.info["history_budget"], round(history_tokens(h[1:], fake_count_tokens) * 0.3))
        self.assertGreaterEqual(r.info["summary_calls"], 1)
        self.assertTrue(r.messages[1]["content"].startswith("<conversation_summary"))

    def test_replay_config_accepts_ratio_and_v2_set(self):
        cfg = make_cfg(compressors=["v2"], history_budgets=[2000, "r=0.5"], summary_model="gpt-6-luna",
                       summary_reasoning_effort="none", summary_max_tokens=1000, presummary_model="fake",
                       notes_model="gpt-6-luna", notes_reasoning_effort="server_default", notes_max_tokens=1000)
        self.assertIn("window_budget(r=0.5)", cfg.compressors)
        self.assertIn("rolling_summary(r=0.5)[sre=none]", cfg.compressors)
        for bad in ("window(", "frozen_summary", "on_arrival(llmlingua2)"):
            self.assertFalse(any(c.startswith(bad) for c in cfg.compressors), bad)
        for want in ("presummary", "fact_notes", "per_message(rule)", "per_message(llmlingua2)", "on_arrival(rule)",
                     "query_select(2000)"):
            self.assertIn(want, cfg.compressors)
        with self.assertRaises(ValueError):
            make_cfg(history_budgets=["r=2"])

    def test_v2_set_contents(self):
        self.assertEqual(expand_sets(["v2"]), COMPRESSOR_SETS["v2"])
        self.assertEqual(len(COMPRESSOR_SETS["v2"]), 9)

    def test_required_args(self):
        with self.assertRaises(ValueError):
            make_cfg(compressors=["none", "presummary"])
        with self.assertRaises(ValueError):
            make_cfg(compressors=["none", "fact_notes"], notes_model="m")
        with self.assertRaises(ValueError):
            make_cfg(cost_mode="sim")


# ---------------- presummary ----------------

class PresummaryTest(_Tmp):
    def _hist(self):
        h = [SYS]
        for i, page in enumerate(["a.md", "b.md", "a.md"]):
            h += [{"role": "user", "content": doc_user(page, f"ORIGINAL {page} body " * 20, f"q{i}")},
                  {"role": "assistant", "content": f"answer {i}"}]
        h += [{"role": "user", "content": "Question: no docs\n\nAnswer format: f"}, {"role": "assistant", "content": "a3"}]
        return h

    def test_replaces_older_docs_only(self):
        store = write_store(self.root / "ps", {"a.md": "SUMMARY A", "b.md": "SUMMARY B"})
        c = get_history_compressor("presummary", token_counter=fake_count_tokens, presummary_store=store, keep_recent=2)
        cur = doc_user("b.md", "CURRENT body", "now")
        r = c.compress_history(self._hist(), cur)
        msgs = r.messages
        self.assertEqual(msgs[0], SYS)
        self.assertEqual(msgs[-1]["content"], cur)                           # 현재 턴 원문
        self.assertIn("SUMMARY A", msgs[1]["content"])
        self.assertNotIn("ORIGINAL a.md", msgs[1]["content"])
        self.assertIn("Question: q0", msgs[1]["content"])                     # 질문 그대로
        self.assertIn("<documentation>", msgs[1]["content"])
        self.assertIn("## Document: a.md", msgs[1]["content"])
        self.assertEqual(msgs[2]["content"], "answer 0")                      # 답변 그대로
        self.assertIn("SUMMARY B", msgs[3]["content"])
        self.assertIn("ORIGINAL a.md", msgs[5]["content"])                   # 직전 keep_recent=2 턴은 원문
        self.assertEqual((r.llm_prompt_tokens, r.llm_completion_tokens), (0, 0))
        self.assertEqual(r.info["pages_replaced"], ["a.md", "b.md"])

    def test_missing_summary_stops(self):
        store = write_store(self.root / "ps", {"a.md": "SUMMARY A"})
        c = get_history_compressor("presummary", presummary_store=store, keep_recent=1)
        with self.assertRaises(MissingPresummaryError):
            c.compress_history(self._hist(), "Q")
        with self.assertRaises(MissingPresummaryError):
            PresummaryStore(self.root / "nothing")
        with self.assertRaises(ValueError):
            get_history_compressor("presummary")

    def test_build_script(self):
        llm = FakePresumLLM()
        prompt = load_section_prompt("presummary", "v1")
        out = self.root / "build"
        out.mkdir()
        (out / "b.md").write_text("EXISTING", encoding="utf-8")
        r = bp.build(["a.md", "b.md"], FakeCorpus(), self.cached(llm), prompt, out, 0.25, log=lambda *_: None)
        self.assertEqual((r["built"], r["skipped"]), (["a.md"], ["b.md"]))
        self.assertEqual(len(llm.calls), 1)
        sent = llm.calls[0][-1]["content"]
        src = bp.count_tokens(FakeCorpus.PAGES["a.md"])
        self.assertIn(f"about {round(src * 0.25)} tokens", sent)              # 목표 길이가 프롬프트에
        self.assertIn("Alpha value is 42", (out / "a.md").read_text(encoding="utf-8"))
        rec = json.loads((out / "_build_log.jsonl").read_text(encoding="utf-8").splitlines()[0])
        for k in ("source_tokens", "target_tokens", "summary_tokens", "ratio", "over_2x_target", "usd", "prompt_tokens"):
            self.assertIn(k, rec)
        self.assertEqual(rec["source_tokens"], src)
        rep = bp.build_report(out)
        self.assertEqual(rep["pages"], 1)
        # 다시 돌리면 둘 다 건너뛴다
        r = bp.build(["a.md", "b.md"], FakeCorpus(), self.cached(llm), prompt, out, 0.25, log=lambda *_: None)
        self.assertEqual(r["built"], [])
        # 설정이 다른 폴더에 이어 쓰면 멈춘다
        m = bp.manifest_for(prompt, "m", "none", 100, 0.25, "server_default")
        bp.check_manifest(out, m)
        with self.assertRaises(SystemExit):
            bp.check_manifest(out, bp.manifest_for(prompt, "m", "none", 100, 0.5, "server_default"))

    def test_build_requires_settings(self):
        for missing in ("--model", "--reasoning-effort", "--max-tokens"):
            args = ["--pages", "a.md", "--model", "m", "--reasoning-effort", "none", "--max-tokens", "10"]
            i = args.index(missing)
            del args[i:i + 2]
            with self.assertRaises(SystemExit):
                bp.build_parser().parse_args(args)


# ---------------- fact_notes ----------------

LATER_SECRETS = ("Recall alpha?", "Sum again?", "f1", "f2")


class FactNotesTest(_Tmp):
    def extractor(self, llm=None, ratio=0.25):
        llm = llm or FakeNotesLLM()
        return NotesExtractor(self.cached(llm, "notes.sqlite"), target_ratio=ratio, token_counter=fake_count_tokens), llm

    def test_extract_signature_has_no_leak_inputs(self):
        params = list(inspect.signature(NotesExtractor.extract).parameters)
        self.assertEqual(params, ["self", "turn", "documentation", "question", "answer", "sample_idx"])
        for banned in ("key_facts", "key_entities", "reference", "later", "scenario", "turns"):
            self.assertNotIn(banned, params)

    def test_replaces_older_doc_blocks(self):
        ex, llm = self.extractor()
        c = get_history_compressor("fact_notes", notes_extractor=ex, keep_recent=1)
        h = [SYS,
             {"role": "user", "content": doc_user("a.md", "Alpha value is 42.\n" + "filler\n" * 50, "q0")},
             {"role": "assistant", "content": "42"},
             {"role": "user", "content": "Question: no docs here\n\nAnswer format: f"},
             {"role": "assistant", "content": "ok"},
             {"role": "user", "content": doc_user("b.md", "Beta value is 7.", "q2")},
             {"role": "assistant", "content": "7"}]
        r = c.compress_history(h, "Question: now", None, {"sample_idx": 0})
        m = r.messages
        self.assertIn("- (turn 0) Alpha value is 42.", m[1]["content"])
        self.assertNotIn("filler", m[1]["content"])
        self.assertIn("Question: q0", m[1]["content"])                       # 질문 그대로
        self.assertEqual(m[2]["content"], "42")
        self.assertEqual(m[3]["content"], h[3]["content"])                   # 문서 없는 턴은 그대로
        self.assertEqual(m[5]["content"], h[5]["content"])                   # 직전 턴 원문
        self.assertEqual(r.info["notes_turns_replaced"], [0])
        self.assertEqual(len(llm.calls), 1)                                  # 문서 없는 턴은 메모 호출 없음
        # 같은 턴·같은 sample 이면 메모 재사용, sample 이 다르면 새로 부른다
        c.compress_history(h, "Question: other", None, {"sample_idx": 0})
        self.assertEqual(len(llm.calls), 1)
        c.compress_history(h, "Question: other", None, {"sample_idx": 1})
        self.assertEqual(len(llm.calls), 2)
        # 목표 길이 = 문서 토큰 × 비율
        doc = re.search(r"<documentation>\n(.*?)\n</documentation>", h[1]["content"], re.S).group(1)
        self.assertIn(f"about {max(60, round(fake_count_tokens(doc) * 0.25))} tokens", llm.calls[0][-1]["content"])

    def test_notes_failure_raises(self):
        ex, llm = self.extractor(FakeNotesLLM(fail=True))
        c = get_history_compressor("fact_notes", notes_extractor=ex)
        h = [SYS, {"role": "user", "content": doc_user("a.md", "x", "q")}, {"role": "assistant", "content": "a"},
             {"role": "user", "content": "Question: y"}, {"role": "assistant", "content": "b"}]
        with self.assertRaises(NotesFailedError):
            c.compress_history(h, "Q", None, {"sample_idx": 0})
        self.assertEqual(len(llm.calls), 3)                                  # 3번 시도, 캐시에 저장 안 함

    def test_not_in_chain(self):
        ex, _ = self.extractor()
        with self.assertRaises(ValueError):
            get_history_compressor("per_message(rule)>fact_notes", notes_extractor=ex)

    def test_replay_end_to_end_no_leak_and_attribution(self):
        notes_llm = FakeNotesLLM()
        ex, _ = self.extractor(notes_llm)
        store = write_store(self.root / "ps", {"a.md": "Alpha value is 42.", "b.md": "Beta value is 7."})
        (self.root / "ps" / "_build_log.jsonl").write_text(
            "\n".join(json.dumps({"page": pg, "prompt_tokens": 300, "completion_tokens": 100, "usd": 0.0001})
                      for pg in ("a.md", "b.md", "unused.md")), encoding="utf-8")
        cfg = make_cfg(compressors=["none", "fact_notes", "presummary"], samples=2, presummary_model="fake",
                       notes_model="gpt-6-luna", notes_reasoning_effort="server_default", notes_max_tokens=1000)
        answer = self.cached(rp.configure_answer_llm(FakeLLM(), cfg))
        judge = self.cached(FakeJudge())
        rep = rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / "mt_v2",
                        reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None,
                        presummary_store=store, notes_extractor=ex)
        summary = rep.run()
        rows = {(r["turn"], r["compressor"], r["sample_idx"]): r
                for r in map(json.loads, (self.root / "mt_v2" / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines())}
        # 메모: 문서가 있는 턴 0, 1 × sample 2 = 4번만 부른다 (이후 턴은 재사용)
        self.assertEqual(len(notes_llm.calls), 4)
        # 정보 누출 금지: 메모 요청에는 그 턴 내용만. 이후 턴 질문·key_facts 없음
        for msgs in notes_llm.calls:
            body = "\n".join(m["content"] for m in msgs)
            for secret in LATER_SECRETS:
                self.assertNotIn(secret, body)
        turn0 = [m for m in notes_llm.calls if "Turn 0" in m[-1]["content"]][0][-1]["content"]
        self.assertIn("What is alpha?", turn0)
        self.assertNotIn("What is beta?", turn0)
        # 토큰 귀속: 메모를 만든 턴(0, 1) trial 에만
        for i in range(2):
            self.assertGreater(rows[(0, "fact_notes", i)]["compress_llm_prompt_tokens"], 0)
            self.assertGreater(rows[(1, "fact_notes", i)]["compress_llm_completion_tokens"], 0)
            self.assertEqual(rows[(1, "fact_notes", i)]["compress_llm_reasoning_tokens"], 25)
            for k in (2, 3, 4, 5):
                self.assertEqual(rows[(k, "fact_notes", i)]["compress_llm_prompt_tokens"], 0)
            self.assertIsNotNone(rows[(0, "fact_notes", i)]["notes_made"]["ratio"])
            for k in range(6):
                self.assertEqual(rows[(k, "presummary", i)]["compress_llm_prompt_tokens"], 0)
        # 메모·요약에 'Alpha value is 42' 가 남아 recall 턴도 맞힌다
        self.assertEqual(rows[(2, "fact_notes", 1)]["answer_accuracy"], 1.0)
        self.assertEqual(rows[(2, "presummary", 1)]["answer_accuracy"], 1.0)
        # 총 토큰 절감률에 메모 토큰이 들어간다
        blk = summary["compressors"]["fact_notes"]["all"]
        self.assertEqual(blk["tokens"]["compressed"]["compress"],
                         sum(r["compress_llm_prompt_tokens"] + r["compress_llm_completion_tokens"]
                             for r in rows.values() if r["compressor"] == "fact_notes"))
        self.assertGreater(blk["compress_token_share_pct"], 0)
        self.assertIn("fact_notes", summary["fact_notes_compression"])
        self.assertEqual(summary["fact_notes_compression"]["fact_notes"]["notes"], 4)
        self.assertIn("presummary_build", summary)
        # presummary 총 토큰 절감률: 구축 토큰 제외·포함 두 값 (이 run 이 쓰는 페이지 a, b 의 구축 토큰만)
        pb = summary["compressors"]["presummary"]["all"]
        self.assertEqual(pb["presummary_build_tokens"], 800)
        self.assertEqual(pb["total_token_reduction_pct_without_build"], pb["total_token_reduction_pct"])
        base, comp = pb["tokens"]["none"]["total"], pb["tokens"]["compressed"]["total"]
        self.assertAlmostEqual(pb["total_token_reduction_pct_with_build"], round(100 * (base - comp - 800) / base, 2))
        row = summary["budget_table"]["no_budget"]["presummary"]
        self.assertEqual(row["total_token_reduction_pct_with_build"], pb["total_token_reduction_pct_with_build"])
        self.assertNotIn("total_token_reduction_pct_with_build", summary["compressors"]["fact_notes"]["all"])
        self.assertNotIn("total_token_reduction_pct_with_build",
                         summary["compressors"]["presummary"]["depends_on_reference_ok"])
        self.assertTrue(any("상한" in n for n in summary["notes"]))
        # replay 의 기록 메시지: 턴 2 의 턴 0 문서는 메모로, 턴 1(직전) 은 원문
        steps = [json.loads(l) for l in (self.root / "mt_v2" / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()]
        st = next(s for s in steps if s["compressor"] == "fact_notes" and s["turn"] == 2 and s["sample_idx"] == 0)
        sent = st["messages_sent"]
        self.assertIn("Fact notes from turn 0", sent[1]["content"])
        self.assertIn("filler line", sent[3]["content"])

    def test_estimate_uses_placeholder_for_missing_pages(self):
        from multiturn.estimate import PlaceholderPresummaryStore, estimate
        store = write_store(self.root / "ps_partial", {"a.md": "Alpha value is 42."})     # b.md 요약 없음
        ph = PlaceholderPresummaryStore(FakeCorpus(), real=store)
        self.assertEqual(ph.get("a.md"), "Alpha value is 42.")
        self.assertTrue(ph.get("b.md").startswith("summary"))
        cfg = make_cfg(compressors=["none", "presummary"], samples=1, presummary_model="fake")
        est = estimate(cfg, [SCENARIO], FakeCorpus(), judge_model="deepseek-flash", presummary_store=store)
        self.assertEqual(est["presummary_placeholder_pages"], ["b.md"])

    def test_estimate_counts_notes_calls(self):
        from multiturn.estimate import estimate
        cfg = make_cfg(compressors=["none", "fact_notes", "presummary"], samples=2, presummary_model="fake",
                       notes_model="gpt-6-luna", notes_reasoning_effort="server_default", notes_max_tokens=1000)
        est = estimate(cfg, [SCENARIO], FakeCorpus(), judge_model="deepseek-flash")
        self.assertEqual(est["compressors"]["fact_notes"]["summary_calls"], 4)       # 문서 턴 2 × sample 2
        self.assertEqual(est["compressors"]["presummary"]["summary_calls"], 0)
        self.assertGreater(est["compressors"]["presummary"]["input_reduction_pct_vs_none"], 0)


# ---------------- 토큰 기준 summary ----------------

class TokenSummaryTest(_Tmp):
    def _run(self, **kw):
        cfg = make_cfg(compressors=["none", "window(1)"], **kw)
        answer = self.cached(rp.configure_answer_llm(FakeLLM(), cfg))
        judge = self.cached(FakeJudge())
        return rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / f"mt_{kw.get('cost_mode', 'd')}",
                         reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None).run()

    def test_default_has_no_cache_metrics(self):
        s = self._run()
        self.assertEqual(s["cost_mode"], "none")
        self.assertNotIn("cache_by_compressor", s)
        blk = s["compressors"]["window(1)"]["all"]
        for k in rp.CACHE_BLOCK_KEYS:
            self.assertNotIn(k, blk)
        for k in ("input_reduction_pct", "total_token_reduction_pct", "retention_pct", "non_inferiority",
                  "non_inferiority_cluster", "tokens", "reasoning_reduction_pct", "accuracy_breakdown"):
            self.assertIn(k, blk)
        t = blk["tokens"]["compressed"]
        self.assertEqual(t["total"], t["input"] + t["output"] + t["compress"])
        self.assertEqual(t["output_visible"] + t["reasoning"], t["output"])
        row = s["budget_table"]["no_budget"]["window(1)"]
        self.assertNotIn("cost_reduction_pct_sim", row)
        self.assertNotIn("prefix_share_mean", row)
        self.assertIn("total_token_reduction_pct", row)
        ab = blk["accuracy_breakdown"]
        self.assertEqual(set(ab["by_turn_type"]), {"new", "recall", "synthesis"})
        self.assertEqual(set(ab["by_recall_distance"]), {"2"})              # 턴 2→0, 3→1
        self.assertIn("recall", s["accuracy_by_turn_type"]["none"])
        self.assertEqual(s["accuracy_by_recall_distance"]["window(1)"]["2"], 0.0)
        self.assertFalse(any("cached_tokens" in n for n in s["notes"]))

    def test_cache_mode_keeps_old_metrics(self):
        s = self._run(cost_mode="cache")
        self.assertIn("cache_by_compressor", s)
        self.assertIn("cost_reduction_pct_sim", s["compressors"]["window(1)"]["all"])
        self.assertIn("prefix_share_mean", s["budget_table"]["no_budget"]["window(1)"])

    def test_breakdown_uses_turn_types_as_given(self):
        def row(tt, d, acc):
            return {"scenario_id": "s", "turn": d, "turn_type": tt, "depends_distance_max": d, "answer_accuracy": acc}
        pairs = [(row("update", 1, 1.0), row("update", 1, 0.5)),
                 (row("same_doc_new_topic", None, 1.0), row("same_doc_new_topic", None, 1.0)),
                 (row("recall", 4, 1.0), row("recall", 4, 0.0))]
        ab = rp.accuracy_breakdown(pairs)
        self.assertEqual(set(ab["by_turn_type"]), {"update", "same_doc_new_topic", "recall"})
        self.assertEqual(ab["by_turn_type"]["update"]["retention_pct"], 50.0)
        self.assertEqual(set(ab["by_recall_distance"]), {"4"})
        self.assertEqual(set(ab["by_dependency_distance"]), {"1", "4"})

    def test_budget_table_ratio_keys(self):
        blocks = {"window_budget(r=0.5)": {"all": {"n_pairs": 1}}, "window_budget(2000)": {"all": {"n_pairs": 1}},
                  "presummary": {"all": {"n_pairs": 1}}}
        t = rp.budget_table(blocks, make_cfg())
        self.assertEqual(list(t), ["2000", "r=0.5", "no_budget"])
        self.assertIn("window_budget", t["r=0.5"])


if __name__ == "__main__":
    unittest.main()
