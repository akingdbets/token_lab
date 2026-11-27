"""multiturn-v2 시나리오 규칙 (scenario_v2) 과 v1 검증 동작 유지 (네트워크 없음)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multiturn.scenario import TURN_TYPES_V1, validate_scenario  # noqa: E402
from multiturn.scenario_v2 import (  # noqa: E402
    check_grounding_v2, fill_derived, rule_report, section_of, validate_scenario_v2,
)

PAGE_A = "---\ntitle: Alpha Settings Reference\n---\n\n# Alpha Settings Reference\n\n## Limits\n\nThe limit is 10 by default.\n\n## Timeouts\n\nThe timeout is 30 seconds unless overridden.\n"
PAGE_B = "---\ntitle: Beta Responses Overview\n---\n\n# Beta Responses Overview\n\n## Codes\n\nIt returns 404 when missing.\n"


class FakeDoc:
    def __init__(self, text):
        self.text = text


class FakeCorpus:
    def __init__(self, pages):
        self.pages = pages

    def get(self, page):
        if page not in self.pages:
            raise KeyError(page)
        return FakeDoc(self.pages[page])


CORPUS = FakeCorpus({f"p{i}.md": PAGE_A if i % 2 == 0 else PAGE_B for i in range(10)})
QUOTE = {"p%d.md" % i: ("The limit is 10 by default." if i % 2 == 0 else "It returns 404 when missing.") for i in range(10)}


def turn(i, tt, pages=(), deps=(), tags=(), quote_page=None, quote=None, **extra):
    qp = quote_page or (pages[0] if pages else "p0.md")
    t = {"turn": i, "turn_type": tt, "type": "fact", "question": f"What about item {i}?",
         "standalone_question": f"In FastAPI, what about item {i}?", "answer": "a", "key_facts": ["fact"],
         "fact_meta": [{"accept_alternatives": [], "tags": list(tags)}], "key_entities": [],
         "evidence_pages": list(pages), "depends_on": list(deps),
         "evidence": [{"quote": quote or QUOTE[qp], "page": qp, "fact_idx": 0}], "alt_evidence": []}
    t.update(extra)
    return t


def valid():
    """19턴, 모든 규칙을 지키는 최소 시나리오."""
    T = [
        turn(0, "new", ["p0.md"], tags=["negation"]),
        turn(1, "new", ["p1.md"], tags=["confusable"]),
        turn(2, "followup", [], [1], quote_page="p1.md"),
        turn(3, "new", ["p2.md"], tags=["condition"]),
        turn(4, "update", [], [3], quote_page="p2.md", changes=[{"what": "x", "from": "a", "to": "b"}], affects=[6]),
        turn(5, "new", ["p3.md"]),
        turn(6, "followup", [], [4, 5], quote_page="p3.md"),
        turn(7, "same_doc_new_topic", [], [0], quote_page="p0.md", source_turn=0,
             quote="The timeout is 30 seconds unless overridden."),
        turn(8, "new", ["p4.md"], tags=["range", "confusable"]),
        turn(9, "update", [], [8], quote_page="p4.md", changes=[{"what": "y", "from": "c", "to": "d"}], affects=[13]),
        turn(10, "new", ["p5.md"]),
        turn(11, "same_doc_new_topic", [], [3], quote_page="p2.md", source_turn=3,
             quote="The timeout is 30 seconds unless overridden."),
        turn(12, "new", ["p6.md"]),
        turn(13, "synthesis", [], [9, 3, 0], quote_page="p0.md"),
        turn(14, "new", ["p7.md"]),
        turn(15, "recall", [], [1], quote_page="p1.md"),
        turn(16, "recall", [], [5], quote_page="p3.md"),
        turn(17, "recall", [], [8], quote_page="p4.md"),
        turn(18, "synthesis", [], [12, 14], quote_page="p6.md"),
    ]
    s = {"schema_version": 2, "scenario_id": "v2_t", "title": "t", "topic": "t", "status": "draft",
         "bundle": [f"p{i}.md" for i in range(8)], "generation": {"model": "m"}, "turns": T}
    return fill_derived(s)


class V1CompatTest(unittest.TestCase):
    def test_v1_rejects_new_types(self):
        s = valid()
        del s["schema_version"]
        errs = validate_scenario(s)
        self.assertTrue(any("turn_type 은" in e and str(TURN_TYPES_V1) in e for e in errs))

    def test_v1_pilot_still_valid(self):
        from multiturn.scenario import load_scenarios
        for s in load_scenarios(Path(__file__).resolve().parents[1] / "data" / "evalsets" / "multiturn-v1"):
            self.assertEqual(validate_scenario(s), [], s["scenario_id"])


class V2RulesTest(unittest.TestCase):
    def test_valid(self):
        s = valid()
        self.assertEqual(validate_scenario_v2(s), [])
        self.assertEqual(check_grounding_v2(s, CORPUS), [])
        self.assertEqual(validate_scenario(s), [])               # replay 가 읽을 때도 통과

    def _errs(self, mutate):
        s = valid()
        mutate(s)
        return validate_scenario_v2(s)

    def test_counts_and_distance(self):
        self.assertTrue(any("update 턴 1개" in e for e in self._errs(
            lambda s: s["turns"][9].update(turn_type="followup", changes=None, affects=None))))
        def near(s):
            for k in (15, 16, 17):
                s["turns"][k]["depends_on"] = [k - 1]
            fill_derived(s)
        self.assertTrue(any("거리 6 이상 recall" in e for e in self._errs(near)))

    def test_recall_distance_must_be_derived(self):
        self.assertTrue(any("recall_distance" in e for e in self._errs(lambda s: s["turns"][15].update(recall_distance=1))))

    def test_update_rules(self):
        self.assertTrue(any("depends_on 에 update 턴" in e for e in self._errs(
            lambda s: s["turns"][6].update(depends_on=[5]) or fill_derived(s))))
        self.assertTrue(any("changes" in e for e in self._errs(lambda s: s["turns"][4].update(changes=[]))))

    def test_same_doc_rules(self):
        self.assertTrue(any("source_turn" in e for e in self._errs(lambda s: s["turns"][7].update(source_turn=None))))
        s = valid()
        s["turns"][7]["evidence"][0]["quote"] = "The limit is 10 by default."     # 첨부 턴과 같은 소제목
        self.assertTrue(any("같은 부분" in e for e in check_grounding_v2(s, CORPUS)))

    def test_source_cue_and_title(self):
        self.assertTrue(any("출처 단서" in e for e in self._errs(
            lambda s: s["turns"][10].update(question="Going back to the JWT tutorial, what was it?"))))
        s = valid()
        s["turns"][10]["question"] = "In Alpha Settings Reference, what was the limit?"
        self.assertTrue(any("페이지 제목" in e for e in check_grounding_v2(s, CORPUS)))

    def test_tags_and_alternatives(self):
        self.assertTrue(any("confusable" in e for e in self._errs(
            lambda s: [m["tags"].remove("confusable") for t in s["turns"] for m in t["fact_meta"] if "confusable" in m["tags"]])))
        self.assertTrue(any("대안 0 에 근거" in e for e in self._errs(
            lambda s: s["turns"][0]["fact_meta"][0]["accept_alternatives"].append("alt"))))
        s = valid()
        s["turns"][0]["fact_meta"][0]["accept_alternatives"].append("alt")
        s["turns"][0]["alt_evidence"].append({"quote": "not in page", "page": "p0.md", "fact_idx": 0, "alt_idx": 0})
        self.assertEqual(validate_scenario_v2(s), [])
        self.assertTrue(any("대안 인용문" in e for e in check_grounding_v2(s, CORPUS)))

    def test_placement(self):
        self.assertTrue(any("턴 0·1" in e for e in self._errs(lambda s: s["turns"][1].update(turn_type="followup", depends_on=[0]))))

    def test_section_of_and_report(self):
        self.assertEqual(section_of(PAGE_A, "The timeout is 30 seconds"), "Timeouts")
        self.assertEqual(section_of(PAGE_A, "The limit   is 10"), "Limits")
        self.assertIsNone(section_of(PAGE_A, "nowhere"))
        rep = rule_report(valid(), CORPUS)
        self.assertEqual(rep["type_counts"]["update"], 2)
        self.assertEqual(rep["same_doc"][0]["sections"], ["Timeouts"])
        self.assertEqual(rep["same_doc"][0]["source_sections"], ["Limits"])


if __name__ == "__main__":
    unittest.main()
