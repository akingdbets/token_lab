"""
문서 중복도 분석(src/redundancy.py) 테스트: 위치 세기, 코드/설명 구분, 근거 자리 판정, trial 상태, Fisher 검정.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from experiment import find_normalized, iter_normalized  # noqa: E402
from redundancy import (code_ranges, core_positions, core_state, evidence_excerpts, evidence_words,  # noqa: E402
                        fisher_p, needle_spans, outside_evidence, quote_window, trial_state)

RAW = """## Document: a

Use `Depends` with yield. The lifespan starts when the app starts.

```python
from asgi_lifespan import LifespanManager
async with LifespanManager(app) as manager:
    pass
```

Install asgi-lifespan to test the lifespan.
"""


def item(answer, quote, entities=None):
    return {"answer": answer, "key_entities": entities, "evidence": [{"quote": quote}]}


class SpanTest(unittest.TestCase):
    def test_iter_normalized_finds_every_position(self):
        spans = list(iter_normalized(RAW, "asgi-lifespan"))
        self.assertEqual([RAW[s:e] for s, e in spans], ["asgi_lifespan", "asgi-lifespan"])
        self.assertEqual(find_normalized(RAW, "asgi-lifespan"), "asgi_lifespan")

    def test_needle_spans_strips_article_and_dedupes(self):
        self.assertEqual(len(needle_spans(RAW, "The lifespan")), 2)      # 떼면 한 단어라 "the lifespan" 그대로
        self.assertEqual(len(needle_spans(RAW, "The lifespan starts")), 1)  # "lifespan starts"
        self.assertEqual(len(needle_spans(RAW, "LifespanManager")), 2)

    def test_code_ranges(self):
        (s, e), = code_ranges(RAW)
        self.assertTrue(RAW[s:e].startswith("```python") and RAW[s:e].rstrip().endswith("```"))
        self.assertEqual(code_ranges("a\n```\nx = 1\n"), [(2, 12)])   # 닫히지 않은 펜스는 끝까지

    def test_core_positions_code_and_prose(self):
        pos = core_positions(RAW, item("asgi-lifespan", "x"))
        self.assertEqual(pos, {"total": 2, "code": 1, "prose": 1})

    def test_long_answer_uses_kth_entity(self):
        it = item("Use the LifespanManager from asgi-lifespan with the app in tests", "x",
                  ["LifespanManager", "asgi-lifespan", "missing_thing"])
        # 개체 위치 수 2, 2, 0 → 절반 규칙 k=2 번째로 많은 값 2
        self.assertEqual(core_positions(RAW, it)["total"], 2)


class EvidenceTest(unittest.TestCase):
    def test_quote_window(self):
        ctx = "a b install asgi lifespan to test the lifespan c".split()
        self.assertEqual(quote_window("install asgi lifespan to test the lifespan".split(), ctx), (2, 9))
        self.assertIsNone(quote_window(["zzz"], ctx))

    def test_outside_evidence_on_raw_and_compressed(self):
        it = item("asgi-lifespan", "Install asgi-lifespan to test the lifespan.")
        ev = evidence_words(RAW, it)
        self.assertEqual(core_positions(RAW, it, outside_evidence(RAW, RAW, ev))["total"], 1)   # 코드의 import 만
        # 근거 문장의 단어 일부만 남은 압축 문맥: 남은 정답은 근거 자리
        comp = RAW.replace("from asgi_lifespan import LifespanManager\n", "").replace(
            "Install asgi-lifespan to test the lifespan.", "asgi-lifespan lifespan.")
        self.assertEqual(core_positions(comp, it, outside_evidence(comp, RAW, ev))["total"], 0)

    def test_trial_states(self):
        it = item("asgi-lifespan", "Install asgi-lifespan to test the lifespan.")
        ev = evidence_words(RAW, it)
        self.assertEqual(trial_state(it, RAW, RAW, ev)["state"], "a")
        gone = RAW.replace("Install asgi-lifespan to test the lifespan.", "")
        st = trial_state(it, gone, RAW, ev)
        self.assertEqual((st["state"], st["where"]), ("b", "code"))   # 보존율은 흩어진 lifespan 으로 부분 점수
        self.assertLess(st["evidence"], 0.5)
        in_place = RAW.replace("from asgi_lifespan import LifespanManager\n", "").replace(
            "Install asgi-lifespan to test the lifespan.", "asgi-lifespan")
        self.assertEqual(trial_state(it, in_place, RAW, ev)["where"], "evidence")
        none_left = gone.replace("from asgi_lifespan import LifespanManager\n", "")
        self.assertEqual(trial_state(it, none_left, RAW, ev)["state"], "c")


class CoreStateTest(unittest.TestCase):
    QUOTE = "Install asgi-lifespan to test the lifespan."

    def setUp(self):
        self.it = item("asgi-lifespan", self.QUOTE)
        self.ev = evidence_words(RAW, self.it)

    def test_in_evidence_is_A_even_if_quote_mostly_deleted(self):
        comp = RAW.replace(self.QUOTE, "asgi-lifespan lifespan.")
        self.assertEqual(core_state(self.it, comp, RAW, self.ev)["cstate"], "A")

    def test_only_elsewhere_is_B_with_location(self):
        comp = RAW.replace(self.QUOTE, "")
        self.assertEqual(core_state(self.it, comp, RAW, self.ev), {"cstate": "B", "cwhere": "code"})

    def test_gone_everywhere_is_C(self):
        comp = RAW.replace(self.QUOTE, "").replace("from asgi_lifespan import LifespanManager\n", "")
        self.assertEqual(core_state(self.it, comp, RAW, self.ev)["cstate"], "C")

    def test_evidence_excerpts_side_by_side(self):
        comp = RAW.replace(self.QUOTE, "Install asgi-lifespan lifespan.")
        (e,) = evidence_excerpts(self.it, comp, RAW)
        self.assertEqual(e, {"quote": self.QUOTE, "compressed": "Install asgi-lifespan lifespan"})


class FisherTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(fisher_p(1, 9, 11, 3), 0.002759, places=5)   # 위키백과 Fisher's exact test 예
        self.assertAlmostEqual(fisher_p(3, 1, 1, 3), 0.485714, places=5)    # 차 맛보기 (34/70)
        self.assertEqual(fisher_p(5, 0, 5, 0), 1.0)


if __name__ == "__main__":
    unittest.main()
