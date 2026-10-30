"""
근거 보존율 (evidence_retention) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evidence_retention import item_retention, quote_kept, summarize  # noqa: E402
from grader import word_tokens  # noqa: E402

QUOTE = "`authenticate_user` still runs `verify_password(password, DUMMY_HASH)` when the user **doesn't exist**."
CTX = f"""## Document: security

Intro line that stays in the context for sure.
{QUOTE}
Closing paragraph about the user and the password."""


def kept(quote: str, ctx: str) -> int:
    return quote_kept(word_tokens(quote), word_tokens(ctx))


class QuoteKeptTest(unittest.TestCase):
    def test_full_quote_kept(self):
        self.assertEqual(kept(QUOTE, CTX), len(word_tokens(QUOTE)))

    def test_deleted_words_counted_out(self):
        ctx = "Intro. authenticate_user runs verify_password password DUMMY_HASH user exist. Closing."
        # still, when, the, doesn, t 가 지워짐
        self.assertEqual(kept(QUOTE, ctx), len(word_tokens(QUOTE)) - 5)

    def test_scattered_common_words_not_counted(self):
        ctx = " ".join(["the"] + ["filler"] * 50 + ["user"] + ["filler"] * 50 + ["when"])
        self.assertEqual(kept(QUOTE, ctx), 1)

    def test_empty(self):
        self.assertEqual(kept(QUOTE, ""), 0)
        self.assertEqual(kept("", CTX), 0)


class ItemRetentionTest(unittest.TestCase):
    def test_intact_and_full(self):
        r = item_retention(CTX, [QUOTE])
        self.assertEqual(r["retention"], 1.0)
        self.assertTrue(r["intact_all"])

    def test_word_weighted_over_quotes(self):
        short = "Intro line that stays"                 # 4 단어, 남음
        long_ = "this sentence was removed by the compressor entirely"   # 8 단어, 대부분 사라짐
        r = item_retention(CTX, [short, long_])
        self.assertFalse(r["intact_all"])
        self.assertAlmostEqual(r["retention"], (4 + r["quotes"][1]["kept"]) / 12, places=4)

    def test_no_quotes(self):
        self.assertIsNone(item_retention(CTX, []))
        self.assertIsNone(item_retention(CTX, ["**"]))


class SummarizeTest(unittest.TestCase):
    def test_lost_correct(self):
        rows = [
            {"retention": 1.0, "intact_all": True, "answer_accuracy": 1.0, "retention_rel": 1.0},
            {"retention": 0.2, "intact_all": False, "answer_accuracy": 1.0},
            {"retention": 0.1, "intact_all": False, "answer_accuracy": 0.0},
            {"retention": 0.3, "intact_all": False, "answer_accuracy": None},
        ]
        s = summarize(rows, low=0.5)
        self.assertEqual((s["n"], s["lost"], s["lost_correct"]), (4, 3, 1))
        self.assertEqual(s["accuracy_kept"], 1.0)
        self.assertEqual(s["accuracy_lost"], 0.5)
        self.assertEqual(s["retention_rel_mean"], 1.0)
        self.assertEqual(s["intact_all_rate"], 0.25)


if __name__ == "__main__":
    unittest.main()
