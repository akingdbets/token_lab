
"""반사실적 문맥 실험: 원본/수정 문맥에 동일한 압축 적용."""

import csv
import json
from pathlib import Path

from compressors import get_compressor
from experiment import load_answer_prompt
from llm import count_message_tokens


ROOT = Path("results/counterfactual/pilot_v1")
MANIFEST = ROOT / "manifest.jsonl"
OUTPUT = ROOT / "compressed"

COMPRESSORS = [
    "none",
    "llmlingua2_r50",
    "llmlingua2_r30",
]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    items = [
        json.loads(line)
        for line in MANIFEST.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    prompt = load_answer_prompt("v1")
    records = []

    for item in items:
        qid = item["qid"]
        question = item["question"]
        qtype = item["type"]

        for variant in ("original", "counterfactual"):
            path = (
                ROOT / "contexts"
                / f"{qid}.{variant}.md"
            )

            context = path.read_text(encoding="utf-8")

            parts = prompt.parts(
                context,
                question,
                qtype,
            )

            original_tokens = count_message_tokens(
                prompt.messages(parts)
            )

            for name in COMPRESSORS:
                compressor = get_compressor(name)
                result = compressor.compress(parts)
                compressed_parts = result.parts

                compressed_tokens = count_message_tokens(
                    prompt.messages(compressed_parts)
                )

                reduction = (
                    100
                    * (original_tokens - compressed_tokens)
                    / original_tokens
                )

                status = result.info.get(
                    "status", "unchanged"
                )

                used_original = result.info.get(
                    "trace", {}
                ).get("used_original", False)

                output_path = (
                    OUTPUT / f"{qid}.{variant}.{name}.md"
                )

                output_path.write_text(
                    compressed_parts.context,
                    encoding="utf-8",
                )

                record = {
                    "qid": qid,
                    "variant": variant,
                    "compressor": name,
                    "input_tokens_raw": original_tokens,
                    "input_tokens_compressed": compressed_tokens,
                    "input_reduction_pct": round(reduction, 2),
                    "status": status,
                    "used_original": used_original,
                    "changed_span_kept": (
                        item["new_span"]
                        in compressed_parts.context
                    ),
                }

                records.append(record)

                print(
                    f"{qid:6} "
                    f"{variant:14} "
                    f"{name:17} "
                    f"절감률 {reduction:6.2f}% "
                    f"상태 {status}"
                )

                if status.startswith("fallback"):
                    print(
                        "  [주의] 압축 실패로 원문을 "
                        "사용했을 수 있습니다."
                    )

    output_csv = ROOT / "compression_summary.csv"

    with output_csv.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(records[0]),
        )
        writer.writeheader()
        writer.writerows(records)

    print()
    print(f"완료: {len(records)}개 압축 결과")
    print(f"결과표: {output_csv}")


if __name__ == "__main__":
    main()
