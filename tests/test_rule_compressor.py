"""RuleCompressor 머리말(frontmatter) 처리 테스트."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import REGISTRY, PromptParts  # noqa: E402
from compressors.rule import RuleCompressor  # noqa: E402

DOC = """## Document: testing/testing-basics.md

---
type: guide
title: Testing with TestClient
description: Test FastAPI apps with pytest and TestClient.
tags:
  - testing
  - testclient
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-252031fc006dbd553c56ddbf
    resource: repo://docs_src/app_testing/app_a_py310/test_main.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Testing with TestClient

Use **TestClient** from `fastapi.testclient`.
"""


def compress(c: RuleCompressor, text: str) -> str:
    return c.compress(PromptParts(system="", context=text, question="q")).context


class FrontmatterTest(unittest.TestCase):
    def test_default_keeps_summary_keys(self):
        out = compress(RuleCompressor(), DOC)
        self.assertIn("---\ntitle: Testing with TestClient\n"
                      "description: Test FastAPI apps with pytest and TestClient.\n"
                      "tags:\n  - testing\n  - testclient\n---\n", out)
        for gone in ("type: guide", "verified", "openwiki-source-", "repo://", "generated"):
            self.assertNotIn(gone, out)
        self.assertIn("# Testing with TestClient", out)
        self.assertIn("Use TestClient from `fastapi.testclient`.", out)

    def test_keep_empty_removes_whole_block(self):
        out = compress(RuleCompressor(frontmatter_keep=()), DOC)
        self.assertNotIn("---", out)
        self.assertNotIn("title:", out)
        self.assertNotIn("openwiki-source-", out)

    def test_registry(self):
        self.assertEqual(REGISTRY["rule"].config()["frontmatter_keep"], ["title", "description", "tags"])
        self.assertEqual(REGISTRY["rule_fm_all"].config()["frontmatter_keep"], [])
        self.assertEqual([REGISTRY[k].name for k in ("rule", "rule_fm_all")], ["rule", "rule_fm_all"])
        self.assertNotIn("title:", compress(REGISTRY["rule_fm_all"], DOC))

    def test_idempotent(self):
        once = compress(RuleCompressor(), DOC)
        self.assertEqual(compress(RuleCompressor(), once), once)

    def test_frontmatter_rule_off(self):
        out = compress(RuleCompressor(frontmatter=False), DOC)
        self.assertIn("openwiki-source-252031fc006dbd553c56ddbf", out)


if __name__ == "__main__":
    unittest.main()
