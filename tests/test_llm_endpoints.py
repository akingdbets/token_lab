"""
역할별 접속 정보(config), 토크나이저 선택, OpenAI 호환 응답의 usage 처리 테스트.

네트워크 호출과 토크나이저 다운로드 없이 mock 으로 확인한다.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import warnings
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm  # noqa: E402
from config import CFG, _env, tokenizer_kind  # noqa: E402
from grader import usage_source_of  # noqa: E402
from llm import LLM  # noqa: E402

MESSAGES = [{"role": "user", "content": "hi"}]


class EnvTest(unittest.TestCase):
    def test_new_name_wins_over_old(self):
        with mock.patch.dict(os.environ, {"ANSWER_MODEL": "gpt", "LLM_MODEL": "qwen"}):
            self.assertEqual(_env(("ANSWER_MODEL", "LLM_MODEL"), "x"), "gpt")

    def test_old_name_used_when_new_missing(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL": "qwen"}):
            os.environ.pop("ANSWER_MODEL", None)
            self.assertEqual(_env(("ANSWER_MODEL", "LLM_MODEL"), "x"), "qwen")

    def test_default_and_type(self):
        with mock.patch.dict(os.environ, {"A_INT": "7"}):
            os.environ.pop("B_INT", None)
            self.assertEqual(_env(("B_INT", "A_INT"), 1), 7)
            self.assertEqual(_env("B_INT", 1), 1)


class TokenizerKindTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(tokenizer_kind("Qwen/Qwen2.5-7B-Instruct"), ("hf", "Qwen/Qwen2.5-7B-Instruct"))
        self.assertEqual(tokenizer_kind("hf:Qwen/Qwen2.5-7B-Instruct"), ("hf", "Qwen/Qwen2.5-7B-Instruct"))
        self.assertEqual(tokenizer_kind("tiktoken:o200k_base"), ("tiktoken", "o200k_base"))


class RoleTest(unittest.TestCase):
    def test_role_picks_endpoint_and_model(self):
        with mock.patch.multiple(CFG, backend="openai", base_url="https://api.openai.com/",
                                 api_key="ka", model="gpt-x",
                                 judge_backend="openai", judge_base_url="https://api.deepseek.com",
                                 judge_api_key="kj", judge_model="ds-x"):
            a, j = LLM(), LLM(role="judge")
        self.assertEqual((a.backend, a.base_url, a.api_key, a.model),
                         ("openai", "https://api.openai.com", "ka", "gpt-x"))
        self.assertEqual((j.backend, j.base_url, j.api_key, j.model),
                         ("openai", "https://api.deepseek.com", "kj", "ds-x"))

    def test_explicit_args_override_role(self):
        with mock.patch.multiple(CFG, judge_model="ds-x"):
            j = LLM(role="judge", model="other")
        self.assertEqual(j.model, "other")

    def test_unknown_role(self):
        with self.assertRaises(ValueError):
            LLM(role="nope")

    def test_models_info_has_no_key(self):
        info = CFG.models_info()
        self.assertNotIn("api_key", json.dumps(info))
        self.assertEqual(set(info), {"answer", "judge", "embed", "tokenizer", "tokenizer_revision"})


class _FakeStream:
    def __init__(self, lines):
        self.lines = lines
        self.ok = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return iter(self.lines)


def _sse(d):
    return b"data: " + json.dumps(d).encode()


class OpenAIUsageTest(unittest.TestCase):
    def setUp(self):
        self.llm = LLM(backend="openai", base_url="http://x", api_key="", model="m")
        # 토크나이저 다운로드 없이 추정 경로를 확인
        p1 = mock.patch.object(llm, "count_message_tokens", return_value=111)
        p2 = mock.patch.object(llm, "count_tokens", return_value=22)
        p1.start(), p2.start()
        self.addCleanup(mock.patch.stopall)

    def test_stream_requests_usage_and_reads_final_chunk(self):
        lines = [
            _sse({"model": "m-2026", "choices": [{"delta": {"content": "Hel"}}]}),
            _sse({"choices": [{"delta": {"content": "lo"}}]}),
            _sse({"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 3}}),
            b"data: [DONE]",
        ]
        with mock.patch.object(llm.requests, "post", return_value=_FakeStream(lines)) as post:
            res = self.llm._openai_chat(MESSAGES, stream_ttft=True)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["stream_options"], {"include_usage": True})
        self.assertEqual(res.text, "Hello")
        self.assertEqual((res.prompt_tokens, res.completion_tokens, res.usage_source), (50, 3, "api"))
        self.assertEqual(res.model, "m-2026")

    def test_stream_without_usage_is_marked_estimate(self):
        lines = [_sse({"choices": [{"delta": {"content": "Hi"}}]}), b"data: [DONE]"]
        with mock.patch.object(llm.requests, "post", return_value=_FakeStream(lines)):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                res = self.llm._openai_chat(MESSAGES, stream_ttft=True)
        self.assertEqual((res.prompt_tokens, res.completion_tokens, res.usage_source), (111, 22, "estimate"))
        self.assertTrue(any("usage" in str(x.message) for x in w))

    def test_non_stream_usage(self):
        resp = mock.Mock()
        resp.json.return_value = {"model": "m", "choices": [{"message": {"content": "ok"}}],
                                  "usage": {"prompt_tokens": 9, "completion_tokens": 1}}
        with mock.patch.object(llm.requests, "post", return_value=resp) as post:
            res = self.llm._openai_chat(MESSAGES, stream_ttft=False)
        self.assertNotIn("stream_options", post.call_args.kwargs["json"])
        self.assertEqual((res.prompt_tokens, res.completion_tokens, res.usage_source), (9, 1, "api"))


def _resp(status, body):
    r = mock.Mock(status_code=status, ok=status < 400, text=json.dumps(body))
    r.json.return_value = body
    return r


def _unsupported(param):
    return _resp(400, {"error": {"message": f"{param} not supported", "param": param,
                                 "code": "unsupported_parameter"}})


class OpenAIUnsupportedParamTest(unittest.TestCase):
    """gpt-6 계열처럼 temperature / max_tokens 를 거부하는 서버."""

    def setUp(self):
        self.llm = LLM(backend="openai", base_url="http://x", api_key="", model="m",
                       temperature=0.0, max_tokens=64, max_retries=3)
        self.ok = _resp(200, {"model": "m", "choices": [{"message": {"content": "ok"}}],
                              "usage": {"prompt_tokens": 9, "completion_tokens": 1}})

    def test_adapts_and_remembers(self):
        with mock.patch.object(llm.requests, "post",
                               side_effect=[_unsupported("temperature"), _unsupported("max_tokens"),
                                            self.ok, self.ok]) as post:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                res = self.llm._openai_chat(MESSAGES, stream_ttft=False)
                self.llm._openai_chat(MESSAGES, stream_ttft=False)
        self.assertEqual(post.call_count, 4)   # 거부 2번 + 성공 2번 (두 번째 호출은 바로 성공)
        last = post.call_args.kwargs["json"]
        self.assertNotIn("temperature", last)
        self.assertNotIn("max_tokens", last)
        self.assertEqual(last["max_completion_tokens"], 64)
        self.assertIsNone(res.temperature)
        info = self.llm.sampling_info()
        self.assertEqual((info["temperature"], info["temperature_requested"], info["max_tokens_param"]),
                         (None, 0.0, "max_completion_tokens"))

    def test_other_4xx_raises_with_body_and_no_retry(self):
        bad = _resp(401, {"error": {"message": "invalid key", "param": None}})
        with mock.patch.object(llm.requests, "post", return_value=bad) as post:
            with self.assertRaises(llm.requests.HTTPError) as cm:
                self.llm._call_with_retry(MESSAGES, stream_ttft=False)
        self.assertIn("invalid key", str(cm.exception))
        self.assertEqual(post.call_count, 1)

    def test_supported_server_keeps_params(self):
        with mock.patch.object(llm.requests, "post", return_value=self.ok) as post:
            res = self.llm._openai_chat(MESSAGES, stream_ttft=False)
        sent = post.call_args.kwargs["json"]
        self.assertEqual((sent["temperature"], sent["max_tokens"]), (0.0, 64))
        self.assertEqual(res.temperature, 0.0)


@dataclass
class _R:
    usage_source: str | None


class UsageSourceOfTest(unittest.TestCase):
    def test_combine(self):
        self.assertIsNone(usage_source_of([]))
        self.assertEqual(usage_source_of([_R("api"), _R("api")]), "api")
        self.assertEqual(usage_source_of([_R("estimate")]), "estimate")
        self.assertEqual(usage_source_of([_R("api"), _R("estimate")]), "mixed")


if __name__ == "__main__":
    unittest.main()
