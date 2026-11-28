"""
query_select_hybrid (BM25 + 임베딩): 정보 누출 없음, 예산 준수, 같은 입력이면 같은 결과, 임베딩 캐시
(가짜 임베더, 네트워크 없음).

    python -m unittest tests.test_mt_hybrid
"""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from multiturn import replay as rp  # noqa: E402
from multiturn.history_compressors import OllamaEmbedder, get_history_compressor, select_hybrid  # noqa: E402
from multiturn.history_compressors.budget import history_tokens  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_replay import PATCHES, SCENARIO, FakeCorpus, FakeJudge, FakeLLM, fake_grade, make_cfg  # noqa: E402
from test_mt_summary_budget import SYS, doc_turn  # noqa: E402


def count(t):
    return len(t.split())


class KeywordEmbedder:
    """단어 집합 기반 가짜 임베딩: 'tokenUrl'·'jwt' 같은 단어가 겹치면 코사인이 크다. 호출한 텍스트를 기록한다."""

    VOCAB = ["token", "tokenurl", "jwt", "cookie", "header", "cors", "database", "secret", "expire", "login"]

    def __init__(self):
        self.seen: list[str] = []

    def embed_many(self, texts):
        self.seen += texts
        out = []
        for t in texts:
            w = t.lower()
            v = [float(w.count(x)) for x in self.VOCAB] + [0.1]
            n = sum(x * x for x in v) ** 0.5
            out.append([x / n for x in v])
        return out

    def config(self):
        return {"fake": True}


def past_history():
    h = [SYS]
    h += doc_turn(0, "The JWT secret signs tokens. Tokens expire after 30 minutes. " + "Filler words. " * 30, "jwt answer")
    h += doc_turn(1, "CORS allows origins. Cookie headers carry sessions. " + "Other padding. " * 30, "cors answer")
    h += doc_turn(2, "Database sessions close after requests. " + "More padding text. " * 30, "db answer")
    return h


class HybridSelectTest(unittest.TestCase):
    def test_signature_has_no_answer_inputs(self):
        params = set(inspect.signature(select_hybrid).parameters)
        self.assertEqual(params, {"question", "past", "budget", "token_counter", "embedder", "keep_recent", "w_bm25"})

    def test_budget_respected_and_recent_kept(self):
        past = past_history()
        emb = KeywordEmbedder()
        for budget in (40, 80, 150, 400):
            msgs, info = select_hybrid("When does the jwt token expire?", past[1:], budget, count, emb)
            recent = past[-2:]
            self.assertEqual(msgs[-2:], recent)                      # 최근 1턴 원문
            selected = msgs[:-2]
            used = history_tokens(msgs, count)
            if selected:
                self.assertLessEqual(used, max(budget, history_tokens(recent, count)))
                self.assertIn("<selected_history>", selected[0]["content"])

    def test_prefers_relevant_and_keeps_order(self):
        past = past_history()
        recent = history_tokens(past[-2:], count)
        msgs, _ = select_hybrid("When does the jwt token expire?", past[1:], recent + 25, count, KeywordEmbedder())
        self.assertEqual(len(msgs), 3)                       # <selected_history> + 최근 1턴
        sel = msgs[0]["content"]
        self.assertIn("expire after 30 minutes", sel)
        self.assertNotIn("Database sessions", sel)
        # 원래 순서: 턴 0 조각이 턴 1 조각보다 앞
        if "turn 1" in sel:
            self.assertLess(sel.index("turn 0"), sel.index("turn 1"))

    def test_deterministic(self):
        past = past_history()
        a = select_hybrid("cookie header cors", past[1:], 80, count, KeywordEmbedder())
        b = select_hybrid("cookie header cors", past[1:], 80, count, KeywordEmbedder())
        self.assertEqual(a, b)

    def test_only_current_question_is_query(self):
        """임베딩에 보내는 질의는 현재 질문뿐이다 (직전 질문·정답·key_facts 를 붙이지 않는다)."""
        emb = KeywordEmbedder()
        comp = get_history_compressor("query_select_hybrid(80)", token_counter=count, embedder=emb)
        past = past_history()
        current = "<documentation>\n## Document: x.md\n\nnew doc\n</documentation>\n\nQuestion: How long do tokens live?\n\nAnswer format: f"
        comp.compress_history(past + [{"role": "user", "content": current}], current)
        self.assertEqual(emb.seen[-1], "How long do tokens live?")
        self.assertNotIn("question 2", emb.seen[-1])

    def test_weights(self):
        past = past_history()
        bm_only, _ = select_hybrid("jwt", past[1:], 40, count, KeywordEmbedder(), w_bm25=1.0)
        emb_only, _ = select_hybrid("jwt", past[1:], 40, count, KeywordEmbedder(), w_bm25=0.0)
        self.assertTrue(bm_only and emb_only)
        with self.assertRaises(ValueError):
            get_history_compressor("query_select_hybrid(80)", token_counter=count, embedder=KeywordEmbedder(),
                                   hybrid_bm25_weight=1.5)

    def test_ratio_budget_name(self):
        comp = get_history_compressor("query_select_hybrid(r=0.5)", token_counter=count, embedder=KeywordEmbedder())
        self.assertEqual((comp.ratio, comp.config()["bm25_weight"]), (0.5, 0.5))


