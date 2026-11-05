import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts, REGISTRY, get_compressor  # noqa: E402
from compressors.sentence_select import (  # noqa: E402
    SentenceSelectCompressor,
    join_units,
    split_documents,
    split_units,
)

DOC = """## Document: a.md

---
title: Demo
---

# Title

This is filler prose about things. It keeps going for a while. Set `max_age` to change it.

- a plain list item here
- the default is 600 seconds

| key | value |
|-----|-------|
| samesite | "lax" (default) |

```python
x = 1

y = 2
```

> Note: keep this.

Another plain sentence here. And one more plain sentence.
"""


def by_length(texts):
    """긴 단위일수록 점수가 높다 (결정적인 가짜 점수)."""
    return [float(len(t)) for t in texts]


def by_position(texts):
    """앞 단위일수록 점수가 높다."""
    return [-float(i) for i in range(len(texts))]


def make(**kw):
    kw.setdefault("min_chars", 0)
    kw.setdefault("scorer", by_position)
    return SentenceSelectCompressor(**kw)


class SplitTest(unittest.TestCase):
    def test_keeping_everything_round_trips(self):
        units = split_units(DOC)
        self.assertEqual(join_units(units, [True] * len(units)), DOC)

    def test_structure_units(self):
        kinds = {u.kind for u in split_units(DOC)}
        for kind in ("doc_header", "frontmatter", "heading", "list", "table", "code", "quote", "sentence", "blank"):
            self.assertIn(kind, kinds)
        code = [u for u in split_units(DOC) if u.kind == "code"]
        self.assertEqual(len(code), 1)
        self.assertIn("\n\ny = 2\n", code[0].text)

    def test_sentences_split_and_marked(self):
        units = {u.text: u for u in split_units(DOC) if u.kind in ("sentence", "list")}
        self.assertIn("This is filler prose about things.", units)
        self.assertIn("number", units["- the default is 600 seconds"].reasons)
        self.assertEqual(units["It keeps going for a while."].reasons, ())
        self.assertEqual(units["Set `max_age` to change it."].reasons, ())   # 인라인 코드는 표지가 아니다

    def test_abbreviation_does_not_split(self):
        texts = [u.text for u in split_units("Use types (e.g. Decimal) here. Next one.\n") if u.kind == "sentence"]
        self.assertEqual(texts, ["Use types (e.g. Decimal) here.", "Next one."])

    def test_split_documents(self):
        ctx = "## Document: a\n\nA.\n\n## Document: b\n\nB.\n"
        self.assertEqual("".join(split_documents(ctx)), ctx)
        self.assertEqual(len(split_documents(ctx)), 2)


class SelectTest(unittest.TestCase):
    def compress(self, comp, context=DOC, question="q"):
        return comp.compress(PromptParts("", context, question))

    def test_protected_units_always_survive(self):
        out = self.compress(make(keep_ratio=0.01, protect="loose")).context
        for kept in ("## Document: a.md", "title: Demo", "# Title",
                     "- the default is 600 seconds", '| samesite | "lax" (default) |', "x = 1\n\ny = 2",
                     "> Note: keep this."):
            self.assertIn(kept, out)

    def test_dropped_sentences_are_whole_and_lines_collapse(self):
        out = self.compress(make(keep_ratio=0.01, protect="loose")).context
        # 예산을 넘기 전까지 점수 높은 순으로 남기므로 가장 앞(점수 최고) 후보 하나만 남는다
        self.assertIn("This is filler prose about things.\n", out)
        self.assertNotIn("It keeps going", out)
        self.assertNotIn("Set `max_age`", out)
        self.assertNotIn("Another plain sentence", out)
        self.assertNotIn("- a plain list item here", out)
        self.assertNotIn("\n\n\n", out)

    def test_keep_ratio_budget_follows_scores(self):
        comp = make(keep_ratio=0.5, protect="structure", scorer=by_length)
        res = self.compress(comp)
        info = res.info["documents"][0]
        self.assertEqual(info["status"], "select")
        self.assertLessEqual(info["dropped_chars"], info["candidate_chars"])
        self.assertGreater(info["dropped_units"], 0)
        # 가장 긴 후보는 남는다
        self.assertIn("This is filler prose about things.", res.context)

    def test_question_is_not_used(self):
        comp = make(keep_ratio=0.5, protect="structure")
        a = self.compress(comp, question="What is max_age?").context
        b = self.compress(comp, question="Something about filler prose").context
        self.assertEqual(a, b)

    def test_protect_levels_change_candidates(self):
        counts = {}
        for level in ("loose", "structure"):
            res = self.compress(make(protect=level))
            counts[level] = res.info["documents"][0]["candidate_units"]
        self.assertLess(counts["loose"], counts["structure"])

    def test_short_and_dense_documents_are_skipped(self):
        res = self.compress(make(min_chars=10_000))
        self.assertEqual(res.context, DOC)
        self.assertEqual(res.info["documents"][0]["status"], "skip_short")
        res = self.compress(make(max_protected_share=0.1))
        self.assertEqual(res.context, DOC)
        self.assertEqual(res.info["documents"][0]["status"], "skip_dense")

    def test_scorer_never_called_when_skipped(self):
        def boom(texts):
            raise AssertionError("scorer called")
        self.compress(make(min_chars=10_000, scorer=boom))

    def test_bad_scorer_length_raises(self):
        with self.assertRaises(ValueError):
            self.compress(make(protect="structure", scorer=lambda texts: [1.0]))

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            SentenceSelectCompressor(keep_ratio=0)
        with self.assertRaises(ValueError):
            SentenceSelectCompressor(protect="nope")

    def test_registry(self):
        for name in ("sent_loose_r70", "sent_structure_r50", "sent_loose_r50"):
            self.assertIn(name, REGISTRY)
        for gone in ("sent_strict_r70", "sent_literal_r70"):
            self.assertNotIn(gone, REGISTRY)
        chain = get_compressor("rule>sent_loose_r70")
        self.assertEqual(chain.name, "rule>sent_loose_r70")
        self.assertEqual(chain.stages[-1].protect, "loose")


if __name__ == "__main__":
    unittest.main()
