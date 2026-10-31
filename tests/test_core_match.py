"""
memory_suspect 용 문맥 검사(answer_core_in_context, 정규화 매칭 normalized-v1) 테스트.

문맥 조각은 run 20261028-195811 의 LLMLingua-2 압축 문맥에서 가져왔다.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from experiment import (  # noqa: E402
    answer_core_in_context,
    answer_core_in_context_strict,
    core_matches,
    find_normalized,
)


def item(answer, entities=None):
    return {"answer": answer, "key_entities": entities or [answer]}


class CoreMatchTest(unittest.TestCase):
    def test_split_or_respelled_identifiers_are_found(self):
        cases = [
            # c0031 llmlingua2_r50
            ("WebSocketDisconnect", "except WebSocket Disconnect: client left", "WebSocket Disconnect"),
            # c0034 llmlingua2_r50
            ("OAuth2PasswordRequestFormStrict", "use OAuth2 PasswordRequestFormStrict instead",
             "OAuth2 PasswordRequestFormStrict"),
            # c0026 llmlingua2_r30
            ("asgi-lifespan", "  from asgi_lifespan import LifespanManager", "asgi_lifespan"),
        ]
        for answer, ctx, found in cases:
            with self.subTest(answer=answer):
                self.assertTrue(answer_core_in_context(ctx, item(answer)))
                self.assertFalse(answer_core_in_context_strict(ctx, item(answer)))   # 이전 방식의 오탐
                self.assertEqual(core_matches(ctx, item(answer))[1], [found])

    def test_token_boundaries_are_kept(self):
        self.assertFalse(answer_core_in_context("status code 1000 returned", item("100")))
        self.assertFalse(answer_core_in_context("limit is 4000 bytes", item("400")))
        self.assertFalse(answer_core_in_context("version 10.0 released", item("100")))   # 숫자끼리는 잇지 않음
        self.assertFalse(answer_core_in_context("WebSocketDisconnected", item("WebSocketDisconnect")))
        self.assertTrue(answer_core_in_context("returns 400.", item("400")))
        self.assertTrue(answer_core_in_context("python 3.10 or later", item("3.10")))

    def test_really_missing_answers_stay_missing(self):
        # c0031 llmlingua2_r30, c0034 llmlingua2_r30 (모델도 NOT FOUND)
        ctx31 = ("Testing Dependencies WebSocket\n hutdown code TestClient context manager WebSocket endpoints "
                 "client websocket_connect\n dependency_overrides websocket_connect")
        ctx34 = "concepts OAuth2 OpenID OpenAPI OAuth2 PasswordBearer tokens get_current_user\n login OAuth2 PasswordRequestForm"
        self.assertFalse(answer_core_in_context(ctx31, item("WebSocketDisconnect")))
        self.assertFalse(answer_core_in_context(ctx34, item("OAuth2PasswordRequestFormStrict")))

    def test_long_answer_needs_half_of_entities(self):
        long_ans = "Wrap the app with LifespanManager from the asgi-lifespan package"
        it = item(long_ans, ["asgi-lifespan", "LifespanManager", "AsyncClient"])
        self.assertTrue(answer_core_in_context("from asgi_lifespan import Lifespan Manager", it))   # 2/3
        self.assertFalse(answer_core_in_context("from asgi_lifespan import x", it))                # 1/3
        self.assertIsNone(find_normalized("anything", "--"))


if __name__ == "__main__":
    unittest.main()
