"""
experiment --resume (중단된 run 이어서 실행) 과 네트워크 재시도 테스트.

답변·채점 호출은 mock 이고 평가셋은 data/evalsets/claude-v1 의 dev 앞 2문항을 쓴다 (네트워크 호출 없음).

    python -m unittest discover -s tests
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import experiment as E  # noqa: E402
import llm  # noqa: E402
from config import CFG  # noqa: E402
from llm import LLM, LLMResult  # noqa: E402


def fake_result(self, text):
    return LLMResult(text=text, prompt_tokens=10, completion_tokens=2, latency=0.0, ttft=0.0,
                     model=self.model, finish_reason="stop")


def args(**kw):
    a = dict(compressors="none,rule", split="dev", limit=2, ids=None, no_judge=False, judge_mode="per_fact",
             semantic=False, answer_prompt="v1", resume=None)
    a.update(kw)
    return argparse.Namespace(**a)


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.eval_dir = mock.patch.object(CFG, "eval_dir", ROOT / "data" / "evalsets" / "claude-v1")
        self.eval_dir.start()
        self.addCleanup(self.eval_dir.stop)
        self.out = None

    def tearDown(self):
        if self.out is not None:
            shutil.rmtree(self.out, ignore_errors=True)

    def test_interrupted_run_resumes_without_redoing_trials(self):
        answers = {"n": 0}

        def chat(self, messages, stream_ttft=False):
            if self.role == "answer":
                answers["n"] += 1
                if answers["n"] == 4:          # 워밍업 1 + trial 2개 뒤 세 번째 trial 답변에서 끊김
                    raise KeyboardInterrupt
            return fake_result(self, "YES" if self.role == "judge" else "DUMMY_HASH")

        with mock.patch.object(LLM, "chat", chat):
            with self.assertRaises(KeyboardInterrupt):
                E.run(args())
            runs = sorted((CFG.results_dir / "runs").iterdir(), key=lambda p: p.stat().st_mtime)
            self.out = runs[-1]
            first = [json.loads(l) for l in open(self.out / "trials.jsonl", encoding="utf-8")]
            self.assertEqual(len(first), 2)

            answers["n"] = 100
            E.run(args(compressors="none", resume=self.out.name))   # 인자는 args.json 의 값이 이긴다

        trials = [json.loads(l) for l in open(self.out / "trials.jsonl", encoding="utf-8")]
        self.assertEqual(sorted((t["qid"], t["compressor"]) for t in trials),
                         sorted({(t["qid"], c) for t in trials for c in ("none", "rule")}))
        self.assertEqual(len(trials), 4)
        meta = json.loads((self.out / "args.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["args"]["compressors"], len(meta["attempts"])), ("none,rule", 2))
        s = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(s["results"]["rule"]["n"], 2)


class NetworkRetryTest(unittest.TestCase):
    def test_connection_errors_wait_longer_then_succeed(self):
        l = LLM(backend="openai", base_url="http://x", api_key="", model="m", max_retries=2)
        calls = {"n": 0}

        def once(messages, stream_ttft):
            calls["n"] += 1
            if calls["n"] <= 3:
                raise llm.requests.ConnectionError("dns")
            return fake_result(l, "ok")

        with mock.patch.object(l, "_call_once", side_effect=once), \
             mock.patch.object(llm.time, "sleep") as sleep, \
             mock.patch.object(CFG, "network_retry_waits", (5, 15, 30)):
            res = l._call_with_retry([{"role": "user", "content": "hi"}], False)
        self.assertEqual((res.text, calls["n"]), ("ok", 4))
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 5, 15])


if __name__ == "__main__":
    unittest.main()
