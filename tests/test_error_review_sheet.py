import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import error_review_sheet as S  # noqa: E402

ITEM = {"answer": "0.95.0", "key_entities": []}
CTX = """Support was added in FastAPI 0.95.0 and is recommended.

```python
# requires 0.95.0
```
"""


class ErrorReviewSheetTest(unittest.TestCase):
    def test_excerpts_mark_code_and_prose(self):
        exs = S.excerpts(CTX, ITEM, words=3)
        self.assertEqual([x["where"] for x in exs], ["설명", "코드"])
        cell = S.cell(exs)
        self.assertTrue(cell.startswith("(2곳) [설명] …"))
        self.assertIn("【0.95.0】", cell)

    def test_none_when_missing(self):
        self.assertEqual(S.cell(S.excerpts("FastAPI 0.96 only", ITEM)), "없음")
        # normalized-v2 는 구두점을 무시하므로 쪼개진 버전도 정답 위치로 잡는다 (자동 분류 A 와 같은 기준)
        self.assertIn("【0 95 0】", S.cell(S.excerpts("FastAPI 0 95 0 only", ITEM)))

    def test_html_escapes_and_marks(self):
        out = S.hl("<b>0.95.0</b>", ITEM)
        self.assertEqual(out, "&lt;b&gt;<mark>0.95.0</mark>&lt;/b&gt;")


if __name__ == "__main__":
    unittest.main()
