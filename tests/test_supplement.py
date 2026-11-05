import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts, REGISTRY, get_compressor  # noqa: E402
from compressors.lexical import bm25_scores, word_cosine_scores  # noqa: E402
from compressors.sentence_select import SentenceSelectCompressor  # noqa: E402
from compressors.supplement import SUPPLEMENT_HEADER, SupplementCompressor  # noqa: E402

DOC = """## Document: cors.md

# CORS

Browsers block cross-origin requests by default. Middleware can relax this rule for chosen sites.
The preflight cache lifetime is configurable. Cookies need extra care with credentials.
Set allow_origins to the list of permitted sites. Wildcards do not work with credentials.

```python
app.add_middleware(CORSMiddleware)


def handler():
    pass
```

## Document: deps.md

# Dependencies

Dependencies are declared as function parameters. They run before the path operation.
Sub-dependencies are resolved in order. Results are cached within one request.
"""


def by_position(texts):
    """앞 단위일수록 점수가 높다 (질문과 무관한 결정적 가짜 점수)."""
    return [-float(i) for i in range(len(texts))]


def make(**kw):
    kw.setdefault("min_chars", 0)
    kw.setdefault("scorer", by_position)
    kw.setdefault("protect", "structure")
    kw.setdefault("keep_ratio", 0.3)
    return SupplementCompressor(**kw)


def run(comp, question, context=DOC):
    return comp.compress(PromptParts("", context, question))


def split(result):
    head, _, tail = result.context.partition(SUPPLEMENT_HEADER)
    return head, tail


class SupplementTest(unittest.TestCase):
    def test_base_matches_sentence_select_and_ignores_question(self):
        base = SentenceSelectCompressor(min_chars=0, scorer=by_position, protect="structure", keep_ratio=0.3)
        expected = base.compress(PromptParts("", DOC, "q")).context
        heads = set()
        for question in ("How long is the preflight cache lifetime?", "Are dependency results cached?"):
            head, tail = split(run(make(), question))
            heads.add(head.rstrip("\n"))
            self.assertTrue(tail)
        # 앞부분(압축본)은 질문이 달라도 글자 하나 다르지 않다 = 캐시되는 고정 앞부분
        self.assertEqual(heads, {expected.rstrip("\n")})

    def test_restores_only_dropped_relevant_units_verbatim(self):
        res = run(make(top_k=2), "How long is the preflight cache lifetime?")
        head, tail = split(res)
        self.assertNotIn("The preflight cache lifetime is configurable.", head)
        self.assertIn("- [cors.md] The preflight cache lifetime is configurable.", tail)
        restored = [row["text"] for row in res.info["supplement"]]
        self.assertLessEqual(len(restored), 2)
        for text in restored:
            self.assertIn(text, DOC)          # 원문 글자 그대로
            self.assertNotIn(text, head)      # 이미 남은 문장은 다시 붙이지 않는다

    def test_no_overlap_means_no_supplement(self):
        res = run(make(), "zzz qqq")
        self.assertNotIn(SUPPLEMENT_HEADER, res.context)
        self.assertEqual(res.info["supplement_units"], 0)

    def test_supplement_keeps_document_order(self):
        res = run(make(top_k=5), "cached requests credentials")
        order = [(row["doc_index"], row["unit_index"]) for row in res.info["supplement"]]
        lines = [line for line in split(res)[1].splitlines() if line.startswith("- [")]
        self.assertEqual(len(lines), len(order))
        self.assertTrue(lines[0].startswith("- [cors.md]"))
        self.assertTrue(lines[-1].startswith("- [deps.md]"))

    def test_code_blocks_keep_blank_lines(self):
        head, _ = split(run(make(), "preflight"))
        self.assertIn("app.add_middleware(CORSMiddleware)\n\n\ndef handler():", head)

    def test_wcos_matches_repair_v1_relevance(self):
        # PR #57 relevance(): \w+ 소문자, 불용어 제외 단어 빈도 코사인
        q, s = "What is the preflight cache?", "The preflight cache lifetime is configurable."
        expected = 2 / (2 ** 0.5 * 4 ** 0.5)      # 질문 {preflight, cache}, 문장 {preflight, cache, lifetime, configurable}
        self.assertAlmostEqual(word_cosine_scores(q, [s])[0], expected)
        self.assertEqual(word_cosine_scores(q, ["nothing here"]), [0.0])
        self.assertGreater(bm25_scores(q, [s, "nothing here"])[0], 0)

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            SupplementCompressor(query_scorer="nope")
        with self.assertRaises(ValueError):
            SupplementCompressor(top_k=0)

    def test_registry_and_chain(self):
        for name in ("sup_bm25_loose_r70_k3", "sup_wcos_loose_r70_k5", "sup_bm25_structure_r50_k3"):
            self.assertIn(name, REGISTRY)
        chain = get_compressor("rule>sup_bm25_loose_r70_k3")
        stage = chain.stages[-1]
        self.assertEqual((stage.query_scorer, stage.protect, stage.keep_ratio, stage.top_k), ("bm25", "loose", 0.7, 3))
        self.assertTrue(stage.config()["uses_question"])
        self.assertEqual(stage.config()["base_policy_version"], "sentence-select-v1")


if __name__ == "__main__":
    unittest.main()
