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


def turn(i, tt, pages=(), deps=(), tags=(), quote_page=None, quote=None, user_quote=None, question=None, extra_pages=(),
         **extra):
    """user_quote=(user_turn, quote) 면 key_fact 하나가 source=user (사용자 발화 인용)."""
    qp = quote_page or (pages[0] if pages else "p0.md")
    t = {"turn": i, "turn_type": tt, "type": "fact", "question": question or f"What about item {i}?",
         "asks": [f"item {i}"],
         "standalone_question": f"In FastAPI, what about item {i}?", "answer": "a", "key_facts": ["fact"],
         "fact_meta": [{"source": "doc", "accept_alternatives": [], "tags": list(tags)}], "key_entities": [],
         "evidence_pages": list(pages), "depends_on": list(deps),
         "evidence": [{"quote": quote or QUOTE[qp], "page": qp, "fact_idx": 0}], "alt_evidence": []}
    if user_quote:
        ut, uq = user_quote
        t["key_facts"].append("user fact")
        t["fact_meta"].append({"source": "user", "accept_alternatives": [], "tags": ["setup"] if ut == i else []})
        t["evidence"].append({"quote": uq, "user_turn": ut, "fact_idx": 1})
    for pg in extra_pages:          # 의존 채점 규칙: 그 턴 페이지 인용을 fact 0 에 더한다
        t["evidence"].append({"quote": QUOTE[pg], "page": pg, "fact_idx": 0})
    if tt == "synthesis":
        t["asks"] = [f"item {i} part {j}" for j in range(len(t["key_facts"]))]
    t.update(extra)
    return t


USER_Q2 = "Our token expiry is 17 minutes; what about item 2?"
USER_Q9 = "Change the expiry to 45 minutes; what about item 9?"


def valid():
    """19턴, 모든 규칙을 지키는 최소 시나리오."""
    T = [
        turn(0, "new", ["p0.md"], tags=["negation"]),
        turn(1, "new", ["p1.md"], tags=["confusable"]),
        turn(2, "followup", [], [1], quote_page="p1.md", question=USER_Q2, user_quote=(2, "token expiry is 17 minutes")),
        turn(3, "new", ["p2.md"], tags=["condition"]),
        turn(4, "update", [], [3], quote_page="p2.md", changes=[{"what": "x", "from": "a", "to": "b"}], affects=[6]),
        turn(5, "new", ["p3.md"]),
        turn(6, "followup", [], [4, 5], quote_page="p3.md", extra_pages=["p2.md"]),
        turn(7, "same_doc_new_topic", [], [0], quote_page="p0.md", source_turn=0,
             quote="The timeout is 30 seconds unless overridden."),
        turn(8, "new", ["p4.md"], tags=["range", "confusable"]),
        turn(9, "update", [], [8], quote_page="p4.md", changes=[{"what": "expiry", "from": "17", "to": "45"}],
             affects=[13], question=USER_Q9, user_quote=(9, "expiry to 45 minutes")),
        turn(10, "new", ["p5.md"]),
        turn(11, "same_doc_new_topic", [], [3], quote_page="p2.md", source_turn=3,
             quote="The timeout is 30 seconds unless overridden."),
        turn(12, "new", ["p6.md"]),
        turn(13, "synthesis", [], [9, 3, 0], quote_page="p0.md", user_quote=(9, "expiry to 45 minutes"), extra_pages=["p2.md"]),
        turn(14, "new", ["p7.md"]),
        turn(15, "recall", [], [2], quote_page="p1.md", user_quote=(2, "token expiry is 17 minutes")),
        turn(16, "recall", [], [5], quote_page="p3.md"),
        turn(17, "recall", [], [8], quote_page="p4.md"),
        turn(18, "synthesis", [], [12, 14, 2], quote_page="p6.md", user_quote=(2, "token expiry is 17 minutes"),
             extra_pages=["p7.md"]),
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
            lambda s: s["turns"][4].update(turn_type="followup", changes=None, affects=None))))
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



