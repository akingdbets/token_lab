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
        self.assertEqual(engine.calls[0]["force_tokens"][:3], ["\n", "?", "create_access_token"])
        self.assertEqual(
            output.info["safety_policy_version"],
            "question-identifiers-v1+fenced-code-blocks-v1+document-headers-v1",
        )

    def test_registry_exposes_default_and_rate_variants(self):
        for name in ("llmlingua2", "llmlingua2_r30", "llmlingua2_r50", "llmlingua2_r70"):
            self.assertIn(name, REGISTRY)
            self.assertEqual(get_compressor(name).name, name)


if __name__ == "__main__":
    unittest.main()
