"""
multiturn/scenario.py (스키마 검증·근거 확인) 와 history_compressors (압축기 3종·체인·압축 대상 범위).
네트워크 없음. 파일럿 시나리오 근거 확인은 저장소의 위키(data/openwiki/en)를 읽는다.

    python -m unittest tests.test_mt_scenario_and_history
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compressors import REGISTRY, Compressor  # noqa: E402
from multiturn.history_compressors import (  # noqa: E402
    get_history_compressor, split_compressor_list, split_top_level,
)
from multiturn.scenario import (  # noqa: E402
    check_grounding, grounding_pages, load_scenarios, validate_scenario,
)

PILOT = ROOT / "data" / "evalsets" / "multiturn-v1"


def _turn(i, tt="new", deps=(), pages=("a.md",)):
    return {"turn": i, "turn_type": tt, "type": "fact", "question": f"q{i}", "answer": f"a{i}",
            "key_facts": [f"fact {i}"], "key_entities": [], "evidence_pages": list(pages),
            "depends_on": list(deps), "evidence": [{"quote": "x", "page": "a.md", "fact_idx": 0}]}


def _scenario():
    return {"scenario_id": "t", "title": "t", "topic": "t", "status": "draft", "turns": [
        _turn(0), _turn(1, "followup", [0], ()), _turn(2, "recall", [0], ()), _turn(3, "recall", [1], ()),
        _turn(4, "synthesis", [0, 1], ()), _turn(5, "synthesis", [2, 3], ())]}


class ScenarioTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_scenario(_scenario()), [])

    def test_depends_on_same_or_future_turn(self):
        for bad in (2, 3):
            s = _scenario()
            s["turns"][2]["depends_on"] = [bad]
            self.assertTrue(any("현재·미래" in e for e in validate_scenario(s)), bad)

    def test_min_recall_synthesis_and_rules(self):
        s = _scenario()
        s["turns"][3]["turn_type"] = "followup"
        self.assertTrue(any("recall 턴이 1개" in e for e in validate_scenario(s)))
        s = _scenario()
        s["turns"][2]["evidence_pages"] = ["a.md"]
        self.assertTrue(any("다시 첨부하지" in e for e in validate_scenario(s)))
        s = _scenario()
        s["turns"][0]["evidence"] = []
        self.assertTrue(any("근거 인용문이 없는 key_fact" in e for e in validate_scenario(s)))
        s = _scenario()
        s["turns"][1]["turn"] = 7
        self.assertTrue(any("turn 번호" in e for e in validate_scenario(s)))

    def test_grounding_pages_follow_dependencies(self):
        s = _scenario()
        s["turns"][3]["evidence_pages"] = []
        s["turns"][1]["evidence_pages"] = ["b.md"]
        self.assertEqual(sorted(grounding_pages(s, 3)), ["a.md", "b.md"])

    def test_pilot_scenarios_valid_and_grounded(self):
        from corpus import load_corpus
        corpus = load_corpus()
        scenarios = load_scenarios(PILOT)
        self.assertEqual(len(scenarios), 3)
        for s in scenarios:
            self.assertEqual(s["status"], "draft")
            self.assertEqual(validate_scenario(s), [], s["scenario_id"])
            self.assertEqual(check_grounding(s, corpus), [], s["scenario_id"])
            self.assertTrue(7 <= len(s["turns"]) <= 10)

    def test_grounding_detects_missing_quote(self):
        from corpus import load_corpus
        s = copy.deepcopy(load_scenarios(PILOT)[0])
        s["turns"][0]["evidence"][0]["quote"] = "this sentence is not in the page"
        s["turns"][0]["key_entities"].append("NoSuchEntityXYZ")
        errs = check_grounding(s, load_corpus())
        self.assertTrue(any("인용문이" in e for e in errs))
        self.assertTrue(any("NoSuchEntityXYZ" in e for e in errs))


DOC = "<documentation>\n## Document: a.md\n\n# A\n\nSome text.\n\n<!-- comment to drop -->\n</documentation>"
SYSTEM = {"role": "system", "content": "SYS"}


def _history(n_turns):
    h = [SYSTEM]
    for i in range(n_turns):
        h.append({"role": "user", "content": f"{DOC}\n\nQuestion: q{i}\n\nAnswer format: f"})
        h.append({"role": "assistant", "content": f"answer {i}"})
    return h


class _Upper(Compressor):
    name = "upper"
    targets = ("context",)

    def compress_context(self, question, context):
        self.add_llm_tokens(3, 1)
        return context.upper()


class _QuestionOnly(Compressor):
    name = "qonly"
    targets = ("question",)

    def compress_question(self, question, context):
        return question


class HistoryCompressorTest(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split_top_level("window(2)>per_message(rule>llmlingua2)"),
                         ["window(2)", "per_message(rule>llmlingua2)"])
        self.assertEqual(split_compressor_list("none,window(2),per_message(a>b)"),
                         ["none", "window(2)", "per_message(a>b)"])
        for bad in ("window(2", "a>>b", "window(x)", "unknown"):
            with self.assertRaises((ValueError, KeyError)):
                get_history_compressor(bad)

    def test_none_and_window(self):
        h = _history(3)
        r = get_history_compressor("none").compress_history(h, "CUR")
        self.assertEqual(r.messages, h + [{"role": "user", "content": "CUR"}])
        r = get_history_compressor("window(1)").compress_history(h, "CUR")
        self.assertEqual([m["content"] for m in r.messages][1:-1], [h[5]["content"], "answer 2"])
        r = get_history_compressor("window(0)").compress_history(h, "CUR")
        self.assertEqual(r.messages, [SYSTEM, {"role": "user", "content": "CUR"}])

    def test_per_message_targets_only_past_doc_blocks(self):
        with mock.patch.dict(REGISTRY, {"upper": _Upper()}):
            hc = get_history_compressor("per_message(upper)")
            cur = f"{DOC}\n\nQuestion: now\n\nAnswer format: f"
            r = hc.compress_history(_history(2), cur)
        self.assertEqual(r.messages[0], SYSTEM)                        # system 그대로
        self.assertEqual(r.messages[-1]["content"], cur)                # 현재 턴(문서 포함) 그대로
        past = r.messages[1:-1]
        self.assertIn("SOME TEXT.", past[0]["content"])                 # 과거 문서 블록은 압축
        self.assertIn("Question: q0", past[0]["content"])               # 질문 줄은 그대로
        self.assertTrue(past[0]["content"].startswith("<documentation>\n"))
        self.assertEqual(past[1]["content"], "answer 0")                # assistant 그대로
        self.assertEqual((r.llm_prompt_tokens, r.llm_completion_tokens), (6, 2))   # 문서 2개 × (3, 1)

    def test_per_message_rejects_non_context(self):
        with mock.patch.dict(REGISTRY, {"qonly": _QuestionOnly()}):
            with self.assertRaises(ValueError):
                get_history_compressor("per_message(qonly)")

    def test_chain(self):
        with mock.patch.dict(REGISTRY, {"upper": _Upper()}):
            r = get_history_compressor("window(1)>per_message(upper)").compress_history(_history(3), "CUR")
        self.assertEqual(len(r.messages), 4)
        self.assertIn("SOME TEXT.", r.messages[1]["content"])
        self.assertEqual((r.llm_prompt_tokens, r.llm_completion_tokens), (3, 1))

    def test_rule_per_message_matches_single_turn_rule(self):
        """어댑터는 기존 rule 압축기를 문서 블록에 그대로 적용한다 (같은 입력이면 같은 출력)."""
        from compressors import PromptParts, get_compressor
        from multiturn.prompt import DOC_BLOCK_RE
        h = _history(1)
        r = get_history_compressor("per_message(rule)").compress_history(h, "CUR")
        doc = DOC_BLOCK_RE.search(h[1]["content"]).group(2)
        want = get_compressor("rule").compress(PromptParts(system="", context=doc, question="q0")).context
        self.assertEqual(DOC_BLOCK_RE.search(r.messages[1]["content"]).group(2), want)

    def test_system_only_at_front(self):
        with self.assertRaises(ValueError):
            get_history_compressor("none").compress_history([SYSTEM, SYSTEM], "CUR")


if __name__ == "__main__":
    unittest.main()
