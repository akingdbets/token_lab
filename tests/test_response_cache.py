"""
multiturn/response_cache.py: 키 구성, 적중 시 원래 토큰 그대로, RESPONSE_CACHE=off (가짜 LLM, 네트워크 없음).

    python -m unittest tests.test_response_cache
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
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



class SlowLLM(FakeLLM):
    """호출이 겹치도록 느린 가짜 LLM. 호출마다 다른 답을 낸다 (동시 중복 호출이면 답이 갈린다)."""

    def __init__(self, delay=0.2, **kw):
        super().__init__(**kw)
        self.delay = delay
        self._n = 0
        self._lock = threading.Lock()

    def chat(self, messages, stream_ttft=False):
        with self._lock:
            self._n += 1
            n = self._n
        time.sleep(self.delay)
        with self._lock:
            self.calls += 1
        return LLMResult(text=f"answer {n}", prompt_tokens=100, completion_tokens=10, latency=self.delay,
                         model=self.model)


class ConcurrencyTest(unittest.TestCase):
    """같은 요청을 동시에 보내면 API 는 한 번만 부르고 모두 같은 답을 받는다 (2026-11 replay 경합 재현)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _parallel(self, cached, n, fn):
        barrier = threading.Barrier(n)

        def task(i):
            barrier.wait()
            return fn(i)
        with ThreadPoolExecutor(n) as ex:
            return list(ex.map(task, range(n)))

    def test_same_key_concurrent_calls_once(self):
        llm = SlowLLM()
        cached = CachedLLM(llm, path=Path(self.tmp.name) / "c.sqlite", enabled=True)
        self.addCleanup(cached.close)
        out = self._parallel(cached, 6, lambda i: cached.chat(MSGS, sample_idx=0))
        self.assertEqual(llm.calls, 1)
        self.assertEqual({r.text for r, _ in out}, {"answer 1"})
        self.assertEqual(sorted(h for _, h in out), [False] + [True] * 5)
        self.assertEqual(cached.chat(MSGS, sample_idx=0)[0].text, "answer 1")      # 저장된 것도 첫 응답

    def test_different_keys_run_in_parallel(self):
        llm = SlowLLM(delay=0.3)
        cached = CachedLLM(llm, path=Path(self.tmp.name) / "c.sqlite", enabled=True)
        self.addCleanup(cached.close)
        t0 = time.perf_counter()
        out = self._parallel(cached, 4, lambda i: cached.chat(MSGS, sample_idx=i))
        self.assertEqual(llm.calls, 4)
        self.assertLess(time.perf_counter() - t0, 0.3 * 3)             # 키가 다르면 서로 기다리지 않는다
        self.assertEqual(len({r.text for r, _ in out}), 4)

    def test_bound_judge_path_also_deduplicated(self):
        llm = SlowLLM()
        cached = CachedLLM(llm, path=Path(self.tmp.name) / "c.sqlite", enabled=True)
        self.addCleanup(cached.close)
        judge = cached.bind(0)
        out = self._parallel(cached, 4, lambda i: judge.ask("same prompt").text)
        self.assertEqual((llm.calls, set(out)), (1, {"answer 1"}))

    def test_two_wrappers_same_file_share_lock(self):
        llm = SlowLLM()
        path = Path(self.tmp.name) / "c.sqlite"
        a, b = CachedLLM(llm, path=path, enabled=True), CachedLLM(llm, path=path, enabled=True)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        out = self._parallel(a, 4, lambda i: (a if i % 2 else b).chat(MSGS, sample_idx=0)[0].text)
        self.assertEqual((llm.calls, set(out)), (1, {"answer 1"}))

    def test_store_if_failure_lets_waiter_retry(self):
        """첫 응답이 store_if 를 통과 못하면 저장하지 않으므로, 기다리던 요청은 새로 호출한다 (실패를 공유하지 않는다)."""
        llm = SlowLLM(delay=0.1)
        cached = CachedLLM(llm, path=Path(self.tmp.name) / "c.sqlite", enabled=True)
        self.addCleanup(cached.close)
        ok = lambda r: r.text != "answer 1"
        out = self._parallel(cached, 2, lambda i: cached.chat(MSGS, sample_idx=0, store_if=ok))
        self.assertEqual(llm.calls, 2)
        self.assertEqual(cached.chat(MSGS, sample_idx=0, store_if=ok)[0].text, "answer 2")

    def test_existing_row_not_overwritten(self):
        llm = SlowLLM(delay=0)
        cached = CachedLLM(llm, path=Path(self.tmp.name) / "c.sqlite", enabled=True)
        self.addCleanup(cached.close)
        key = cache_key(llm, MSGS, 0)
        first = LLMResult(text="first", prompt_tokens=1, completion_tokens=1, latency=0.0, model=llm.model)
        cached.put(key, first, 0)
        cached.put(key, LLMResult(text="second", prompt_tokens=1, completion_tokens=1, latency=0.0,
                                  model=llm.model), 0)
        self.assertEqual(cached.get(key).text, "first")

if __name__ == "__main__":
    unittest.main()
