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

    # ---------------- on_arrival ----------------

    @staticmethod
    def _doc(i):
        return f"<documentation>\n## Document: d{i}.md\n\n# D{i}\n\nText {i}.\n\n<!-- drop {i} -->\n</documentation>"

    def _conversation(self, hc, n=4):
        """on_arrival 로 실제 대화처럼 진행: 턴마다 기준 원문 기록 + 현재 턴을 넣고 보낸 요청을 모은다."""
        hist, reqs = [SYSTEM], []
        for k in range(n):
            cur = f"{self._doc(k)}\n\nQuestion: q{k}\n\nAnswer format: f"
            reqs.append(hc.compress_history(hist, cur).messages)
            hist = hist + [{"role": "user", "content": cur}, {"role": "assistant", "content": f"answer {k}"}]
        return reqs

    def test_on_arrival_compresses_current_turn_docs_only(self):
        with mock.patch.dict(REGISTRY, {"upper": _Upper()}):
            hc = get_history_compressor("on_arrival(upper)")
            cur = f"{DOC}\n\nQuestion: now\n\nAnswer format: f"
            r = hc.compress_history(_history(2), cur)
        self.assertEqual(hc.name, "on_arrival(upper)")
        self.assertEqual(r.messages[0], SYSTEM)
        last = r.messages[-1]["content"]
        self.assertIn("SOME TEXT.", last)                                # 현재 턴 문서도 압축
        self.assertTrue(last.endswith("\n\nQuestion: now\n\nAnswer format: f"))   # 질문·형식 줄은 그대로
        self.assertIn("SOME TEXT.", r.messages[1]["content"])           # 과거 문서도 압축된 상태
        self.assertEqual(r.messages[2]["content"], "answer 0")          # assistant 그대로
        self.assertEqual(r.info["current_doc_blocks_compressed"], 1)

    def test_on_arrival_requests_are_prefix_of_next(self):
        """캐시 친화성: 턴 k 요청 + 턴 k 답변이 턴 k+1 요청의 접두부와 정확히 같다 (per_message 는 다르다)."""
        for name in ("on_arrival(rule)", "per_message(rule)"):
            reqs = self._conversation(get_history_compressor(name))
            ok = all(reqs[k + 1][:len(reqs[k]) + 1] == reqs[k] + [{"role": "assistant", "content": f"answer {k}"}]
                     for k in range(len(reqs) - 1))
            self.assertEqual(ok, name.startswith("on_arrival"), name)

    def test_on_arrival_deterministic_across_instances(self):
        """같은 문서 원문 + 같은 압축기면 새 인스턴스에서도 같은 결과 (replay 가 턴 k 기록을 다시 만들어도 같다)."""
        a = self._conversation(get_history_compressor("on_arrival(rule)"))
        b = self._conversation(get_history_compressor("on_arrival(rule)"))
        self.assertEqual(a, b)

    def test_on_arrival_never_changes_a_compressed_doc(self):
        """압축기가 호출마다 다른 결과를 내도, 한 번 압축한 문서는 이후 턴에서 같은 압축본을 쓴다."""
        class _Counter(Compressor):
            name = "counter"
            targets = ("context",)
            n = 0

            def compress_context(self, question, context):
                _Counter.n += 1
                return f"v{_Counter.n}:" + context[:5]

        with mock.patch.dict(REGISTRY, {"counter": _Counter()}):
            hc = get_history_compressor("on_arrival(counter)")
            reqs = self._conversation(hc, n=3)
        first = reqs[0][-1]["content"]
        self.assertEqual(reqs[1][1]["content"], first)
        self.assertEqual(reqs[2][1]["content"], first)
        self.assertEqual(_Counter.n, 3)                 # 문서 3개, 각 한 번씩만 압축

    def test_system_only_at_front(self):
        with self.assertRaises(ValueError):
            get_history_compressor("none").compress_history([SYSTEM, SYSTEM], "CUR")


if __name__ == "__main__":
    unittest.main()
