"""
실험 run 의 답변으로 사람 라벨링 시트 만들기 (judge 검증용)

experiment.py 로 만든 trials.jsonl 에서
    - none 답변의 key_fact 전부 (문항마다 fact 한 줄)
    - none 과 answer_accuracy 가 다른 압축기 답변의 key_fact (compressor 열로 구분)
를 뽑아 라벨링 시트를 만든다. judge 판정은 시트에 넣지 않고(라벨링하는 사람이 보면 안 됨)
별도 파일에 둔다. 라벨이 채워지면 judge_agreement.py --judged 로 일치율을 낸다.

    python src/label_sheet.py results/runs/<run_id>/trials.jsonl \\
        --sheet docs/results/judge_check_v3.csv --judged docs/results/judge_check_v3_judged.csv \\
        --judge-name jdsflash_perfact

시트 열 (judge_check_v2.csv 와 같은 순서에 compressor 추가)
    qid, assignee, type, compressor, fact_idx, key_fact, answer, human, note
    - answer 는 채점 대상 답변 (정답 아님). fact_idx 는 0 부터 (grader index 와 같음)
    - assignee 는 A/B/C/D. 한 문항(같은 qid 의 모든 행)은 한 사람이 맡고,
      type 이 한 사람에게 몰리지 않게 type 별로 돌아가며 배정한다 (행 수도 고르게)
판정 파일 열
    qid, compressor, fact_idx, <judge 이름>   (O | X | ? = judge 응답을 못 읽음)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import TYPES

ASSIGNEES = ("A", "B", "C", "D")
SHEET_FIELDS = ["qid", "assignee", "type", "compressor", "fact_idx", "key_fact", "answer", "human", "note"]


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick_trials(trials: list[dict], base: str = "none") -> list[dict]:
    """base 답변 전부 + base 와 answer_accuracy 가 다른 다른 압축기 답변. qid, base 먼저 순."""
    by_qid = {t["qid"]: t for t in trials if t["compressor"] == base}
    if not by_qid:
        sys.exit(f"{base} 답변이 없습니다")
    picked = list(by_qid.values())
    for t in trials:
        b = by_qid.get(t["qid"])
        if t["compressor"] != base and b is not None and t.get("answer_accuracy") != b.get("answer_accuracy"):
            picked.append(t)
    return sorted(picked, key=lambda t: (t["qid"], t["compressor"] != base, t["compressor"]))


def assign_mixed(qtypes: dict[str, str], rows: dict[str, int]) -> dict[str, str]:
    """문항 -> 담당자. type 순서대로, 같은 type 안에서는 행이 많은 문항부터,
    (그 type 을 가장 적게 맡은 사람, 행이 가장 적은 사람, 이름) 순으로 고른다."""
    load = {a: 0 for a in ASSIGNEES}
    per_type = {a: {} for a in ASSIGNEES}
    order = sorted(qtypes, key=lambda q: (TYPES.index(qtypes[q]) if qtypes[q] in TYPES else len(TYPES),
                                          -rows[q], q))
    out = {}
    for q in order:
        t = qtypes[q]
        a = min(ASSIGNEES, key=lambda a: (per_type[a].get(t, 0), load[a], a))
        out[q] = a
        load[a] += rows[q]
        per_type[a][t] = per_type[a].get(t, 0) + 1
    return out


def build(trials: list[dict]) -> tuple[list[dict], list[dict]]:
    """(시트 행, judge 판정 행)."""
    picked = pick_trials(trials)
    rows: dict[str, int] = {}
    for t in picked:
        rows[t["qid"]] = rows.get(t["qid"], 0) + len(t["fact_results"])
    assignee = assign_mixed({t["qid"]: t["qtype"] for t in picked}, rows)
    sheet, judged = [], []
    for t in picked:
        if not t["fact_results"]:
            sys.exit(f"{t['qid']} {t['compressor']}: fact_results 가 없습니다 (--no-judge 로 돌린 run?)")
        for i, fr in enumerate(t["fact_results"]):
            sheet.append({"qid": t["qid"], "assignee": assignee[t["qid"]], "type": t["qtype"],
                          "compressor": t["compressor"], "fact_idx": i, "key_fact": fr["fact"],
                          "answer": t["response"], "human": "", "note": ""})
            s = fr["satisfied"]
            judged.append({"qid": t["qid"], "compressor": t["compressor"], "fact_idx": i,
                           "judge": "?" if s is None else "O" if s else "X"})
    return sheet, judged


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Excel 에서 한글이 깨지지 않게 BOM 포함 UTF-8
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="run 답변으로 사람 라벨링 시트 + judge 판정 파일 만들기")
    ap.add_argument("trials", help="experiment.py 의 trials.jsonl")
    ap.add_argument("--sheet", required=True, help="라벨링 시트 csv (judge 판정 없음)")
    ap.add_argument("--judged", required=True, help="judge 판정 csv (qid, compressor, fact_idx, <이름>)")
    ap.add_argument("--judge-name", default="judge", help="판정 열 이름 (judge_agreement.py 에 나오는 이름)")
    args = ap.parse_args()

    trials = load_jsonl(Path(args.trials))
    sheet, judged = build(trials)
    if Path(args.sheet).exists():
        sys.exit(f"{args.sheet} 가 이미 있습니다 (사람 라벨을 덮어쓰지 않도록 멈춤)")
    write_csv(Path(args.sheet), sheet, SHEET_FIELDS)
    for r in judged:
        r[args.judge_name] = r.pop("judge")
    write_csv(Path(args.judged), judged, ["qid", "compressor", "fact_idx", args.judge_name])

    extra = [r for r in sheet if r["compressor"] != "none"]
    print(f"시트 {args.sheet}: {len(sheet)}행 (none {len(sheet) - len(extra)}, 정확도가 바뀐 압축기 답변 {len(extra)})")
    for a in ASSIGNEES:
        mine = [r for r in sheet if r["assignee"] == a]
        types = {t: len({r["qid"] for r in mine if r["type"] == t}) for t in TYPES}
        print(f"  {a}: {len(mine)}행, 문항 {len({r['qid'] for r in mine})}개  type {types}")
    print(f"판정 {args.judged}: {sum(r[args.judge_name] == '?' for r in judged)}행이 '?' (judge 응답 못 읽음)")


if __name__ == "__main__":
    main()
