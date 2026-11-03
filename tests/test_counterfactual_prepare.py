
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from counterfactual_prepare import prepare, replace_once


class CounterfactualPrepareTest(unittest.TestCase):

    def test_replace_exactly_once(self):
        result = replace_once(
            "default 500", "500", "750"
        )
        self.assertEqual(result, "default 750")

        for text in ("no number", "500 and 500"):
            with self.assertRaises(ValueError):
                replace_once(text, "500", "750")

    def test_prepare_never_edits_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            (root / "run/contexts").mkdir(
                parents=True
            )

            original = "default `500`"

            source = (
                root / "run/contexts/c0018.none.md"
            )

            source.write_text(original)

            trial = {
                "qid": "c0018",
                "compressor": "none",
                "question": "default?",
                "answer": "500",
                "qtype": "fact",
            }

            (
                root / "run/trials.jsonl"
            ).write_text(json.dumps(trial) + "\n")

            spec = root / "spec.json"

            spec.write_text(json.dumps([{
                "qid": "c0018",
                "old_span": "default `500`",
                "new_span": "default `750`",
                "synthetic_answer": "750",
            }]))

            records = prepare(
                spec,
                root / "out",
                root,
                "run",
                root / "run",
            )

            self.assertEqual(len(records), 1)

            self.assertEqual(
                source.read_text(),
                original,
            )

            modified = (
                root
                / "out/contexts/c0018.counterfactual.md"
            )

            self.assertEqual(
                modified.read_text(),
                "default `750`",
            )

            with self.assertRaises(FileExistsError):
                prepare(
                    spec,
                    root / "out",
                    root,
                    "run",
                    root / "run",
                )


if __name__ == "__main__":
    unittest.main()
