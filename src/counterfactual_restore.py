
"""c0021: r30 관계 표현 복원 실험."""

import argparse
import json
from pathlib import Path

from experiment import ANSWER_MAX_TOKENS, load_answer_prompt
from llm import LLM
from counterfactual_answer import classify_answer

ROOT = Path("results/counterfactual/pilot_v1")
MANIFEST = ROOT / "manifest.jsonl"
OUTPUT = ROOT / "restoration_answers.jsonl"

VARIANTS = ("original", "counterfactual")


def read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats는 1 이상이어야 합니다.")

    item = next(
        row for row in read_jsonl(MANIFEST)
        if row["qid"] == "c0021"
    )

    existing = read_jsonl(OUTPUT)
    completed = {
        (row["variant"], row["repeat"])
        for row in existing
    }

    tasks = []

    for variant in VARIANTS:
        path = (
            ROOT / "compressed"
            / f"c0021.{variant}.r30_restored.md"
        )

        if not path.exists():
            raise FileNotFoundError(path)

        context = path.read_text(encoding="utf-8")

        expected_keyword = (
            item["original_answer"]
            if variant == "original"
            else item["counterfactual_answer"]
        )

        if expected_keyword not in context:
            raise ValueError(
                f"{variant}: 복원 문맥에 정답 키워드가 없습니다."
            )

        for repeat in range(1, args.repeats + 1):
            if (variant, repeat) not in completed:
                tasks.append(
                    (variant, repeat, context, path)
                )

    print(f"이미 완료: {len(existing)}회")
    print(f"이번 실행 대상: {len(tasks)}회")

    if not args.run:
        print("미리보기입니다. API 호출 없음.")
        for variant, repeat, _, _ in tasks:
            print(variant, f"repeat={repeat}")
        return

    prompt = load_answer_prompt("v1")
    llm = LLM(
        role="answer",
        max_tokens=ANSWER_MAX_TOKENS,
        max_retries=1,
    )

    print("답변 모델:", llm.model)

    with OUTPUT.open("a", encoding="utf-8") as file:
        for variant, repeat, context, path in tasks:
            parts = prompt.parts(
                context,
                item["question"],
                item["type"],
            )

            result = llm.chat(
                prompt.messages(parts)
            )

            classification = classify_answer(
                result.text,
                item["original_answer"],
                item["counterfactual_answer"],
            )

            expected = (
                "original"
                if variant == "original"
                else "counterfactual"
            )

            record = {
                "qid": "c0021",
                "variant": variant,
                "compressor": "llmlingua2_r30_restored",
                "repeat": repeat,
                "context_file": str(path),
                "question": item["question"],
                "response": result.text.strip(),
                "classification": classification,
                "expected_classification": expected,
                "followed_document": (
                    classification == expected
                ),
                "model": result.model,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "prompt_version": prompt.version,
                "prompt_hash": prompt.sha256,
                "sampling": llm.sampling_info(),
            }

            file.write(
                json.dumps(
                    record, ensure_ascii=False
                ) + "\n"
            )
            file.flush()

            existing.append(record)

            print(
                f"[{variant} / {repeat}] "
                f"답변={result.text.strip()!r} "
                f"판정={classification}"
            )

    correct = sum(
        row["followed_document"]
        for row in existing
    )

    print(f"\n복원 문맥 정답: {correct}/{len(existing)}")
    print("결과 파일:", OUTPUT)


if __name__ == "__main__":
    main()
