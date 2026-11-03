
"""TokenLab 반사실적 문맥 실험: 원본을 보존하면서 수정 문맥 생성."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def replace_once(text: str, before: str, after: str) -> str:
    """문서에서 정확히 한 곳만 수정한다."""
    if not before or not after or before == after:
        raise ValueError("변경 전후 문자열은 서로 달라야 합니다.")

    count = text.count(before)

    if count != 1:
        raise ValueError(
            f"변경 대상은 정확히 한 번 있어야 합니다: "
            f"{before!r}, 발견 {count}회"
        )

    return text.replace(before, after, 1)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_items(
    eval_dir: Path,
    qids: list[str],
    source: str,
    run_dir: Path | None,
) -> dict[str, dict]:

    if source == "repo":
        from corpus import load_corpus
        from experiment import build_context

        questions = json.loads(
            (eval_dir / "qa_dev.json").read_text(encoding="utf-8")
        )

        corpus = load_corpus()

        return {
            q["id"]: {
                "question": q["question"],
                "answer": q["answer"],
                "type": q["type"],
                "context": build_context(corpus, q),
            }
            for q in questions
            if q["id"] in qids
        }

    if run_dir is None:
        raise ValueError(
            "--source run 사용 시 --run-dir가 필요합니다."
        )

    result = {}

    lines = (
        run_dir / "trials.jsonl"
    ).read_text(encoding="utf-8").splitlines()

    for line in lines:
        if not line.strip():
            continue

        row = json.loads(line)

        if (
            row.get("compressor") != "none"
            or row["qid"] not in qids
        ):
            continue

        context_path = (
            run_dir / "contexts" / f'{row["qid"]}.none.md'
        )

        result[row["qid"]] = {
            "question": row["question"],
            "answer": row["answer"],
            "type": row["qtype"],
            "context": context_path.read_text(
                encoding="utf-8"
            ),
        }

    return result


def prepare(
    spec_file: Path,
    output_dir: Path,
    eval_dir: Path,
    source: str = "repo",
    run_dir: Path | None = None,
) -> list[dict]:

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"출력 폴더에 파일이 이미 있습니다: {output_dir}"
        )

    specs = json.loads(
        spec_file.read_text(encoding="utf-8")
    )

    if not isinstance(specs, list) or not specs:
        raise ValueError(
            "실험 설정 JSON은 비어 있지 않은 배열이어야 합니다."
        )

    qids = [s["qid"] for s in specs]

    if len(qids) != len(set(qids)):
        raise ValueError("중복 문항 ID가 있습니다.")

    items = build_items(
        eval_dir, qids, source, run_dir
    )

    staged = []

    # 먼저 모든 문항이 올바르게 수정되는지 검증
    for spec in specs:
        qid = spec["qid"]

        if qid not in items:
            raise ValueError(
                f"평가셋에서 문항을 찾지 못했습니다: {qid}"
            )

        q = items[qid]

        original = q["context"].replace(
            "\r\n", "\n"
        )

        modified = replace_once(
            original,
            spec["old_span"],
            spec["new_span"],
        )

        synthetic = spec["synthetic_answer"]

        if str(q["answer"]).strip() == synthetic.strip():
            raise ValueError(
                f"변경 전후 정답이 같습니다: {qid}"
            )

        if synthetic not in modified:
            raise ValueError(
                f"변경된 정답이 수정 문맥에 없습니다: {qid}"
            )

        staged.append(
            (spec, q, original, modified)
        )

    (output_dir / "contexts").mkdir(
        parents=True, exist_ok=True
    )

    manifest = []

    # 원본과 수정 문맥을 별도 파일로 저장
    for spec, q, original, modified in staged:
        qid = spec["qid"]

        for version, text in (
            ("original", original),
            ("counterfactual", modified),
        ):
            path = (
                output_dir
                / "contexts"
                / f"{qid}.{version}.md"
            )

            path.write_text(
                text, encoding="utf-8"
            )

        manifest.append({
            "qid": qid,
            "type": q["type"],
            "question": q["question"],
            "original_answer": q["answer"],
            "counterfactual_answer": spec["synthetic_answer"],
            "old_span": spec["old_span"],
            "new_span": spec["new_span"],
            "source": source,
            "synthetic": True,
            "original_sha256": sha256(original),
            "counterfactual_sha256": sha256(modified),
            "remaining_original_answer_occurrences": (
                modified.count(str(q["answer"]))
            ),
        })

    manifest_path = output_dir / "manifest.jsonl"

    with manifest_path.open(
        "w", encoding="utf-8"
    ) as file:
        for record in manifest:
            file.write(
                json.dumps(
                    record, ensure_ascii=False
                ) + "\n"
            )

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="반사실적 문맥 생성 (API 호출 없음)"
    )

    parser.add_argument(
        "--spec",
        type=Path,
        default=Path(
            "data/counterfactual/pilot_v1.json"
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "results/counterfactual/pilot_v1"
        ),
    )

    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=Path(
            "data/evalsets/claude-v1"
        ),
    )

    parser.add_argument(
        "--source",
        choices=["repo", "run"],
        default="repo",
    )

    parser.add_argument(
        "--run-dir",
        type=Path,
    )

    args = parser.parse_args()

    try:
        records = prepare(
            args.spec,
            args.out,
            args.eval_dir,
            args.source,
            args.run_dir,
        )

    except (
        ValueError,
        FileNotFoundError,
        FileExistsError,
    ) as error:
        sys.exit(
            f"실험 문맥 생성 실패: {error}"
        )

    for rec in records:
        print(
            f'OK {rec["qid"]}: '
            f'{rec["original_answer"]} → '
            f'{rec["counterfactual_answer"]}'
        )

    print(
        f"생성 완료: {args.out} "
        f"({len(records)}문항)"
    )

    print(
        "주의: 원래 정답이 문서의 다른 위치에 "
        "남아 있는지 추가로 확인해야 합니다."
    )


if __name__ == "__main__":
    main()
