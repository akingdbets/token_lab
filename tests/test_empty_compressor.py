"""
empty 압축기 (문서를 비우는 바닥값) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts, get_compressor  # noqa: E402


class EmptyContextTest(unittest.TestCase):
    def test_context_is_emptied_and_rest_kept(self):
        parts = PromptParts(system="You answer...", context="# Doc\nlong text", question="What is X?")
        res = get_compressor("empty").compress(parts)
        self.assertEqual((res.system, res.context, res.question), ("You answer...", "", "What is X?"))
        self.assertEqual((res.llm_prompt_tokens, res.llm_completion_tokens), (0, 0))


if __name__ == "__main__":
    unittest.main()
