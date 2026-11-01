"""
정답 사본 지우기 압축기 (compressors/copies.py) 테스트.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm  # noqa: E402
from compressors import PromptParts, get_compressor  # noqa: E402
from compressors.copies import segment  # noqa: E402

CTX = """## Document: testing/async.md

---
title: Async Tests
tags: [testing, asgi-lifespan]
---

# Async Tests

Intro sentence that stays. Use `httpx.AsyncClient` for async tests.

```python
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Tomato"}
```

- **Lifespan events don't run** with `ASGITransport`. Wrap the app with the `asgi-lifespan` package.

  ```python
  from asgi_lifespan import LifespanManager
  ```

| Package | Purpose |
|---|---|
| anyio | runs async tests |

Closing paragraph about other things. See the asgi-lifespan docs for more."""

EVIDENCE = ("Wrap the app with the `asgi-lifespan` package.",)


def tokens(text):
    return len(text.split())


def compress(name, evidence=EVIDENCE, needles=("asgi-lifespan",), question="Which package runs lifespan?"):
    with mock.patch.object(llm, "count_tokens", side_effect=tokens):
        return get_compressor(name).compress(
            PromptParts(system="s", context=CTX, question=question, evidence=evidence, answer_core=needles))


class SegmentTest(unittest.TestCase):
    def test_units(self):
        seg = segment(CTX)
        kinds = [u.kind for u in seg.units]
        self.assertEqual(kinds.count("code"), 2)
        self.assertEqual(kinds.count("meta"), 2)
        self.assertEqual(kinds.count("table"), 3)
        prose = [u.text for u in seg.units if u.kind == "prose"]
        self.assertIn("Intro sentence that stays.", prose)
        self.assertIn("Use `httpx.AsyncClient` for async tests.", prose)
        lst = [u.text for u in seg.units if u.kind == "list"]
        self.assertEqual(len(lst), 2)

    def test_no_split_inside_inline_code(self):
        seg = segment("Call `a. B` here. Next one.")
        self.assertEqual([u.text for u in seg.units], ["Call `a. B` here.", "Next one."])

    def test_render_without_drop_is_identity(self):
        self.assertEqual(segment(CTX).render(set()), CTX)


class DropAllCopiesTest(unittest.TestCase):
    def test_drops_evidence_and_all_spellings(self):
        res = compress("drop_all_copies")
        self.assertNotIn("asgi-lifespan", res.context)
        self.assertNotIn("asgi_lifespan", res.context)       # 표기만 다른 사본 (코드 블록 통째로)
        self.assertNotIn("LifespanManager", res.context)
        self.assertNotIn("Lifespan events don't run", res.context)   # 근거 줄은 줄째 (drop_evidence 와 같다)
        self.assertIn("Closing paragraph about other things.", res.context)   # 근거가 아닌 줄은 사본 문장만
        self.assertIn("title: Async Tests", res.context)
        self.assertIn('return {"message": "Tomato"}', res.context)
        self.assertIn("app = FastAPI()\n\n\n@app.get", res.context)   # 건드리지 않은 코드 블록은 그대로
        i = res.info
        self.assertTrue(i["defined"] and i["verified"])
        self.assertEqual((i["copy_units"], i["copy_units_code"]), (4, 1))
        self.assertGreater(i["dropped_tokens"], 0)

    def test_undefined_when_answer_absent(self):
        res = compress("drop_all_copies", needles=("NotInTheDoc",))
        self.assertEqual(res.context, CTX)
        self.assertFalse(res.info["defined"])

    def test_cross_unit_residual_fails_verification(self):
        # 문장 경계를 넘는 사본은 단위로는 안 잡혀도 문맥 전체 검사에서 걸린다
        with mock.patch.object(llm, "count_tokens", side_effect=tokens):
            res = get_compressor("drop_all_copies").compress(PromptParts(
                system="s", context="Ends with Foo. Bar starts here.\nFoo Bar is here too.", question="q",
                answer_core=("Foo Bar",)))
        self.assertTrue(res.info["defined"])
        self.assertIn("Foo. Bar", res.context)
        self.assertNotIn("Foo Bar is here", res.context)
        self.assertFalse(res.info["verified"])


class KeepOneCopyTest(unittest.TestCase):
    def test_keep_code_copy(self):
        res = compress("keep_code_copy")
        self.assertIn("from asgi_lifespan import LifespanManager", res.context)
        self.assertNotIn("asgi-lifespan", res.context)
        self.assertTrue(res.info["verified"])
        self.assertEqual(res.info["kept_kind"], "code")

    def test_keep_prose_copy_keeps_first_non_evidence(self):
        res = compress("keep_prose_copy")
        self.assertIn("tags: [testing, asgi-lifespan]", res.context)
        self.assertNotIn("Wrap the app", res.context)
        self.assertNotIn("asgi_lifespan", res.context)
        self.assertTrue(res.info["verified"])
        self.assertEqual(res.info["kept_kind"], "meta")

    def test_undefined_without_that_kind(self):
        res = compress("keep_code_copy", needles=("Closing paragraph",), evidence=())
        self.assertEqual(res.context, CTX)
        self.assertFalse(res.info["defined"])


class KeepAnswerInPlaceTest(unittest.TestCase):
    def test_keeps_only_answer_phrase_in_evidence(self):
        res = compress("keep_answer_in_place")
        self.assertTrue(res.info["verified"], res.info["reason"])
        self.assertEqual(res.info["kept_phrase"], "asgi-lifespan")
        self.assertIn("- asgi-lifespan\n", res.context)          # 목록 표시는 남고 근거 문장 자리에 구절만
        self.assertNotIn("Wrap the app", res.context)
        self.assertNotIn("asgi_lifespan", res.context)
        self.assertNotIn("tags: [testing, asgi-lifespan]", res.context)
        self.assertEqual(res.context.count("asgi-lifespan"), 1)

    def test_code_block_evidence_becomes_one_line(self):
        res = compress("keep_answer_in_place", evidence=("from asgi_lifespan import LifespanManager",))
        self.assertTrue(res.info["verified"], res.info["reason"])
        self.assertEqual(res.info["kept_kind"], "code")
        self.assertIn("\nasgi_lifespan\n", res.context)
        self.assertNotIn("LifespanManager", res.context)

    def test_undefined_without_answer_in_evidence(self):
        res = compress("keep_answer_in_place", evidence=("Intro sentence that stays.",))
        self.assertEqual(res.context, CTX)
        self.assertFalse(res.info["defined"])


class AnswerKindTest(unittest.TestCase):
    def test_kinds(self):
        from core_match import answer_kind
        for a in ("DUMMY_HASH", "asgi-lifespan", "@pytest.mark.anyio", "StaticPool", "FastAPIError", "main:app",
                  "X-Token", "websocket_connect"):
            self.assertEqual(answer_kind(a), "identifier", a)
        for a in ("15", "0.95.0", "<0.113.0", '"request"', "http://test", "/v1", "testing_admin@example.com",
                  "*.example.com", "The last one added", "blue", "Rick"):
            self.assertEqual(answer_kind(a), "value", a)


class MatchedRandomDropTest(unittest.TestCase):
    def test_keeps_evidence_and_copies_and_matches_tokens(self):
        target = compress("drop_all_copies").info["dropped_tokens"]
        res = compress("matched_random_drop")
        self.assertTrue(res.info["verified"], res.info["reason"])
        self.assertEqual(res.info["target_tokens"], target)
        self.assertIn("Wrap the app with the `asgi-lifespan` package.", res.context)
        self.assertIn("from asgi_lifespan import LifespanManager", res.context)
        self.assertIn("tags: [testing, asgi-lifespan]", res.context)
        self.assertIn("## Document: testing/async.md", res.context)

    def test_seed_is_deterministic_and_varies(self):
        a, b = compress("matched_random_drop").context, compress("matched_random_drop").context
        self.assertEqual(a, b)
        others = {compress(n).context for n in ("matched_random_drop_s2", "matched_random_drop_s3")}
        self.assertTrue(others - {a})


class ChainTest(unittest.TestCase):
    def test_answer_core_survives_chain(self):
        res = compress("none>drop_all_copies")
        self.assertNotIn("asgi-lifespan", res.context)


if __name__ == "__main__":
    unittest.main()