class ToolsTest(unittest.TestCase):
    def test_ratio_overflow_counts_only_long_history(self):
        from multiturn.scenario_v2 import ratio_overflow

        class P:
            @staticmethod
            def user_message(t, corpus):
                return ("x " * 2000) if t["evidence_pages"] else "q"
        s = valid()
        ro = ratio_overflow(s, CORPUS, P, lambda txt: len(txt.split()), min_history=4000)
        self.assertGreater(ro["turns_counted"], 0)
        self.assertTrue(all(r["history"] >= 4000 for r in ro["rows"]))
        self.assertLessEqual(ro["r75_overflow_rate"], ro["r25_overflow_rate"])

    def test_review_rows_and_leak(self):
        from multiturn.review_sheet import COLUMNS, rows_for
        from multiturn.scenario_v2 import leak_entities
        s = valid()
        rows = rows_for(s, {3: ["오류 예시"]})
        self.assertEqual(len(rows), len(s["turns"]))
        self.assertEqual(set(rows[0]), set(COLUMNS))
        self.assertEqual(rows[3]["auto_check"], "오류 예시")
        self.assertEqual(rows[0]["verdict"], "")
        t = dict(s["turns"][0], key_entities=["X-Cat-Dog"], question="What header did we choose?",
                 standalone_question="Which header, X-Cat-Dog?")
        self.assertEqual(leak_entities(t), ["X-Cat-Dog"])


class UserSourceAndLeakTest(unittest.TestCase):
    """2026-11-28 설계 변경: 사용자 고유 값(source=user), 누설 검사, 질문 크기, 기호 entity."""

    def _errs(self, mutate):
        s = valid()
        mutate(s)
        return validate_scenario_v2(s)

    def test_user_evidence_accepted_by_v1_validator_only_for_v2(self):
        s = valid()
        self.assertEqual(validate_scenario(s), [])
        del s["schema_version"]
        self.assertTrue(any("evidence 항목은" in e for e in validate_scenario(s)))

    def test_user_quote_must_be_in_chain_and_verbatim(self):
        self.assertTrue(any("사슬 밖" in e for e in self._errs(
            lambda s: s["turns"][15]["evidence"][1].update(user_turn=9))))
        self.assertTrue(any("질문에 없음" in e for e in self._errs(
            lambda s: s["turns"][15]["evidence"][1].update(quote="expiry is 99 minutes"))))

    def test_source_needs_matching_evidence(self):
        self.assertTrue(any("source=user) 에 사용자 발화 근거" in e for e in self._errs(
            lambda s: s["turns"][15]["evidence"].pop(1))))
        self.assertTrue(any("source 는" in e for e in self._errs(
            lambda s: s["turns"][0]["fact_meta"][0].pop("source"))))

    def test_user_share_range_and_user_update(self):
        def no_user(s):
            for k in (13, 15):
                s["turns"][k]["fact_meta"][1]["source"] = "doc"
                s["turns"][k]["evidence"][1] = {"quote": QUOTE["p0.md"], "page": "p0.md", "fact_idx": 1}
        errs = self._errs(no_user)
        self.assertTrue(any("source=user 1/8" in e for e in errs))

        def all_user(s):
            for k in (16, 17, 18):
                q = (2, "token expiry is 17 minutes")
                s["turns"][k]["depends_on"] = sorted(set(s["turns"][k]["depends_on"]) | {2})
                s["turns"][k]["fact_meta"][0]["source"] = "user"
                s["turns"][k]["evidence"][0] = {"quote": q[1], "user_turn": q[0], "fact_idx": 0}
            fill_derived(s)
        self.assertTrue(any("source=user 6/8" in e for e in self._errs(all_user)))

        def no_user_update(s):
            t = s["turns"][9]
            t["fact_meta"][1]["source"] = "doc"
            t["evidence"][1] = {"quote": QUOTE["p4.md"], "page": "p4.md", "fact_idx": 1}
        self.assertTrue(any("user key_fact 를 가진 update 턴 0개" in e for e in self._errs(no_user_update)))

    def test_leak_is_error(self):
        def leak(s):
            t = s["turns"][15]
            t["key_entities"] = ["17 minutes"]
            t["standalone_question"] = "With a 17 minutes expiry, what is item 15?"
        self.assertTrue(any("답 누설" in e for e in self._errs(leak)))

    def test_question_size(self):
        self.assertTrue(any("3가지를 묻습니다" in e for e in self._errs(
            lambda s: s["turns"][0].update(asks=["a", "b", "c"]))))
        self.assertFalse(any("가지를 묻습니다" in e for e in self._errs(lambda s: s["turns"][18].update(asks=["a", "b", "c"]))))
        self.assertTrue(any("asks" in e for e in self._errs(lambda s: s["turns"][0].pop("asks"))))

        def four_facts(s):
            t = s["turns"][0]
            t["key_facts"] = ["f"] * 4
            t["fact_meta"] = [{"source": "doc", "accept_alternatives": [], "tags": []} for _ in range(4)]
            t["evidence"] = [{"quote": QUOTE["p0.md"], "page": "p0.md", "fact_idx": i} for i in range(4)]
        self.assertTrue(any("key_facts 4개" in e for e in self._errs(four_facts)))

    def test_grounding_user_entities_and_symbol_warning(self):
        s = valid()
        s["turns"][15]["key_entities"] = ["17 minutes", "/"]
        warns = []
        self.assertEqual(check_grounding_v2(s, CORPUS, warns), [])
        self.assertEqual(len(warns), 1)
        s["turns"][16]["key_entities"] = ["17 minutes"]           # 턴 16 의 사슬에는 턴 2 가 없다
        self.assertTrue(any("17 minutes" in e for e in check_grounding_v2(s, CORPUS)))

    def test_report_source_fields(self):
        rep = rule_report(valid(), CORPUS)
        self.assertEqual(rep["user_share_recall_synthesis"], (3, 8))
        self.assertEqual(rep["facts_by_source"]["user"], 5)
        self.assertEqual([u["user_source"] for u in rep["updates"]], [False, True])


