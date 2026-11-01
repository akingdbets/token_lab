"""
압축률 – 손실 곡선 (ratio_curve) 테스트. 실제 모델·임베딩은 쓰지 않는다.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ratio_curve  # noqa: E402
from compressors.llmlingua2 import LLMLingua2Compressor  # noqa: E402

CTX = """## Document: security

`authenticate_user` still runs `verify_password(password, DUMMY_HASH)` when the user doesn't exist.
```python
app = FastAPI()
```
Closing paragraph."""

ITEM = {"id": "c0001", "type": "fact", "question": "Which hash is checked?", "answer": "DUMMY_HASH",
        "key_entities": ["DUMMY_HASH", "authenticate_user"],
        "evidence": [{"quote": "`authenticate_user` still runs `verify_password(password, DUMMY_HASH)`"}]}


class FakeEngine:
    def __init__(self, text):
        self.text = text

    def compress_prompt(self, **kw):
        return {"compressed_prompt": self.text, "origin_tokens": 10, "compressed_tokens": 5}


def words(text: str) -> int:
    return len(text.split())


class MeasureTest(unittest.TestCase):
    def measure(self, compressed_masked: str):
        comp = LLMLingua2Compressor(retain_ratio=0.5, engine_factory=lambda: FakeEngine(compressed_masked),
                                    force_tokens=("\n",))
        with mock.patch.object(ratio_curve, "count_tokens", side_effect=words):
            return ratio_curve.measure(ITEM, CTX, words(CTX), None, comp, embedder=None)

    def test_kept_evidence(self):
        row = self.measure("__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ authenticate_user still runs "
                           "verify_password(password, DUMMY_HASH) __LLMLINGUA_PROTECTED_CODE_BLOCK_0000__ Closing.")
        self.assertEqual(row["status"], "compressed")
        self.assertEqual(row["ratio"], 0.5)
        self.assertEqual(row["evidence_retention"], 1.0)
        self.assertTrue(row["answer_core"])
        self.assertEqual(row["entity_retention"], 1.0)
        self.assertGreater(row["reduction_pct"], 0)
        self.assertIsNone(row["semantic_loss"])          # 임베딩 없이 돌리면 의미 손실은 비운다

    def test_lost_evidence(self):
        row = self.measure("__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ user "
                           "__LLMLINGUA_PROTECTED_CODE_BLOCK_0000__ Closing.")
        self.assertLess(row["evidence_retention"], 0.5)
        self.assertFalse(row["answer_core"])
        self.assertEqual(row["entity_retention"], 0.0)


class AggregateTest(unittest.TestCase):
    def test_token_sum_reduction_and_rates(self):
        rows = [
            {"ctx_tokens_raw": 100, "ctx_tokens": 50, "semantic_loss": 0.02, "entity_retention": 1.0,
             "evidence_retention": 1.0, "answer_core": True, "status": "compressed"},
            {"ctx_tokens_raw": 300, "ctx_tokens": 250, "semantic_loss": 0.2, "entity_retention": 0.5,
             "evidence_retention": 0.4, "answer_core": False, "status": "fallback_error"},
        ]
        s = ratio_curve.aggregate(rows)
        self.assertEqual(s["reduction_pct"], 25.0)
        self.assertEqual(s["within_5pct"], 0.5)
        self.assertEqual(s["answer_core_rate"], 0.5)
        self.assertEqual(s["evidence_retention"], 0.7)
        self.assertEqual(s["fallback"], 1)


class CodeTokensTest(unittest.TestCase):
    def test_only_fenced_blocks(self):
        with mock.patch.object(ratio_curve, "count_tokens", side_effect=words):
            self.assertEqual(ratio_curve.code_tokens(CTX), words("```python\napp = FastAPI()\n```\n"))


if __name__ == "__main__":
    unittest.main()
