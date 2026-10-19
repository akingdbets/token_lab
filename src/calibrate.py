"""
보정 유지율을 다른 run 의 empty(문서 없음) 결과와 묶어 계산 (API 호출 없음)

experiment.py 는 같은 run 에 empty 가 있으면 summary.json 에 calibrated_retention_pct 를 넣는다.
empty 없이 돌린 기존 run 은 empty 가 있는 run 과 묶어 여기서 계산한다.

    python src/calibrate.py results/runs/<기존 run>/trials.jsonl \\
        --floor results/runs/<empty 가 있는 run>/trials.jsonl

    보정 유지율 = (압축 정확도 − empty 정확도) / (none 정확도 − empty 정확도) × 100   (문항 짝 평균)
    none 은 --base-from 으로 고른다: run (기본, 압축기와 같은 run 의 none) | floor (empty 와 같은 run 의 none)

두 run 의 생성 조건(temperature, reasoning_effort 등)이 다르면 바닥값도 달라질 수 있으니 summary.json 의
config.sampling 을 함께 확인한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import calibrated_retention


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def acc_of(trials: list[dict], comp: str) -> dict:
    return {t["qid"]: t.get("answer_accuracy") for t in trials if t["compressor"] == comp}


def main():
    ap = argparse.ArgumentParser(description="다른 run 의 empty 와 묶어 보정 유지율 계산")
    ap.add_argument("run", help="압축기 결과가 있는 trials.jsonl")
    ap.add_argument("--floor", required=True, help="empty 결과가 있는 trials.jsonl")
    ap.add_argument("--base-from", choices=("run", "floor"), default="run", help="none 정확도를 어느 run 에서 쓸지")
    args = ap.parse_args()

    run, floor = load(args.run), load(args.floor)
    empty = acc_of(floor, "empty")
    if not empty:
        sys.exit(f"{args.floor} 에 empty 결과가 없습니다")
    none = acc_of(run if args.base_from == "run" else floor, "none")
    if not none:
        sys.exit("none 결과가 없습니다")
    comps = [c for c in dict.fromkeys(t["compressor"] for t in run) if c not in ("none", "empty")]
    out = {"run": args.run, "floor": args.floor, "base_from": args.base_from,
           "results": {c: calibrated_retention(none, empty, acc_of(run, c)) for c in comps}}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
