"""Import TokenLab experiment runs without changing their source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ImportFailure(Exception):
    pass


class ImportConflict(ImportFailure):
    pass


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {value}")


def _parse_json(data: bytes, source: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ImportFailure(f"{source}: invalid JSON: {exc}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                   .encode("utf-8"))


def _object(value: Any, source: str) -> dict:
    if not isinstance(value, dict):
        raise ImportFailure(f"{source}: expected JSON object")
    return value


def _string(value: Any, source: str) -> str:
    if not isinstance(value, str) or not value:
        raise ImportFailure(f"{source}: expected nonempty string")
    return value


def _integer(value: Any, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ImportFailure(f"{source}: expected integer")
    return value


def _optional_number(value: Any, source: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImportFailure(f"{source}: expected number or null")
    return value


@dataclass(frozen=True)
class Trial:
    record: dict
    sha256: str


@dataclass(frozen=True)
class RunFiles:
    directory: Path
    summary: dict
    trials: list[Trial]
    summary_sha256: str
    trials_sha256: str
    schema_version: str
    cohort_sha256: str
    observed_splits: list[str]
    dataset_name: str | None
    dataset_sha256: str | None
    dataset_match_status: str


def _schema_version(summary: dict, trials: list[Trial]) -> str:
    metrics = summary["results"]
    current = all("input_reduction_pct" in value for value in metrics.values())
    legacy = all("net_reduction_pct" in value for value in metrics.values())
    if current == legacy:
        raise ImportFailure("summary: cannot identify one consistent legacy/current schema")
    required = "input_tokens_raw" if current else "ctx_tokens_raw"
    forbidden = "ctx_tokens_raw" if current else "input_tokens_raw"
    if any(required not in t.record or forbidden in t.record for t in trials):
        raise ImportFailure("trials: schema does not match summary")
    return "current" if current else "legacy"


def _dataset_match(items: dict[str, dict], evalsets_root: Path) -> tuple[str | None, str | None, str]:
    matches = []
    if evalsets_root.is_dir():
        for path in sorted(evalsets_root.glob("*/qa_dataset.json")):
            try:
                raw = path.read_bytes()
                dataset = _parse_json(raw, str(path))
                if not isinstance(dataset, list):
                    continue
                by_id = {item["id"]: item for item in dataset if isinstance(item, dict) and "id" in item}
                if all(
                    qid in by_id
                    and all(by_id[qid].get(source_key) == value for source_key, value in (
                        ("split", item["split"]), ("type", item["qtype"]),
                        ("question", item["question"]), ("answer", item["answer"]),
                        ("evidence_pages", item["evidence_pages"]),
                    ))
                    for qid, item in items.items()
                ):
                    matches.append((path.parent.name, _sha256(raw)))
            except (OSError, ImportFailure, KeyError, TypeError):
                continue
    if len(matches) == 1:
        return matches[0][0], matches[0][1], "content_match"
    return None, None, "ambiguous" if matches else "unmatched"


def inspect_run(directory: Path, evalsets_root: Path) -> RunFiles:
    summary_path = directory / "summary.json"
    trials_path = directory / "trials.jsonl"
    if not summary_path.is_file() or not trials_path.is_file():
        raise ImportFailure(f"{directory}: summary.json and trials.jsonl are both required")
    summary_raw = summary_path.read_bytes()
    trials_raw = trials_path.read_bytes()
    summary = _object(_parse_json(summary_raw, str(summary_path)), str(summary_path))
    run_id = _string(summary.get("run_id"), f"{summary_path}: run_id")
    if run_id != directory.name:
        raise ImportFailure(f"{directory}: directory name and summary run_id differ")
    config = _object(summary.get("config"), f"{summary_path}: config")
    compressors = _object(summary.get("compressors"), f"{summary_path}: compressors")
    results = _object(summary.get("results"), f"{summary_path}: results")
    if not results or set(compressors) != set(results):
        raise ImportFailure(f"{directory}: summary compressors and results differ")
    if any(not isinstance(value, dict) for value in compressors.values()):
        raise ImportFailure(f"{directory}: compressor settings must be objects")
    if any(not isinstance(value, dict) for value in results.values()):
        raise ImportFailure(f"{directory}: compressor metrics must be objects")
    if not isinstance(summary.get("corpus_source"), dict):
        raise ImportFailure(f"{directory}: corpus_source must be an object")

    trials: list[Trial] = []
    unique: set[tuple[str, str, int, int]] = set()
    questions: dict[str, dict] = {}
    for line_number, line in enumerate(trials_raw.splitlines(), 1):
        if not line.strip():
            continue
        source = f"{trials_path}:{line_number}"
        record = _object(_parse_json(line, source), source)
        if record.get("run_id") != run_id:
            raise ImportFailure(f"{source}: trial run_id differs from summary")
        qid = _string(record.get("qid"), f"{source}: qid")
        compressor = _string(record.get("compressor"), f"{source}: compressor")
        if compressor not in results:
            raise ImportFailure(f"{source}: compressor absent from summary: {compressor}")
        repeat_index = _integer(record.get("repeat_index", 0), f"{source}: repeat_index")
        turn_index = _integer(record.get("turn_index", 0), f"{source}: turn_index")
        if repeat_index < 0 or turn_index < 0:
            raise ImportFailure(f"{source}: negative repeat/turn index")
        key = (qid, compressor, repeat_index, turn_index)
        if key in unique:
            raise ImportFailure(f"{source}: duplicate trial {key}")
        unique.add(key)
        for field in ("split", "qtype", "question", "answer"):
            _string(record.get(field), f"{source}: {field}")
        evidence = record.get("evidence_pages")
        if not isinstance(evidence, list) or any(not isinstance(page, str) for page in evidence):
            raise ImportFailure(f"{source}: evidence_pages must be a string array")
        question = {field: record[field] for field in ("split", "qtype", "question", "answer", "evidence_pages")}
        if qid in questions and questions[qid] != question:
            raise ImportFailure(f"{source}: question metadata differs across compressors")
        questions[qid] = question
        if not isinstance(record.get("fact_results", []), list) or not isinstance(record.get("info", {}), dict):
            raise ImportFailure(f"{source}: fact_results/info has invalid type")
        trials.append(Trial(record, _sha256(line)))

    if not trials:
        raise ImportFailure(f"{directory}: no trials")
    counts = Counter(t.record["compressor"] for t in trials)
    if set(counts) != set(results):
        raise ImportFailure(f"{directory}: summary and trial compressor sets differ")
    for compressor, metric in results.items():
        if _integer(metric.get("n"), f"{directory}: {compressor}.n") != counts[compressor]:
            raise ImportFailure(f"{directory}: {compressor} summary n differs from trial count")
    if "n_items" in config and _integer(config["n_items"], f"{directory}: config.n_items") != len(questions):
        raise ImportFailure(f"{directory}: config.n_items differs from unique question count")
    schema_version = _schema_version(summary, trials)
    cohort = [{"qid": qid, **questions[qid]} for qid in sorted(questions)]
    dataset_name, dataset_sha256, match_status = _dataset_match(questions, evalsets_root)
    return RunFiles(
        directory, summary, trials, _sha256(summary_raw), _sha256(trials_raw),
        schema_version, _canonical_hash(cohort),
        sorted({t.record["split"] for t in trials}),
        dataset_name, dataset_sha256, match_status,
    )


METRIC_FIELDS = (
    "input_reduction_pct", "net_input_reduction_pct", "reduction_pct",
    "net_reduction_pct", "semantic_sim", "entity_retention", "answer_accuracy",
    "answer_accuracy_retention_pct",
)


def _metric(value: dict, field: str, source: str) -> int | float | None:
    return _optional_number(value.get(field), f"{source}: {field}")


def import_run(conn: Any, run: RunFiles, source_namespace: str) -> str:
    from psycopg.types.json import Jsonb

    summary = run.summary
    config = summary["config"]
    fact_judge = config.get("fact_judge") if isinstance(config.get("fact_judge"), dict) else {}
    answer_prompt = config.get("answer_prompt") if isinstance(config.get("answer_prompt"), dict) else {}
    source_path = f"runs/{run.directory.name}"
    with conn.transaction():
        existing = conn.execute(
            "SELECT summary_sha256, trials_sha256 FROM runs "
            "WHERE source_namespace = %s AND run_id = %s FOR UPDATE",
            (source_namespace, summary["run_id"]),
        ).fetchone()
        if existing:
            if existing == (run.summary_sha256, run.trials_sha256):
                return "SKIPPED"
            raise ImportConflict(
                f"{source_namespace}/{summary['run_id']}: existing run ID has different file hashes"
            )
        row = conn.execute(
            """INSERT INTO runs (
                source_namespace, run_id, source_path, schema_version, summary_sha256,
                trials_sha256, cohort_sha256, run_time_text, git_head, requested_split,
                observed_splits, n_items, llm_config, judge_model, judge_mode,
                judge_prompt_version, judge_prompt_hash, answer_prompt_version,
                answer_prompt_hash, semantic_enabled, dataset_name, dataset_sha256,
                dataset_match_status, config_json, corpus_source_json, summary_raw
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) RETURNING run_pk""",
            (
                source_namespace, summary["run_id"], source_path, run.schema_version,
                run.summary_sha256, run.trials_sha256, run.cohort_sha256,
                summary.get("time"), summary.get("git_head"), config.get("split"),
                run.observed_splits, config.get("n_items"), config.get("llm"),
                config.get("judge_model"), config.get("judge_mode"),
                fact_judge.get("prompt_version"), fact_judge.get("prompt_hash"),
                answer_prompt.get("version"), answer_prompt.get("sha256"),
                config.get("semantic"), run.dataset_name, run.dataset_sha256,
                run.dataset_match_status, Jsonb(config), Jsonb(summary["corpus_source"]),
                Jsonb(summary),
            ),
        ).fetchone()
        run_pk = row[0]
        for compressor, value in summary["results"].items():
            source = f"{run.directory}: results.{compressor}"
            metrics = [_metric(value, field, source) for field in METRIC_FIELDS]
            relevant = [t.record for t in run.trials if t.record["compressor"] == compressor]
            coverage = {field: sum(t.get(field) is not None for t in relevant)
                        for field in METRIC_FIELDS}
            conn.execute(
                """INSERT INTO run_compressor_metrics (
                    run_pk, compressor, compressor_config, n_trials, input_reduction_pct,
                    net_input_reduction_pct, context_reduction_pct, legacy_net_reduction_pct,
                    semantic_sim, entity_retention, answer_accuracy,
                    answer_accuracy_retention_pct, metric_coverage, raw_metrics
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (run_pk, compressor, Jsonb(summary["compressors"][compressor]),
                 value["n"], *metrics, Jsonb(coverage), Jsonb(value)),
            )
        for trial in run.trials:
            t = trial.record
            source = f"{run.directory}: trial {t['qid']}/{t['compressor']}"
            for field in METRIC_FIELDS:
                _metric(t, field, source)
            current = run.schema_version == "current"
            conn.execute(
                """INSERT INTO trials (
                    run_pk, qid, compressor, repeat_index, turn_index, conversation_id,
                    split, qtype, question, reference_answer, response,
                    input_tokens_raw, input_tokens, input_reduction_pct,
                    net_input_reduction_pct, context_tokens_raw, context_tokens,
                    context_reduction_pct, legacy_net_reduction_pct, semantic_sim,
                    entity_retention, answer_accuracy, satisfied_facts, total_facts,
                    correct, judge, judge_prompt_version, judge_prompt_hash, judge_mode,
                    fact_results, compressor_info, record_sha256, raw_record
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )""",
                (run_pk, t["qid"], t["compressor"], t.get("repeat_index", 0),
                 t.get("turn_index", 0), t.get("conversation_id"), t["split"],
                 t["qtype"], t["question"], t["answer"], t.get("response"),
                 t.get("input_tokens_raw"), t.get("input_tokens"),
                 t.get("input_reduction_pct"), t.get("net_input_reduction_pct"),
                 t.get("context_tokens_raw") if current else t.get("ctx_tokens_raw"),
                 t.get("context_tokens") if current else t.get("ctx_tokens"),
                 t.get("reduction_pct"), t.get("net_reduction_pct"),
                 t.get("semantic_sim"), t.get("entity_retention"),
                 t.get("answer_accuracy"), t.get("satisfied_facts"),
                 t.get("total_facts"), t.get("correct"), t.get("judge"),
                 t.get("judge_prompt_version"), t.get("judge_prompt_hash"),
                 t.get("judge_mode"), Jsonb(t.get("fact_results", [])),
                 Jsonb(t.get("info", {})), trial.sha256, Jsonb(t)),
            )
    return "IMPORTED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import TokenLab experiment results")
    parser.add_argument("--runs-root", type=Path, default=Path("/data/results/runs"))
    parser.add_argument("--evalsets-root", type=Path, default=Path("/data/evalsets"))
    args = parser.parse_args()
    source_namespace = os.environ.get("SOURCE_NAMESPACE", "local").strip()
    if not source_namespace:
        parser.error("SOURCE_NAMESPACE must not be empty")
    directories = sorted(path.parent for path in args.runs_root.glob("*/summary.json"))
    if not directories:
        print(f"No runs found under {args.runs_root}")
        return 0
    try:
        import psycopg
        conn = psycopg.connect(autocommit=True)
    except Exception as exc:
        print(f"Database connection failed: {exc}", file=sys.stderr)
        return 1
    counts = Counter()
    with conn:
        for directory in directories:
            try:
                run = inspect_run(directory, args.evalsets_root)
                outcome = import_run(conn, run, source_namespace)
                counts[outcome] += 1
                print(f"{outcome} {run.summary['run_id']} schema={run.schema_version} "
                      f"trials={len(run.trials)} dataset={run.dataset_name or 'unknown'}", flush=True)
            except Exception as exc:
                counts["FAILED"] += 1
                print(f"FAILED {directory.name}: {exc}", file=sys.stderr, flush=True)
    print(f"Import summary: imported={counts['IMPORTED']} skipped={counts['SKIPPED']} "
          f"failed={counts['FAILED']}")
    return 1 if counts["FAILED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