class ClosedBookV2Test(unittest.TestCase):
    def test_grounded_messages_use_experiment_prompt(self):
        from multiturn.closed_book_v2 import grounded_messages
        from multiturn.prompt import load_mt_prompt
        p = load_mt_prompt("v2")
        t = valid()["turns"][15]
        m = grounded_messages(t, p)
        self.assertEqual(m[0], {"role": "system", "content": p.system})
        self.assertIn("NOT FOUND", m[0]["content"])
        self.assertEqual(m[1]["content"], p.user_text(t["standalone_question"], "fact", None))
        self.assertNotIn("<documentation>", m[1]["content"])

    def test_check_scenario_with_fakes(self):
        from multiturn import closed_book_v2 as cb
        from multiturn.prompt import load_mt_prompt

        class R:
            def __init__(self, text):
                self.text, self.prompt_tokens, self.completion_tokens = text, 10, 2
                self.finish_reason, self.model, self.usage_source = "stop", "fake", "api"

        class Answer:
            def ask(self, prompt, system=None):
                return R("UNKNOWN")

            def chat(self, messages):
                return R("NOT FOUND")

            def sampling_info(self):
                return {"model": "fake"}

        class Judge:
            model = "judge"

        s = valid()
        s["turns"][0]["closed_book"] = {"correct": True}
        rows = []
        out = cb.check_scenario(s, Answer(), Judge(), "rid", rows, load_mt_prompt("v2"))
        self.assertEqual((out["knowledge_correct"], out["grounded_correct"]), (0, 0))
        self.assertEqual(out["grounded_not_found"], len(s["turns"]))
        t = s["turns"][0]
        self.assertNotIn("closed_book", t)
        self.assertEqual(t["closed_book_grounded"]["judge_prompt"][0], "fact_judge_v3")
        self.assertTrue(t["closed_book_knowledge"]["unknown"])
        self.assertEqual(len(rows), 2 * len(s["turns"]))


