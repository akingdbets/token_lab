
"""반사실적 문맥 실험: 압축된 문맥에 대한 답변 충실도 평가."""
import re
import argparse
import csv
import json
from pathlib import Path

from experiment import ANSWER_MAX_TOKENS, load_answer_prompt
from llm import LLM
from compressors.base import PromptParts


ROOT = Path("results/counterfactual/pilot_v1")
MANIFEST = ROOT / "manifest.jsonl"
CONTEXTS = ROOT / "compressed"
RESULTS = ROOT / "answers.jsonl"
SUMMARY = ROOT / "answer_summary.csv"

COMPRESSORS = (
    "none",
    "llmlingua2_r50",
    "llmlingua2_r30",
)
VARIANTS = ("original", "counterfactual")




def normalize_answer(value):
    """숫자형 단답의 단위 표현을 정규화한다."""
    value = str(value).strip()

    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()

    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].strip()

    value = value.rstrip(".").strip()

    # 500 bytes → 500
    # 15 minutes → 15
    # 23 minutes → 23
    value = re.sub(
        r"^(\d+)\s*(?:bytes?|바이트|minutes?|mins?|분)$",
        r"\1",
        value,
        flags=re.IGNORECASE,
    )

    return value



def classify_answer(response, original, modified):
    """단답형만 자동 평가하고 나머지는 수동 검토 대상으로 둠."""
    answer = normalize_answer(response)
    old = normalize_answer(str(original))
    new = normalize_answer(str(modified))

    if not answer:
        return "empty"

    if answer.upper().startswith("NOT FOUND"):
        return "not_found"

    if answer.casefold() == old.casefold():
        return "original"

    if answer.casefold() == new.casefold():
        return "counterfactual"

    return "other"


def load_manifest():
    return [
        json.loads(line)
        for line in MANIFEST.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def load_existing():
    if not RESULTS.exists():
        return []

    return [
        json.loads(line)
        for line in RESULTS.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def save_summary(records):
    if not records:
        return

    columns = [
        "qid",
        "variant",
        "compressor",
        "repeat",
        "response",
        "classification",
        "expected_classification",
        "followed_document",
        "prompt_tokens",
        "completion_tokens",
        "model",
    ]

    with SUMMARY.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="실제로 답변 API 호출",
    )
    parser.add_argument("--qid")
    parser.add_argument(
        "--compressor",
        choices=COMPRESSORS,
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats는 1 이상이어야 합니다.")

    items = load_manifest()
    prompt = load_answer_prompt("v1")

    existing = load_existing()
    completed = {
        (
            row["qid"],
            row["variant"],
            row["compressor"],
            row["repeat"],
        )
        for row in existing
    }

    tasks = []

    for item in items:
        qid = item["qid"]

        if args.qid and qid != args.qid:
            continue

        for variant in VARIANTS:
            for compressor in COMPRESSORS:
                if (
                    args.compressor
                    and compressor != args.compressor
                ):
                    continue

                context_file = (
                    CONTEXTS
                    / f"{qid}.{variant}.{compressor}.md"
                )

                if not context_file.exists():
                    raise FileNotFoundError(context_file)

                context = context_file.read_text(
                    encoding="utf-8"
                )

                for repeat in range(1, args.repeats + 1):
                    key = (
                        qid,
                        variant,
                        compressor,
                        repeat,
                    )

                    if key not in completed:
                        tasks.append(
                            (
                                item,
                                variant,
                                compressor,
                                repeat,
                                context,
                            )
                        )

    print(f"이미 완료: {len(existing)}회")
    print(f"이번 실험 대상: {len(tasks)}회")

    if not args.run:
        print(
            "미리보기만 실행했습니다. "
            "실제 API 호출은 --run 옵션을 사용하세요."
        )

        for item, variant, compressor, repeat, _ in tasks:
            print(
                item["qid"],
                variant,
                compressor,
                f"repeat={repeat}",
            )

        return

    if not tasks:
        print("추가로 실행할 조건이 없습니다.")
        return

    llm = LLM(
        role="answer",
        max_tokens=ANSWER_MAX_TOKENS,
    )

    print(f"답변 모델: {llm.model}")

    RESULTS.parent.mkdir(
        parents=True, exist_ok=True
    )

    with RESULTS.open(
        "a", encoding="utf-8"
    ) as output:

        for index, (
            item,
            variant,
            compressor,
            repeat,
            context,
        ) in enumerate(tasks, 1):

            parts = prompt.parts(
                context,
                item["question"],
                item["type"],
            )

            messages = prompt.messages(parts)

            print(
                f"\n[{index}/{len(tasks)}] "
                f'{item["qid"]} '
                f"{variant} {compressor}"
            )

            result = llm.chat(messages)

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
                "qid": item["qid"],
                "variant": variant,
                "compressor": compressor,
                "repeat": repeat,
                "question": item["question"],
                "original_answer": item["original_answer"],
                "counterfactual_answer": (
                    item["counterfactual_answer"]
                ),
                "response": result.text.strip(),
                "classification": classification,
                "expected_classification": expected,
                "followed_document": (
                    classification == expected
                ),
                "model": result.model or llm.model,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": (
                    result.completion_tokens
                ),
                "finish_reason": result.finish_reason,
                "answer_prompt_version": prompt.version,
                "answer_prompt_hash": prompt.sha256,
                "sampling": llm.sampling_info(),
            }

            output.write(
                json.dumps(
                    record, ensure_ascii=False
                ) + "\n"
            )
            output.flush()

            existing.append(record)

            print("정답 구분:", expected)
            print("모델 답변:", repr(result.text.strip()))
            print("판정:", classification)

    save_summary(existing)

    print("\n실험 완료")
    print(f"상세 결과: {RESULTS}")
    print(f"결과표: {SUMMARY}")


if __name__ == "__main__":
    main()
