import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compressors import PromptParts  # noqa: E402
from compressors import telegraph as T  # noqa: E402

PAGE = """Use `APIRouter` to split apps. Since FastAPI 0.95.0 use `Annotated`.

```python
import fastapi
app = fastapi.FastAPI()
```

The default is "Successful Response". Install starlette-graphene3.
"""


class TelegraphTest(unittest.TestCase):
    def test_mask_and_restore_code_byte_identical(self):
        masked, blocks = T.mask_code(PAGE)
        self.assertEqual(len(blocks), 1)
        self.assertIn("⟦CODE-0⟧", masked)
        self.assertNotIn("import fastapi", masked)
        te = "H1: ROUTING\n`APIRouter` SPLITS APPS\n⟦CODE-0⟧\nDEFAULT=\"Successful Response\""
        out, fx = T.restore_code(te, blocks, [0])
        self.assertIn(blocks[0].rstrip("\n"), out)
        self.assertEqual(fx["missing"], [])
        self.assertTrue(T.check_page(PAGE, out)["code_blocks_identical"])

    def test_missing_placeholder_is_appended_and_duplicate_dropped(self):
        _, blocks = T.mask_code(PAGE)
        out, fx = T.restore_code("NO CODE HERE", blocks, [0])
        self.assertEqual(fx["missing"], [0])
        self.assertTrue(out.endswith(blocks[0].rstrip("\n")))
        out, fx = T.restore_code("⟦CODE-0⟧\n⟦CODE-0⟧", blocks, [0])
        self.assertEqual((fx["duplicate"], out.count("import fastapi")), (1, 1))

    def test_restore_case_skips_ambiguous_identifiers(self):
        idents = T.identifiers("`APIRouter` and `fastapi` vs FastAPI and `model_dump`")
        out, n = T.restore_case("APIROUTER ∧ MODEL_DUMP; FASTAPI", idents)
        self.assertEqual(out, "APIRouter ∧ model_dump; FASTAPI")   # fastapi / FastAPI 는 어느 쪽인지 몰라 둔다
        self.assertEqual(n, 2)

    def test_check_page_lists_missing_facts(self):
        te = "`APIRouter` SPLITS APPS\n```python\nimport fastapi\napp = fastapi.FastAPI()\n```\nDEFAULT=RESPONSE"
        miss = T.check_page(PAGE, te)["missing"]
        self.assertIn("0.95.0", miss["numbers"])
        self.assertIn("starlette-graphene3", miss["hyphen_names"])
        self.assertIn("Successful Response", miss["quoted"])
        self.assertIn("Annotated", miss["identifiers"])
        self.assertNotIn("APIRouter", miss["identifiers"])

    def test_chunks_keep_paragraphs_under_limit(self):
        text = "\n\n".join(" ".join(["w"] * 30) for _ in range(5))
        cs = T.chunks(text, limit=70)
        self.assertEqual([len(c.split()) for c in cs], [60, 60, 30])

    def test_compressor_swaps_bodies_and_keeps_headers(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.te.md").write_text("A-TE\n", encoding="utf-8")
        body = "original A"
        (d / "index.json").write_text(json.dumps({"x/a.md": {"file": "a.te.md", "source_sha256": T.sha(body),
                                                             "prompt_hash": "h"}}), encoding="utf-8")
        parts = lambda ctx: PromptParts(system="s", context=ctx, question="q")  # noqa: E731
        with mock.patch.object(T, "TE_DIR", d):
            res = T.TelegraphCompressor().compress(parts(f"## Document: x/a.md\n\n{body}"))
            self.assertEqual(res.context, "## Document: x/a.md\n\nA-TE")
            self.assertEqual(res.info["te_pages"], ["x/a.md"])
            with self.assertRaises(ValueError):          # 원문이 바뀌면 조용히 대체하지 않는다
                T.TelegraphCompressor().compress(parts("## Document: x/a.md\n\nchanged"))


if __name__ == "__main__":
    unittest.main()
