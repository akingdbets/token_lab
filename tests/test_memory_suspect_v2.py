"""
memory_suspect 두 축 분류(정답 핵심어 × 근거 보존율)와 normalized-v2 매칭 테스트.

tests/fixtures/memory_suspect_v1/ 은 run 20261028-195811 (PR #28·#30 이전 코드) 에서 이전 방식으로
memory_suspect 였던 14건과, 정답이 정말 빠져 NOT FOUND 였던 대조 2건의 압축 문맥, 그 문항들의 none 문맥이다.
아래 EXPECTED 는 문맥을 사람이 읽고 정한 분류다 (docs/results/llmlingua2_dev_v1.md 의 memory_suspect 절).

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from corpus import load_corpus  # noqa: E402
from experiment import answer_core_in_context, build_context, find_normalized  # noqa: E402
from memory_suspect import classify  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "memory_suspect_v1"
ITEMS = {x["id"]: x for x in json.loads((ROOT / "data/evalsets/claude-v1/qa_dataset.json").read_text(encoding="utf-8"))}

EXPECTED = {
    # 표기 분리·관사: 정답 핵심어가 문맥에 있다 (이전 방식의 오탐)
    ("c0004", "llmlingua2_r70"): "core_present",     # "last one added outermost" (The 만 빠짐)
    ("c0026", "llmlingua2_r30"): "core_present",     # 코드의 asgi_lifespan (정답 asgi-lifespan)
    ("c0031", "llmlingua2_r70"): "core_present",     # WebSocket Disconnect
    ("c0031", "llmlingua2_r50"): "core_present",
    ("c0034", "llmlingua2_r70"): "core_present",     # OAuth2 PasswordRequestFormStrict
    ("c0034", "llmlingua2_r50"): "core_present",
    # 표현만 바뀜 (중간 단어 삭제): 매칭으로 잡지 않고 근거 보존율 축에 맡긴다
    ("c0030", "llmlingua2_r70"): "evidence_kept",    # "override ' s signature" (own 삭제)
    ("c0004", "llmlingua2_r50"): "evidence_low",     # "last added outermost"
    ("c0004", "rule>llmlingua2"): "evidence_low",
    ("c0030", "llmlingua2_r50"): "evidence_low",     # "override signature"
    ("c0030", "rule>llmlingua2"): "evidence_low",
    ("c0034", "rule>llmlingua2"): "evidence_low",    # "OAuth2 PasswordRequestForm" 만 있고 Strict 없음
    # 근거 없음 (헤드라인). 사람이 보면 둘 다 간접 단서가 남아 있다
    ("c0004", "llmlingua2_r30"): "evidence_absent",  # 요청·응답 순서 줄 "MiddlewareB MiddlewareA" 만 남음
    ("c0030", "llmlingua2_r30"): "evidence_absent",  # 산문 조각 "function parameters" 만 남음
    # 정답이 정말 빠져 NOT FOUND (정확도 0): 의심 대상이 아니다
    ("c0031", "llmlingua2_r30"): "not_correct",
    ("c0034", "llmlingua2_r30"): "not_correct",
}


def read(qid: str, comp: str) -> str:
    return (FIXTURE / f"{qid}.{comp.replace('>', '+')}.md").read_text(encoding="utf-8")


class HandClassificationTest(unittest.TestCase):
    def test_reproduces_manual_classification(self):
        cases = json.loads((FIXTURE / "cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual({(c["qid"], c["compressor"]) for c in cases}, set(EXPECTED))
        for c in cases:
            key = (c["qid"], c["compressor"])
            with self.subTest(case=key):
                r = classify(ITEMS[c["qid"]], read(*key), read(c["qid"], "none"), c["answer_accuracy"])
                self.assertEqual(r["label"], EXPECTED[key], r)
                self.assertTrue(r["measurable"])

    def test_headline_and_sensitivity(self):
        heads = {k for k, v in EXPECTED.items() if v == "evidence_absent"}
        sens = {k for k, v in EXPECTED.items() if v in ("evidence_absent", "evidence_low")}
        for key in EXPECTED:
            r = classify(ITEMS[key[0]], read(*key), read(key[0], "none"), 1.0 if EXPECTED[key] != "not_correct" else 0.0)
            self.assertEqual(r["memory_suspect"], key in heads, key)
            self.assertEqual(r["memory_suspect_sensitive"], key in sens, key)


class NormalizedMatchTest(unittest.TestCase):
    def found(self, ctx, needle):
        return find_normalized(ctx, needle) is not None

    def test_spaces_inserted_by_compression_are_allowed(self):
        self.assertTrue(self.found("raises WebSocket Disconnect assert", "WebSocketDisconnect"))
        self.assertTrue(self.found("from asgi_lifespan import x", "asgi-lifespan"))
        self.assertTrue(self.found("the asgi - lifespan package", "asgi-lifespan"))
        self.assertTrue(self.found("python 3.10 or later", "3.10"))

    def test_identifier_parts_and_merged_words_are_not_matches(self):
        # 다른 문항 문맥에서 normalized-v1 이 "있다"고 잘못 본 사례들
        self.assertFalse(self.found("async def read_items(): ...", "Read items."))
        self.assertFalse(self.found("username johndoe", "John Doe"))
        self.assertFalse(self.found("HTTPBearer(auto_error=False)", '"auto"'))
        self.assertFalse(self.found("requires Python 3.10+", "3.1.0"))
        self.assertFalse(self.found("version 10.0 released", "100"))
        self.assertFalse(self.found("WebSocketDisconnected", "WebSocketDisconnect"))

    def test_leading_article_is_ignored_for_short_answers(self):
        it = {"answer": "The last one added", "key_entities": ["The last one added"]}
        self.assertTrue(answer_core_in_context("wraps app built last one added outermost", it))
        self.assertFalse(answer_core_in_context("wraps app built last added outermost", it))   # 중간 삭제는 안 잡음


class NoneContextTest(unittest.TestCase):
    """압축 없는 원문에는 정답이 있어야 한다. 원문에서도 안 잡히는 문항은 측정 불가로 뺀다."""
    # 정답을 문장으로 바꿔 써서 원문 문자열과 다른 문항 (c0124 "The parameter names" 는 관사 규칙으로 잡힘)
    UNMEASURABLE = {"c0008", "c0009", "c0012", "c0043", "c0049", "c0061", "c0073", "c0102", "c0139", "c0173"}

    def test_only_known_paraphrased_answers_are_missing(self):
        corpus = load_corpus()
        missing = {q for q, x in ITEMS.items() if not answer_core_in_context(build_context(corpus, x), x)}
        self.assertEqual(missing, self.UNMEASURABLE)

    def test_unmeasurable_item_is_not_suspect(self):
        x = ITEMS["c0012"]
        r = classify(x, "nothing left", "takes ~10 seconds to stop", 1.0)
        self.assertFalse(r["measurable"])
        self.assertEqual(r["label"], "unmeasurable")
        self.assertFalse(r["memory_suspect"])


if __name__ == "__main__":
    unittest.main()
