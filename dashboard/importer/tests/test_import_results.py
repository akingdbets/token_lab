"""Importer validation and isolated PostgreSQL integration tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from src.import_results import ImportConflict, ImportFailure, import_run, inspect_run


def make_current_run(root: Path, run_id: str = "fixture-current-001") -> Path:
    """Create a synthetic current-schema run outside the operational results tree."""
    directory = root / run_id
    directory.mkdir()
    summary = {
        "run_id": run_id,
        "time": "2026-10-14T12:00:00",
        "git_head": "fixture",
        "config": {
            "llm": "backend=ollama model=fixture ctx=16384 temp=0.0 seed=42",
            "judge_model": "fixture-judge",
            "judge_mode": "per_fact",
            "answer_max_tokens": 512,
            "answer_prompt": {"version": "v1", "sha256": "fixture-prompt"},
            "fact_judge": {"prompt_version": "fact_judge_v2", "prompt_hash": "fixture-hash",
                           "mode": "per_fact", "max_tokens": 512},
            "semantic": False,
            "split": "dev",
            "n_items": 1,
        },
        "corpus_source": {"wiki": "fixture"},
        "compressors": {"none": {}, "rule": {"frontmatter": True}},
        "results": {
            "none": {"n": 1, "input_reduction_pct": 0.0, "net_input_reduction_pct": 0.0,
                     "reduction_pct": 0.0, "semantic_sim": None, "entity_retention": 1.0,
                     "answer_accuracy": 1.0, "answer_accuracy_retention_pct": None},
            "rule": {"n": 1, "input_reduction_pct": 25.0, "net_input_reduction_pct": 25.0,
                     "reduction_pct": 30.0, "semantic_sim": None, "entity_retention": 1.0,
                     "answer_accuracy": 0.5, "answer_accuracy_retention_pct": 50.0},
        },
    }
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    trials = []
    for compressor, reduction, accuracy in (("none", 0.0, 1.0), ("rule", 25.0, 0.5)):
        trials.append({
            "run_id": run_id, "qid": "f0001", "split": "dev", "qtype": "fact",
            "compressor": compressor, "question": "Fixture question?", "answer": "Fixture answer.",
            "evidence_pages": ["fixture.md"], "response": "Fixture response.",
            "input_tokens_raw": 100, "input_tokens": 100 if compressor == "none" else 75,
            "input_reduction_pct": reduction, "net_input_reduction_pct": reduction,
            "context_tokens_raw": 80, "context_tokens": 80 if compressor == "none" else 56,
            "reduction_pct": 0.0 if compressor == "none" else 30.0,
            "semantic_sim": None, "entity_retention": 1.0, "answer_accuracy": accuracy,
            "satisfied_facts": 1, "total_facts": 1, "correct": True, "judge": None,
            "judge_prompt_version": "fact_judge_v2", "judge_prompt_hash": "fixture-hash",
            "judge_mode": "per_fact", "fact_results": [{"fact": "Fixture fact.", "satisfied": True}],
            "info": {},
        })
    (directory / "trials.jsonl").write_text(
        "".join(json.dumps(trial) + "\n" for trial in trials), encoding="utf-8")
    return directory


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tokenlab-import-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = make_current_run(self.root)

    def test_current_fixture_and_null_vs_zero(self):
        run = inspect_run(self.directory, self.root / "evalsets")
        self.assertEqual(run.schema_version, "current")
        self.assertIsNone(run.dataset_name)
        self.assertEqual(run.summary["results"]["none"]["input_reduction_pct"], 0.0)
        self.assertIsNone(run.summary["results"]["none"]["semantic_sim"])

    def test_bad_json(self):
        (self.directory / "trials.jsonl").write_text("{bad json}\n", encoding="utf-8")
        with self.assertRaisesRegex(ImportFailure, "invalid JSON"):
            inspect_run(self.directory, self.root)

    def test_duplicate_trial(self):
        path = self.directory / "trials.jsonl"
        first = path.read_text(encoding="utf-8").splitlines()[0]
        with path.open("a", encoding="utf-8") as stream:
            stream.write(first + "\n")
        with self.assertRaisesRegex(ImportFailure, "duplicate trial"):
            inspect_run(self.directory, self.root)

    def test_trial_run_id_mismatch(self):
        path = self.directory / "trials.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0]["run_id"] = "wrong"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        with self.assertRaisesRegex(ImportFailure, "run_id differs"):
            inspect_run(self.directory, self.root)

    def test_compressor_mismatch(self):
        path = self.directory / "trials.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[1]["compressor"] = "missing"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        with self.assertRaisesRegex(ImportFailure, "compressor absent"):
            inspect_run(self.directory, self.root)


@unittest.skipUnless(os.environ.get("TEST_PGDATABASE"), "isolated test database not configured")
class DatabaseTests(unittest.TestCase):
    def test_import_reimport_conflict_and_rollback(self):
        import psycopg

        test_db = os.environ["TEST_PGDATABASE"]
        self.assertNotEqual(test_db, os.environ.get("PGDATABASE"))
        namespace = f"fixture-{uuid.uuid4().hex}"
        with tempfile.TemporaryDirectory(prefix="tokenlab-db-test-") as temp:
            root = Path(temp)
            directory = make_current_run(root)
            schema = Path(os.environ["TEST_SCHEMA_PATH"]).read_text(encoding="utf-8")
            with psycopg.connect(dbname=test_db, autocommit=True) as conn:
                conn.execute(schema)
                try:
                    run = inspect_run(directory, root / "evalsets")
                    self.assertEqual(import_run(conn, run, namespace), "IMPORTED")
                    self.assertEqual(import_run(conn, run, namespace), "SKIPPED")
                    row = conn.execute(
                        """SELECT m.input_reduction_pct, m.net_input_reduction_pct,
                                  m.context_reduction_pct, m.legacy_net_reduction_pct,
                                  m.semantic_sim, m.answer_accuracy_retention_pct
                           FROM run_compressor_metrics m JOIN runs r USING (run_pk)
                           WHERE r.source_namespace = %s AND compressor = 'none'""",
                        (namespace,),
                    ).fetchone()
                    self.assertEqual(row[0:3], (0.0, 0.0, 0.0))
                    self.assertEqual(row[3:], (None, None, None))
                    count_runs = conn.execute(
                        "SELECT count(*) FROM runs WHERE source_namespace = %s", (namespace,)
                    ).fetchone()[0]
                    self.assertEqual(count_runs, 1)

                    # The same Run ID with changed bytes is rejected before any write.
                    summary_path = directory / "summary.json"
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    summary["git_head"] = "different"
                    summary_path.write_text(json.dumps(summary), encoding="utf-8")
                    changed = inspect_run(directory, root / "evalsets")
                    with self.assertRaises(ImportConflict):
                        import_run(conn, changed, namespace)

                    # A late validation error rolls back both the run and its first metric row.
                    invalid_dir = make_current_run(root, "fixture-invalid-001")
                    invalid_path = invalid_dir / "summary.json"
                    invalid = json.loads(invalid_path.read_text(encoding="utf-8"))
                    invalid["results"]["rule"]["answer_accuracy"] = "invalid"
                    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
                    with self.assertRaises(ImportFailure):
                        import_run(conn, inspect_run(invalid_dir, root / "evalsets"), namespace)
                    self.assertEqual(conn.execute(
                        "SELECT count(*) FROM runs WHERE source_namespace = %s", (namespace,)
                    ).fetchone()[0], 1)
                    self.assertEqual(conn.execute(
                        """SELECT count(*) FROM trials t JOIN runs r USING (run_pk)
                           WHERE r.source_namespace = %s""", (namespace,)
                    ).fetchone()[0], 2)
                finally:
                    conn.execute("DELETE FROM runs WHERE source_namespace = %s", (namespace,))


if __name__ == "__main__":
    unittest.main()
