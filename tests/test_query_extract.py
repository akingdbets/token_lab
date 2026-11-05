import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts, REGISTRY, get_compressor  # noqa: E402
from compressors.query_extract import QueryExtractCompressor, bm25_scores, terms  # noqa: E402

DOC = """## Document: cors.md

# CORS

Browsers block cross-origin requests by default. Middleware can relax this rule for chosen sites.
The preflight cache lifetime is configurable. Cookies need extra care with credentials.
Set allow_origins to the list of permitted sites. Wildcards do not work together with credentials.

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```
"""


def make(**kw):
    kw.setdefault("min_chars", 0)
    kw.setdefault("protect", "structure")
    return QueryExtractCompressor(**kw)


class TermsTest(unittest.TestCase):
    def test_identifiers_are_kept_whole_and_split(self):
        t = terms("How does create_access_token use CORSMiddleware?")
        for term in ("create_access_token", "create", "access", "token", "corsmiddleware", "cors", "middleware"):
            self.assertIn(term, t)
        self.assertNotIn("how", t)

    def test_bm25_prefers_matching_unit(self):
        scores = bm25_scores("allow_origins credentials", ["nothing here", "set allow_origins now", "credentials"])
        self.assertEqual(scores[0], 0.0)
        self.assertGreater(scores[1], 0)
        self.assertGreater(scores[2], 0)


class QueryExtractTest(unittest.TestCase):
    def run_q(self, comp, question):
        return comp.compress(PromptParts("", DOC, question))

    def test_keeps_question_relevant_sentences(self):
        res = self.run_q(make(keep_ratio=0.3), "What does allow_origins set?")
        self.assertIn("Set allow_origins to the list of permitted sites.", res.context)
        self.assertNotIn("Browsers block cross-origin requests by default.", res.context)
        # 보호 단위(제목, 코드 블록, 문서 경계)는 남는다
        for kept in ("## Document: cors.md", "# CORS", 'allow_origins=["*"]'):
            self.assertIn(kept, res.context)
        self.assertTrue(res.info["uses_question"])
        self.assertEqual(res.info["documents"][0]["status"], "select")

    def test_different_questions_keep_different_sentences(self):
        comp = make(keep_ratio=0.3)
        a = self.run_q(comp, "What does allow_origins set?").context
        b = self.run_q(comp, "How long is the preflight cache lifetime?").context
        self.assertNotEqual(a, b)
        self.assertIn("The preflight cache lifetime is configurable.", b)

    def test_threshold_mode(self):
        comp = make(min_score=0.99)
        res = self.run_q(comp, "preflight cache lifetime")
        self.assertEqual(comp.name, "qx_bm25_structure_t99")
        self.assertIn("The preflight cache lifetime is configurable.", res.context)
        self.assertNotIn("Cookies need extra care", res.context)
        # 기준점 0 이면 모두 남는다
        self.assertEqual(self.run_q(make(min_score=0.0), "anything").context, DOC)

    def test_registry_and_chain(self):
        for name in ("qx_bm25_loose_r50", "qx_bm25_structure_r30"):
            self.assertIn(name, REGISTRY)
        self.assertFalse(any(name.startswith("qx_emb_") for name in REGISTRY))
        chain = get_compressor("rule>qx_bm25_loose_r50")
        self.assertEqual(chain.stages[-1].config()["uses_question"], True)
        self.assertEqual(chain.stages[-1].config()["scorer"], "bm25")


if __name__ == "__main__":
    unittest.main()
