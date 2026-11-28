"""
요약 목표 길이 상한 (Summarizer max_target, --summary-max-target): 목표 = min(예산 - 최근 원문 턴, 상한)
(가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_mt_summary_cap
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from multiturn import replay as rp  # noqa: E402
from multiturn.history_compressors import Summarizer, get_history_compressor  # noqa: E402
from multiturn.history_compressors.budget import history_tokens  # noqa: E402
from multiturn.response_cache import CachedLLM  # noqa: E402
from test_mt_summary_budget import FakeSummaryLLM, history  # noqa: E402


def count(t):
    return len(t.split())


def target_in(messages) -> int:
    return int(re.search(r"at most (\d+) tokens", messages[-1]["content"]).group(1))


class SummaryCapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.caches = []

    def tearDown(self):
        for c in self.caches:
            c.close()
        self.tmp.cleanup()

    def _summ(self, max_target):
        llm = FakeSummaryLLM()
        c = CachedLLM(llm, path=self.root / f"s{max_target}.sqlite", enabled=True)
        self.caches.append(c)
        return Summarizer(c, max_target=max_target), llm

    def _run(self, spec, max_target, n=8):
        summ, llm = self._summ(max_target)
        comp = get_history_compressor(spec, token_counter=count, summarizer=summ, keep_recent=1)
        h = history(n, filler=60)
        past, user = h[:-1], h[-1]["content"]
        res = comp.compress_history(h, "next question", None, comp.initial_state(0))
        return res, llm, h

    def test_cap_applies_when_budget_large(self):
        res, llm, h = self._run("rolling_summary(r=0.5)", 250)
        self.assertEqual(len(llm.calls), 1)
        info = res.info
        self.assertGreater(info["summary_target_requested"], 250)
        self.assertEqual((info["summary_target"], info["summary_target_capped"], info["summary_max_target"]),
                         (250, True, 250))
        self.assertEqual(target_in(llm.calls[0]), 250)              # 지시문의 목표 길이가 상한값
        # 예산을 다 쓰지 않는다 (상한 때문에): 압축 뒤 기록 <= 예산
        self.assertLessEqual(history_tokens(res.messages[1:-1], count), info["history_budget"])

    def test_no_cap_when_target_small(self):
        res, llm, _ = self._run("rolling_summary(r=0.5)", 100000)
        self.assertEqual(res.info["summary_target"], res.info["summary_target_requested"])
        self.assertFalse(res.info["summary_target_capped"])

    def test_none_means_no_cap(self):
        res, llm, _ = self._run("rolling_summary(r=0.5)", None)
        self.assertEqual(res.info["summary_target"], res.info["summary_target_requested"])
        self.assertIsNone(res.info["summary_max_target"])

    def test_frozen_summary_also_capped(self):
        res, llm, _ = self._run("frozen_summary(r=0.5)", 250)
        self.assertEqual(res.info["summary_target"], 250)

    def test_invalid_cap(self):
        with self.assertRaises(ValueError):
            Summarizer(None, max_target=50)

    def test_cli_default_and_zero(self):
        base = ["--scenarios", "x", "--model", "gpt-6-luna", "--reasoning-effort", "server_default",
                "--max-completion-tokens", "4096", "--compressors", "none,rolling_summary(r=0.5)",
                "--summary-model", "gpt-6-luna", "--summary-reasoning-effort", "server_default",
                "--summary-max-tokens", "4096"]
        self.assertEqual(rp.config_from_args(rp.build_parser().parse_args(base)).summary_max_target, 3000)
        cfg = rp.config_from_args(rp.build_parser().parse_args(base + ["--summary-max-target", "0"]))
        self.assertIsNone(cfg.summary_max_target)

    def test_budget_use_mean(self):
        rows = [{"history_tokens_compressed": 50, "history_budget_effective": 100},
                {"history_tokens_compressed": 100, "history_budget_effective": 100},
                {"history_tokens_compressed": 10, "history_budget_effective": None}]
        self.assertEqual(rp.budget_use_mean(rows), 0.75)
        self.assertIsNone(rp.budget_use_mean([{"history_tokens_compressed": 5}]))


if __name__ == "__main__":
    unittest.main()
