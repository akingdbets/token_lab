"""LLMLingua-2 어댑터 테스트. 네트워크와 실제 모델은 사용하지 않는다."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts, REGISTRY, get_compressor  # noqa: E402
from compressors.llmlingua2 import LLMLingua2Compressor, _split_fenced_blocks  # noqa: E402


class FakeEngine:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = []

    def compress_prompt(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def result(text: str, before: int = 10, after: int = 5) -> dict:
    return {
        "compressed_prompt": text,
        "origin_tokens": before,
        "compressed_tokens": after,
        "ratio": f"{before / after:.1f}x" if after else "1.0x",
        "rate": f"{100 * after / before:.1f}%" if before else "100.0%",
    }


def labeled_result(text: str, pairs: list[tuple[str, str]]) -> dict:
    """return_word_label=True 결과 (llmlingua 0.2.2 기본 구분자)."""
    return {**result(text), "fn_labeled_original_prompt": "\t\t|\t\t".join(f"{w} {label}" for w, label in pairs)}


class LLMLingua2CompressorTest(unittest.TestCase):
    def make(self, engine: FakeEngine, **kwargs) -> LLMLingua2Compressor:
        return LLMLingua2Compressor(
            retain_ratio=kwargs.pop("retain_ratio", 0.5),
            engine_factory=lambda: engine,
            force_tokens=kwargs.pop("force_tokens", ("\n", "?")),
            **kwargs,
        )

    def test_model_is_lazy_and_context_only_is_compressed(self):
        engine = FakeEngine(result("important 500 bytes"))
        factory_calls = []
        comp = LLMLingua2Compressor(
            retain_ratio=0.5,
            engine_factory=lambda: factory_calls.append(True) or engine,
        )
        self.assertEqual(factory_calls, [])

        output = comp.compress(PromptParts("system", "long context 500 bytes", "question"))

        self.assertEqual(factory_calls, [True])
        self.assertEqual(output.system, "system")
        self.assertEqual(output.context, "important 500 bytes")
        self.assertEqual(output.question, "question")
        self.assertEqual(output.llm_prompt_tokens, 0)
        self.assertEqual(output.llm_completion_tokens, 0)
        self.assertEqual(output.info["status"], "compressed")
        self.assertEqual(output.info["trace"]["removed_tokens_internal"], 5)
        self.assertEqual(output.info["trace"]["reduction_pct_internal"], 50.0)

    def test_official_call_uses_retain_ratio_and_protection(self):
        engine = FakeEngine(result("short"))
        comp = self.make(engine, retain_ratio=0.3, force_reserve_digit=True)
        comp.compress(PromptParts("", "source text", "unused question"))
        call = engine.calls[0]
        self.assertEqual(call["context"], ["source text"])
        self.assertEqual(call["rate"], 0.3)
        self.assertFalse(call["use_context_level_filter"])
        self.assertTrue(call["use_token_level_filter"])
        self.assertTrue(call["force_reserve_digit"])

    def test_default_protection_contains_negation_and_identifier_separator(self):
        engine = FakeEngine(result("short"))
        comp = LLMLingua2Compressor(engine_factory=lambda: engine)
        output = comp.compress(
            PromptParts("", "GZipMiddleware uses minimum_size for source text", "question")
        )
        protected = engine.calls[0]["force_tokens"]
        self.assertIn("not", protected)
        self.assertIn("unless", protected)
        self.assertIn("don't", protected)
        self.assertIn("can't", protected)
        self.assertIn("default", protected)
        self.assertIn("except", protected)
        self.assertIn("_", protected)
        self.assertIn("GZipMiddleware", protected)
        self.assertIn("minimum_size", protected)
        self.assertEqual(
            output.info["protected_identifiers"],
            ["GZipMiddleware", "minimum_size"],
        )

    def test_empty_context_does_not_load_model(self):
        factory_calls = []
        comp = LLMLingua2Compressor(
            engine_factory=lambda: factory_calls.append(True),
        )
        output = comp.compress(PromptParts("", " \n", "question"))
        self.assertEqual(output.context, " \n")
        self.assertEqual(output.info["status"], "unchanged_empty_input")
        self.assertEqual(factory_calls, [])

    def test_invalid_ratios_are_rejected(self):
        for value in (0, -0.1, 1.01):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    LLMLingua2Compressor(retain_ratio=value)

    def test_engine_error_falls_back_and_is_recorded(self):
        comp = self.make(FakeEngine(error=RuntimeError("model failed\nsecret detail")))
        source = "original context"
        output = comp.compress(PromptParts("", source, "question"))
        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_error")
        self.assertEqual(output.info["error_type"], "RuntimeError")
        self.assertNotIn("\n", output.info["error"])
        self.assertTrue(output.info["trace"]["used_original"])

    def test_empty_and_larger_outputs_fall_back(self):
        cases = (
            (result(" ", before=10, after=0), "fallback_empty_output"),
            (result("too many tokens", before=10, after=11), "fallback_larger_output"),
        )
        for fake_result, status in cases:
            with self.subTest(status=status):
                comp = self.make(FakeEngine(fake_result))
                output = comp.compress(PromptParts("", "original context", ""))
                self.assertEqual(output.context, "original context")
                self.assertEqual(output.info["status"], status)
                self.assertEqual(output.info["trace"]["removed_tokens_internal"], 0)
                self.assertEqual(
                    output.info["attempted_compressed_tokens_internal"],
                    fake_result["compressed_tokens"],
                )

    def test_broken_code_fence_falls_back(self):
        source = "before\n```python\nvalue = 1\n```\nafter"
        compressed = "__LLMLINGUA_PROTECTED_CODE_BLOCK_0000__\n```"
        comp = self.make(FakeEngine(result(compressed)))
        output = comp.compress(PromptParts("", source, ""))
        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_broken_fence")

    def test_fenced_code_block_is_excluded_and_restored_exactly(self):
        code = "```python\nif value:\n    return 15\n```"
        protected_code = f"{code}\n"
        source = f"before prose\n{protected_code}after prose"
        compressed = "short __LLMLINGUA_PROTECTED_CODE_BLOCK_0000__ after"
        engine = FakeEngine(result(compressed))
        comp = self.make(engine)

        output = comp.compress(PromptParts("", source, ""))

        self.assertNotIn("return 15", engine.calls[0]["context"][0])
        self.assertIn("__LLMLINGUA_PROTECTED_CODE_BLOCK_0000__", engine.calls[0]["context"][0])
        self.assertIn("__LLMLINGUA_PROTECTED_CODE_BLOCK_0000__", engine.calls[0]["force_tokens"])
        self.assertEqual(output.context, f"short\n{protected_code} after")
        source_blocks = [chunk for is_code, chunk in _split_fenced_blocks(source) if is_code]
        output_blocks = [chunk for is_code, chunk in _split_fenced_blocks(output.context) if is_code]
        self.assertEqual(output_blocks, source_blocks)
        self.assertEqual(output.info["protected_code_blocks"], 1)
        self.assertEqual(output.info["protected_code_characters"], len(protected_code))

    def test_missing_code_block_marker_falls_back(self):
        source = "before\n```python\nvalue = 1\n```\nafter"
        comp = self.make(FakeEngine(result("compressed without marker")))

        output = comp.compress(PromptParts("", source, ""))

        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_missing_code_block_marker")
        self.assertEqual(
            output.info["missing_code_block_markers"],
            ["__LLMLINGUA_PROTECTED_CODE_BLOCK_0000__"],
        )

    def test_document_headers_are_excluded_and_restored_exactly(self):
        # BERT tokenizer 는 force token 을 복원하면서 " ##" 를 지운다. 경계 줄은 마커로 빼 두었다가 그대로 되돌린다
        first = "## Document: security/oauth2-jwt.md\n"
        second = "## Document: security/oauth2-password-flow.md\n"
        source = f"{first}\nJWT tokens are signed.\n\n{second}\nPassword flow returns a token."
        compressed = (
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ \n JWT tokens signed \n \n "
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0001__ \n Password flow returns token"
        )
        engine = FakeEngine(result(compressed))
        comp = self.make(engine)

        output = comp.compress(PromptParts("", source, ""))

        sent = engine.calls[0]["context"][0]
        self.assertNotIn("## Document:", sent)
        self.assertIn("__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0001__", sent)
        self.assertIn("__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__", engine.calls[0]["force_tokens"])
        self.assertIn("__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0001__", engine.calls[0]["force_tokens"])
        self.assertEqual(output.info["status"], "compressed")
        self.assertEqual(
            output.context,
            f"{first}\n JWT tokens signed \n \n{second}\n Password flow returns token",
        )
        self.assertEqual(output.info["protected_document_headers"], 2)

    def test_document_headers_and_code_blocks_keep_source_order(self):
        source = "## Document: a.md\nintro\n```python\nx = 1\n```\n## Document: b.md\noutro"
        compressed = (
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ intro __LLMLINGUA_PROTECTED_CODE_BLOCK_0000__ "
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0001__ outro"
        )
        output = self.make(FakeEngine(result(compressed))).compress(PromptParts("", source, ""))
        self.assertEqual(output.info["status"], "compressed")
        self.assertEqual(output.context, source)

    def test_header_inside_code_block_stays_part_of_code(self):
        source = "## Document: a.md\n```markdown\n## Document: not-a-boundary\n```\n"
        compressed = "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ __LLMLINGUA_PROTECTED_CODE_BLOCK_0000__"
        output = self.make(FakeEngine(result(compressed))).compress(PromptParts("", source, ""))
        self.assertEqual(output.info["status"], "compressed")
        self.assertEqual(output.context, source)
        self.assertEqual(output.info["protected_document_headers"], 1)
        self.assertEqual(output.info["protected_code_blocks"], 1)

    def test_missing_document_header_marker_falls_back(self):
        source = "## Document: guide.md\n\nimportant fact"
        comp = self.make(FakeEngine(result("important fact")))
        output = comp.compress(PromptParts("", source, ""))
        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_missing_document_header_marker")
        self.assertEqual(
            output.info["missing_document_header_markers"],
            ["__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__"],
        )

    def test_reordered_protected_markers_fall_back(self):
        source = "## Document: a.md\nfirst\n## Document: b.md\nsecond"
        compressed = (
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0001__ second "
            "__LLMLINGUA_PROTECTED_DOCUMENT_HEADER_0000__ first"
        )
        output = self.make(FakeEngine(result(compressed))).compress(PromptParts("", source, ""))
        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_reordered_protected_marker")

    def test_missing_question_identifier_falls_back(self):
        source = "def create_access_token(expires_delta=None): return 15"
        compressed = "expires_delta None return 15"
        engine = FakeEngine(result(compressed))
        comp = self.make(engine)

        output = comp.compress(PromptParts(
            "",
            source,
            "What does create_access_token use by default?",
        ))

        self.assertEqual(output.context, source)
        self.assertEqual(output.info["status"], "fallback_missing_question_identifier")
        self.assertEqual(output.info["required_question_identifiers"], ["create_access_token"])
        self.assertEqual(output.info["missing_question_identifiers"], ["create_access_token"])
        self.assertTrue(output.info["trace"]["used_original"])

    def test_question_identifier_is_prioritized_and_preserved(self):
        source = "def create_access_token(expires_delta=None): return 15"
        compressed = "create_access_token expires_delta 15"
        engine = FakeEngine(result(compressed))
        comp = self.make(engine)

        output = comp.compress(PromptParts(
            "",
            source,
            "What does create_access_token use by default?",
        ))

        self.assertEqual(output.context, compressed)
        self.assertEqual(output.info["status"], "compressed")
        self.assertEqual(output.info["required_question_identifiers"], ["create_access_token"])
        self.assertEqual(output.info["protected_identifiers"][0], "create_access_token")
        self.assertEqual(
            output.info["safety_policy_version"],
            "question-identifiers-v1+fenced-code-blocks-v1+document-headers-v1+unsplit-identifiers-v1",
        )

    def assert_not_split_by_llmlingua(self, source: str, question: str, **kwargs):
        """llmlingua 0.2.2 처럼 force token 을 리스트 순서대로 단어 경계 없이 [NEWi] 로 치환했을 때
        [NEWi] 앞뒤에 다른 영숫자가 붙지 않는지 (붙으면 복원 뒤 공백이 끼어 식별자가 쪼개진다)."""
        engine = FakeEngine(result("short"))
        self.make(engine, **kwargs).compress(PromptParts("", source, question))
        sent = engine.calls[0]["context"][0]
        force_tokens = engine.calls[0]["force_tokens"]
        self.assertEqual([len(t) for t in force_tokens], sorted(map(len, force_tokens), reverse=True))
        for i, token in enumerate(force_tokens):
            if len(token) > 1:
                sent = sent.replace(token, f"[NEW{i}]")
        self.assertNotRegex(sent, r"[A-Za-z0-9_]\[NEW|\][A-Za-z0-9_]")
        return force_tokens

    def test_identifier_inside_longer_word_is_not_split(self):
        # c0034: 질문 식별자 OAuth2 가 OAuth2PasswordRequestFormStrict 안에서 바뀌어 "OAuth2 PasswordRequestFormStrict"
        # c0001: 문맥 앞쪽의 JWT 가 PyJWT 안에서 바뀌어 "Py JWT"
        force_tokens = self.assert_not_split_by_llmlingua(
            "Use JWT tokens with OAuth2. Install PyJWT. OAuth2PasswordRequestFormStrict requires grant_type.",
            "Which OAuth2 form class requires grant_type?",
        )
        for value in ("OAuth2", "OAuth2PasswordRequestFormStrict", "JWT", "PyJWT"):
            self.assertIn(value, force_tokens)

    def test_containing_word_is_added_even_past_identifier_limit(self):
        # c0040: 식별자가 많아 긴 WebSocketDisconnect 가 한도에 밀려도, 짧은 WebSocket 을 보호하면 함께 들어간다
        filler = " ".join(f"Item{i}Name" for i in range(120))
        force_tokens = self.assert_not_split_by_llmlingua(
            f"WebSocket basics. {filler}. Catch WebSocketDisconnect when the client leaves.",
            "What does WebSocket raise on disconnect?",
        )
        self.assertIn("WebSocket", force_tokens)
        self.assertIn("WebSocketDisconnect", force_tokens)
        self.assertLessEqual(len(force_tokens), 100)

    def test_identifier_dropped_when_containing_word_does_not_fit(self):
        filler = " ".join(f"Item{i}Name" for i in range(120))
        force_tokens = self.assert_not_split_by_llmlingua(f"{filler}. Then CORSMiddleware and CORS.", "q")
        self.assertLessEqual(len(force_tokens), 100)
        self.assertNotIn("CORS", force_tokens)

    def rejoin(self, source: str, labels: str):
        """labels: 공백으로 나눈 "단어/라벨" (예: "0/1 ./0"). 압축 결과는 BERT 처럼 남긴 단어를 공백으로 잇는다."""
        pairs = [(w.rsplit("/", 1)[0].replace("\\n", "\n"), w.rsplit("/", 1)[1]) for w in labels.split()]
        compressed = " ".join(w for w, label in pairs if label == "1")
        engine = FakeEngine(labeled_result(compressed, pairs))
        return self.make(engine, rejoin_punctuated=True).compress(PromptParts("", source, "q")), engine

    def test_punctuated_tokens_split_by_compression_are_rejoined_by_word_labels(self):
        # c0007 "0.95.0" → "0 95 0", c0076 하이픈 이름 → "standard no fastapi cloud - cli"
        output, engine = self.rejoin(
            "FastAPI 0.95.0 works.\nInstall fastapi[standard-no-cli] or pydantic.v1 too.",
            "FastAPI/1 0/1 ./0 95/1 ./0 0/1 works/0 ./0 \\n/1 Install/0 fastapi/1 [/0 standard/1 -/0 no/1 -/1 "
            "cli/1 ]/0 or/0 pydantic/1 ./0 v1/1 too/0 ./0",
        )

        self.assertEqual(output.context, "FastAPI 0.95.0 \n fastapi standard-no-cli pydantic.v1")
        self.assertEqual(output.info["rejoined_punctuated"], ["0.95.0", "standard-no-cli", "pydantic.v1"])
        self.assertIsNone(output.info["rejoin_skipped"])
        self.assertTrue(output.info["safety_policy_version"].endswith("+rejoin-punctuated-v2"))
        self.assertTrue(engine.calls[0]["return_word_label"])

    def test_rejoin_skips_tokens_with_dropped_segments(self):
        output, _ = self.rejoin("Requires 0.128.0 now.", "Requires/1 0/1 ./0 128/1 ./0 0/0 now/0 ./0")

        self.assertEqual(output.context, "Requires 0 128")
        self.assertEqual(output.info["rejoined_punctuated"], [])

    def test_rejoin_uses_positions_not_matching_text(self):
        # v1(문자열 매칭)이 틀렸던 경우: 멀쩡한 2-9 를 2.9 로, 쉼표 빠진 "1, 0" 을 1.0 으로,
        # 수식 "3 - 1" 을 3.1 로, 줄바꿈 너머 "1\n5" 를 1.5 로 바꿨다
        cases = [
            ("See pages 2-9. Version 2.9 is new.",
             "See/0 pages/1 2/1 -/1 9/1 ./0 Version/1 2/1 ./0 9/1 is/0 new/1 ./0",
             "pages 2-9 Version 2.9 new"),
            ("Returns 1, 0 on error. Use version 1.0 now.",
             "Returns/1 1/1 ,/0 0/1 on/0 error/1 ./0 Use/1 version/1 1/1 ./0 0/1 now/0 ./0",
             "Returns 1 0 error Use version 1.0"),
            ("Compute 3 - 1 here. Python 3.1 is old.",
             "Compute/1 3/1 -/1 1/1 here/0 ./0 Python/1 3/1 ./0 1/1 is/0 old/1 ./0",
             "Compute 3 - 1 Python 3.1 old"),
            ("Total 1\n5 items. Version 1.5 out.",
             "Total/1 1/1 \\n/1 5/1 items/1 ./0 Version/1 1/1 ./0 5/1 out/0 ./0",
             "Total 1 \n 5 items Version 1.5"),
        ]
        for source, labels, expected in cases:
            with self.subTest(source=source):
                output, _ = self.rejoin(source, labels)
                self.assertEqual(output.context, expected)

    def test_rejoin_is_skipped_when_labels_do_not_align_or_are_missing(self):
        misaligned, _ = self.rejoin("Use 2.9 here.", "Use/1 3/1 ./0 9/1 here/0 ./0")
        self.assertEqual(misaligned.context, "Use 3 9")
        self.assertEqual(misaligned.info["rejoin_skipped"], "source_alignment_failed")

        # BERT 어휘에 없는 "—" "`" 는 [UNK] 로 단어 목록에서 빠지지만 정렬은 이어진다
        unknown, _ = self.rejoin("Login — use `2.9` now.", "Login/1 use/1 2/1 ./0 9/1 now/0 ./0")
        self.assertEqual(unknown.context, "Login use 2.9")
        self.assertIsNone(unknown.info["rejoin_skipped"])

        missing = self.make(FakeEngine(result("Use 2 9")), rejoin_punctuated=True).compress(
            PromptParts("", "Use 2.9 here.", "q")
        )
        self.assertEqual(missing.context, "Use 2 9")
        self.assertEqual(missing.info["rejoin_skipped"], "missing_word_labels")

    def test_rejoin_is_off_by_default(self):
        engine = FakeEngine(result("Use 2 9"))
        off = self.make(engine).compress(PromptParts("", "Use 2.9 here.", "q"))

        self.assertEqual(off.context, "Use 2 9")
        self.assertNotIn("rejoined_punctuated", off.info)
        self.assertNotIn("return_word_label", engine.calls[0])
        self.assertNotIn("rejoin_punctuated", LLMLingua2Compressor().config())

    def test_registry_exposes_default_and_rate_variants(self):
        for name in (
            "llmlingua2", "llmlingua2_r30", "llmlingua2_r50", "llmlingua2_r70",
            "llmlingua2_punct", "llmlingua2_r30_punct", "llmlingua2_r50_punct", "llmlingua2_r70_punct",
        ):
            self.assertIn(name, REGISTRY)
            self.assertEqual(get_compressor(name).name, name)
        self.assertTrue(REGISTRY["llmlingua2_r30_punct"].rejoin_punctuated)
        self.assertFalse(REGISTRY["llmlingua2_r30"].rejoin_punctuated)


if __name__ == "__main__":
    unittest.main()
