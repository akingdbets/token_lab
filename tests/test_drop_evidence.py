"""
drop_evidence 압축기 (근거 인용문 줄만 지우기) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm  # noqa: E402
from compressors import PromptParts, get_compressor  # noqa: E402
from compressors.drop_evidence import evidence_lines  # noqa: E402

CTX = """## Document: security

Intro line that stays in the context for sure.
`authenticate_user` still runs `verify_password(password, DUMMY_HASH)` when the user **doesn't exist**.
```python
app = FastAPI()
```
Step one of the procedure is described here in words.
Step two of the procedure follows right after it.
Closing paragraph that also stays in the context."""


def compress(evidence):
    with mock.patch.object(llm, "count_tokens", side_effect=lambda t: len(t.split())):
        return get_compressor("drop_evidence").compress(
            PromptParts(system="s", context=CTX, question="q", evidence=tuple(evidence)))


class DropEvidenceTest(unittest.TestCase):
    def test_single_line_quote_dropped_rest_kept(self):
        res = compress(["`authenticate_user` still runs `verify_password(password,  DUMMY_HASH)`"])
        self.assertNotIn("DUMMY_HASH", res.context)
        self.assertIn("Intro line", res.context)
        self.assertIn("app = FastAPI()", res.context)
        self.assertEqual((res.info["dropped_lines"], res.info["unmatched_quotes"]), (1, []))
        self.assertGreater(res.info["dropped_tokens"], 0)
        self.assertEqual((res.system, res.question), ("s", "q"))

    def test_multi_line_quote_drops_block(self):
        res = compress(["Step one of the procedure is described here in words.\n"
                        "Step two of the procedure follows right after it."])
        self.assertNotIn("Step one", res.context)
        self.assertNotIn("Step two", res.context)
        self.assertEqual(res.info["dropped_lines"], 2)

    def test_short_common_lines_not_dropped_elsewhere(self):
        drop, unmatched = evidence_lines(CTX, ("```python\napp = FastAPI()\nsomething not in the doc\n```",))
        self.assertEqual(drop, set())
        self.assertEqual(len(unmatched), 1)

    def test_evidence_survives_chain(self):
        with mock.patch.object(llm, "count_tokens", side_effect=lambda t: len(t.split())):
            res = get_compressor("none>drop_evidence").compress(
                PromptParts(system="s", context=CTX, question="q",
                            evidence=("Closing paragraph that also stays in the context.",)))
        self.assertNotIn("Closing paragraph", res.context)


if __name__ == "__main__":
    unittest.main()