class EmbedderCacheTest(unittest.TestCase):
    def test_same_text_embedded_once_and_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def fake_request(self, texts):
                calls.append(list(texts))
                return [[float(len(t)), 1.0] for t in texts]

            with mock.patch.object(OllamaEmbedder, "_request", fake_request):
                e = OllamaEmbedder(base_url="http://x", model="bge-m3", cache_path=Path(d) / "e.sqlite")
                v1 = e.embed_many(["a", "bb", "a"])
                v2 = e.embed_many(["bb", "ccc"])
                self.assertEqual(calls, [["a", "bb"], ["ccc"]])        # 같은 텍스트는 한 번만
                self.assertEqual(v1[0], v1[2])
                self.assertAlmostEqual(sum(x * x for x in v2[1]), 1.0)  # 단위 벡터
                e2 = OllamaEmbedder(base_url="http://x", model="bge-m3", cache_path=Path(d) / "e.sqlite")
                e2.embed_many(["a", "ccc"])                            # 디스크 캐시 (--resume)
                self.assertEqual(len(calls), 2)
                self.assertEqual(e2.stats["disk_hits"], 2)
                e._db_conn.close()
                e2._db_conn.close()


class ReplayHybridTest(unittest.TestCase):
    def setUp(self):
        for p in PATCHES:
            p.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        for p in reversed(PATCHES):
            p.stop()
        self.tmp.cleanup()

    def test_replay_runs_and_records(self):
        cfg = make_cfg(compressors=["none", "query_select_hybrid(r=0.5)"], hybrid_bm25_weight=0.5)
        answer = CachedLLM(rp.configure_answer_llm(FakeLLM(), cfg), path=self.root / "c.sqlite", enabled=True)
        judge = CachedLLM(FakeJudge(), path=self.root / "c.sqlite", enabled=True)
        emb = KeywordEmbedder()
        try:
            summary = rp.Replay(cfg, [SCENARIO], FakeCorpus(), answer, judge, self.root / "run",
                                reference_root=self.root / "refs", grade_fn=fake_grade, sleep=lambda s: None,
                                embedder=emb).run()
        finally:
            answer.close()
            judge.close()
        self.assertIn("query_select_hybrid(r=0.5)", summary["compressors"])
        self.assertEqual(summary["config"]["embedder"], {"fake": True})
        rows = [json.loads(l) for l in (self.root / "run" / "turn_trials.jsonl").read_text(encoding="utf-8").splitlines()]
        hy = [r for r in rows if r["compressor"] == "query_select_hybrid(r=0.5)"]
        self.assertEqual(len(hy), 12)
        for q in emb.seen:                                   # 정답·key_facts 가 임베딩 입력에 없다
            self.assertNotIn("f1", q.split())
        self.assertIn("r=0.5", summary["budget_table"])
        self.assertIn("query_select_hybrid", summary["budget_table"]["r=0.5"])


if __name__ == "__main__":
    unittest.main()