class ReviewRulesTest(unittest.TestCase):
    """2026-11-28 검수 결정: setup, synthesis 1:1·열린 요청 금지, 대안 근거, 의존 채점, 한 턴 한 주제."""

    def _errs(self, mutate):
        s = valid()
        mutate(s)
        return validate_scenario_v2(s)

    def test_fixture_valid(self):
        self.assertEqual(validate_scenario_v2(valid()), [])

    def test_setup_required_and_only_where_allowed(self):
        self.assertTrue(any("setup 필요" in e for e in self._errs(
            lambda s: s["turns"][2]["fact_meta"][1]["tags"].remove("setup"))))
        self.assertTrue(any("setup 태그는" in e for e in self._errs(
            lambda s: s["turns"][0]["fact_meta"][0]["tags"].append("setup"))))

    def test_needs_non_setup_fact(self):
        def only_setup(s):
            t = s["turns"][2]
            t["key_facts"] = t["key_facts"][1:]
            t["fact_meta"] = t["fact_meta"][1:]
            t["evidence"] = [dict(e, fact_idx=0) for e in t["evidence"] if e["fact_idx"] == 1]
        self.assertTrue(any("setup 이 아닌 key_fact 가 없습니다" in e for e in self._errs(only_setup)))

    def test_synthesis_one_to_one_and_open_ended(self):
        self.assertTrue(any("1:1" in e for e in self._errs(lambda s: s["turns"][18].update(asks=["only one"]))))
        self.assertTrue(any("열린 요청" in e for e in self._errs(
            lambda s: s["turns"][18].update(question="Give me a test plan for item 18?"))))

    def test_alternative_needs_evidence_user_or_page(self):
        def alt_user(s):
            t = s["turns"][15]
            t["fact_meta"][1]["accept_alternatives"] = ["seventeen minutes"]
            t["alt_evidence"] = [{"quote": "token expiry is 17 minutes", "user_turn": 2, "fact_idx": 1, "alt_idx": 0}]
        self.assertEqual(self._errs(alt_user), [])

        def alt_bad(s):
            alt_user(s)
            s["turns"][15]["alt_evidence"][0]["quote"] = "not said"
        self.assertTrue(any("대안" in e for e in self._errs(alt_bad)))

    def test_dependency_must_be_scored(self):
        self.assertTrue(any("depends_on 턴 4" in e for e in self._errs(
            lambda s: s["turns"][6].update(evidence=s["turns"][6]["evidence"][:1]))))

    def test_topic_warning_and_suspects(self):
        from multiturn.scenario_v2 import suspect_reasons, topic_warnings
        s = valid()
        s["turns"][0]["evidence_pages"] = ["security/a.md", "errors/b.md"]
        self.assertEqual(len(topic_warnings(s)), 1)
        t = s["turns"][0]
        t["question"] = "x" * 401
        t["closed_book_grounded"] = {"accuracy_main": 0.5}
        r = suspect_reasons(s, t)
        self.assertTrue(any("질문이 김" in x for x in r) and any("grounded" in x for x in r))

    def test_closed_book_main_accuracy_skips_setup(self):
        from multiturn.closed_book_v2 import main_accuracy
        t = valid()["turns"][2]             # fact 0 doc, fact 1 user setup
        self.assertEqual(main_accuracy(t, {"accuracy": 0.5, "fact_results": [True, False]}), 1.0)
        self.assertEqual(main_accuracy(t, {"accuracy": 0.5, "fact_results": [False, True]}), 0.0)
        self.assertEqual(main_accuracy(t, {"accuracy": 0.0, "fact_results": []}), 0.0)
        self.assertIsNone(main_accuracy(t, {"accuracy": None, "fact_results": []}))


if __name__ == "__main__":
    unittest.main()
