import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import judge_check_viewer as V  # noqa: E402


class JudgeCheckViewerTest(unittest.TestCase):
    def test_build_embeds_rows_without_judge_and_escapes_script(self):
        row = {c: "" for c in V.COLUMNS}
        row.update({"row_id": "T001", "담당자": "A", "모델 답변": "</script><b>x</b>", "human": "O", "judge": "YES"})
        html = V.build([row])
        self.assertNotIn("</script><b>", html)                       # 답변 속 </script> 가 스크립트를 닫지 않는다
        data = json.loads(re.search(r"const ROWS = (\[.*?\]);\n", html).group(1).replace("<\\/", "</"))
        self.assertEqual(data[0]["모델 답변"], "</script><b>x</b>")
        self.assertEqual(data[0]["human"], "O")                       # 이미 채운 라벨은 유지
        self.assertNotIn("judge", data[0])                            # 블라인드: judge 판정은 넣지 않는다
        self.assertEqual(list(data[0]), V.COLUMNS)


if __name__ == "__main__":
    unittest.main()
