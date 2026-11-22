"""
llm.parse_usage_details: 제공사별 usage 의 캐시·추론 토큰 파싱 (가짜 usage dict, 네트워크 없음).

    python -m unittest tests.test_usage_details
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm  # noqa: E402
from llm import LLM, parse_usage_details  # noqa: E402

OPENAI_USAGE = {
    "prompt_tokens": 2006, "completion_tokens": 300, "total_tokens": 2306,
    "prompt_tokens_details": {"cached_tokens": 1920, "audio_tokens": 0},
    "completion_tokens_details": {"reasoning_tokens": 256, "audio_tokens": 0},
}
DEEPSEEK_USAGE = {
    "prompt_tokens": 2000, "completion_tokens": 120, "total_tokens": 2120,
    "prompt_cache_hit_tokens": 1792, "prompt_cache_miss_tokens": 208,
    "completion_tokens_details": {"reasoning_tokens": 80},
}


class ParseTest(unittest.TestCase):
    def test_openai(self):
        d = parse_usage_details(OPENAI_USAGE)
        self.assertEqual(d["cached_tokens"], 1920)
        self.assertEqual(d["reasoning_tokens"], 256)
        self.assertIsNone(d["cache_write_tokens"])     # chat completions 에 없으면 None
        self.assertEqual(d["raw_usage"], OPENAI_USAGE)

    def test_deepseek_miss_is_not_cache_write(self):
        d = parse_usage_details(DEEPSEEK_USAGE)
        self.assertEqual(d["cached_tokens"], 1792)
        self.assertEqual(d["reasoning_tokens"], 80)
        self.assertIsNone(d["cache_write_tokens"])

    def test_cache_write_candidate(self):
        u = {"prompt_tokens": 10, "completion_tokens": 1,
             "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 9}}
        d = parse_usage_details(u)
        self.assertEqual(d["cached_tokens"], 0)         # 0 은 0 그대로 (None 과 구분)
        self.assertEqual(d["cache_write_tokens"], 9)

    def test_missing_is_none_not_zero(self):
        for u in (None, {}, {"prompt_tokens": 5, "completion_tokens": 1},
                  {"prompt_tokens_details": None, "completion_tokens_details": {"reasoning_tokens": None}}):
            d = parse_usage_details(u)
            self.assertIsNone(d["cached_tokens"])
            self.assertIsNone(d["cache_write_tokens"])
            self.assertIsNone(d["reasoning_tokens"])
        self.assertIsNone(parse_usage_details(None)["raw_usage"])

    def test_responses_api_shape(self):
        u = {"input_tokens": 100, "output_tokens": 20,
             "input_tokens_details": {"cached_tokens": 64, "cache_write_tokens": 30},
             "output_tokens_details": {"reasoning_tokens": 12}}
        d = parse_usage_details(u)
        self.assertEqual((d["cached_tokens"], d["cache_write_tokens"], d["reasoning_tokens"]), (64, 30, 12))


class _Resp:
    ok = True
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class OpenAIChatTest(unittest.TestCase):
    """_openai_chat 이 usage 세부와 추론 원문을 LLMResult 에 담는지 (요청은 mock)."""

    def _llm(self):
        return LLM(backend="openai", base_url="http://x", api_key="", model="m", role="answer")

    def test_non_stream_deepseek(self):
        body = {"model": "deepseek-flash", "usage": DEEPSEEK_USAGE,
                "choices": [{"message": {"content": "YES", "reasoning_content": "think..."},
                             "finish_reason": "stop"}]}
        with mock.patch.object(llm.requests, "post", return_value=_Resp(body)):
            res = self._llm()._openai_chat([{"role": "user", "content": "hi"}], stream_ttft=False)
        self.assertEqual(res.text, "YES")
        self.assertEqual(res.reasoning_text, "think...")
        self.assertEqual(res.cached_tokens, 1792)
        self.assertEqual(res.reasoning_tokens, 80)
        self.assertEqual(res.raw_usage["prompt_cache_miss_tokens"], 208)
        self.assertTrue(res.created_at.endswith("+00:00"))

    def test_non_stream_openai_no_reasoning_text(self):
        body = {"model": "gpt-6.1-sol", "usage": OPENAI_USAGE,
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]}
        with mock.patch.object(llm.requests, "post", return_value=_Resp(body)):
            res = self._llm()._openai_chat([{"role": "user", "content": "hi"}], stream_ttft=False)
        self.assertIsNone(res.reasoning_text)
        self.assertEqual(res.cached_tokens, 1920)


if __name__ == "__main__":
    unittest.main()
