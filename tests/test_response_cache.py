"""
multiturn/response_cache.py: 키 구성, 적중 시 원래 토큰 그대로, RESPONSE_CACHE=off (가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_response_cache
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm import LLMResult  # noqa: E402
from multiturn.response_cache import CachedLLM, cache_enabled, cache_key  # noqa: E402

MSGS = [{"role": "user", "content": "hello"}]


class FakeLLM:
    def __init__(self, model="gpt-6.1-sol", backend="openai", base_url="https://api.openai.com",
                 temperature=0.0, effort=""):
        self.model, self.backend, self.base_url = model, backend, base_url
        self.temperature, self.reasoning_effort = temperature, effort
        self.calls = 0
        self.unsupported: set[str] = set()

    def sampling_info(self):
        return {"model": self.model,
                "temperature": None if "temperature" in self.unsupported else self.temperature,
                "temperature_requested": self.temperature, "seed": 42,
                "reasoning_effort": self.reasoning_effort or None,
                "reasoning_effort_requested": self.reasoning_effort or None,
                "max_tokens": None, "max_tokens_param": "max_tokens"}

    def chat(self, messages, stream_ttft=False):
        self.calls += 1
        self.unsupported.add("temperature")        # 첫 호출 뒤 실제 전송값이 바뀌는 상황
        return LLMResult(text=f"answer {self.calls}", prompt_tokens=1500, completion_tokens=40, latency=1.0,
                         model=self.model, cached_tokens=1024, reasoning_tokens=30,
                         raw_usage={"prompt_tokens": 1500}, created_at="2026-11-22T00:00:00+00:00")


class KeyTest(unittest.TestCase):
    def test_key_components(self):
        base = cache_key(FakeLLM(), MSGS, 0)
        self.assertNotEqual(base, cache_key(FakeLLM(), MSGS, 1))                          # sample_idx
        self.assertNotEqual(base, cache_key(FakeLLM(base_url="https://other"), MSGS, 0))  # base_url
        self.assertNotEqual(base, cache_key(FakeLLM(backend="ollama"), MSGS, 0))          # backend
        self.assertNotEqual(base, cache_key(FakeLLM(model="x"), MSGS, 0))                 # model
        self.assertNotEqual(base, cache_key(FakeLLM(effort="low"), MSGS, 0))              # reasoning_effort
        self.assertNotEqual(base, cache_key(FakeLLM(temperature=1.0), MSGS, 0))           # sampling
        self.assertNotEqual(base, cache_key(FakeLLM(), [{"role": "user", "content": "hi"}], 0))

    def test_key_uses_requested_not_sent(self):
        llm = FakeLLM()
        before = cache_key(llm, MSGS, 0)
        llm.unsupported.add("temperature")
        self.assertEqual(before, cache_key(llm, MSGS, 0))


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cache" / "responses.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_hit_returns_original_tokens(self):
        llm = FakeLLM()
        c = CachedLLM(llm, path=self.path, enabled=True)
        r1, h1 = c.chat(MSGS, sample_idx=0)
        r2, h2 = c.chat(MSGS, sample_idx=0)
        c.close()
        self.assertEqual((h1, h2), (False, True))
        self.assertEqual(llm.calls, 1)
        self.assertEqual(r1, r2)                       # 토큰·created_at 등 원래 값 그대로
        self.assertEqual(r2.cached_tokens, 1024)

        # 새 프로세스(새 LLM 객체)에서도 디스크에서 적중
        llm2 = FakeLLM()
        c2 = CachedLLM(llm2, path=self.path, enabled=True)
        _, h3 = c2.chat(MSGS, sample_idx=0)
        _, h4 = c2.chat(MSGS, sample_idx=1)            # 다른 반복은 새로 호출
        c2.close()
        self.assertEqual((h3, h4, llm2.calls), (True, False, 1))

    def test_sample_idx_required(self):
        c = CachedLLM(FakeLLM(), path=self.path, enabled=True)
        with self.assertRaises(TypeError):
            c.chat(MSGS)                               # noqa
        with self.assertRaises(TypeError):
            c.chat(MSGS, sample_idx=None)
        c.close()

    def test_disabled(self):
        llm = FakeLLM()
        c = CachedLLM(llm, path=self.path, enabled=False)
        self.assertEqual([c.chat(MSGS, sample_idx=0)[1] for _ in range(2)], [False, False])
        self.assertEqual(llm.calls, 2)
        self.assertFalse(self.path.exists())

    def test_env_switch(self):
        with mock.patch.dict(os.environ, {"RESPONSE_CACHE": "off"}):
            self.assertFalse(cache_enabled())
            self.assertFalse(CachedLLM(FakeLLM(), path=self.path).enabled)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESPONSE_CACHE", None)
            self.assertTrue(cache_enabled())

    def test_passthrough_attrs(self):
        self.assertEqual(CachedLLM(FakeLLM(), path=self.path).model, "gpt-6.1-sol")


if __name__ == "__main__":
    unittest.main()
