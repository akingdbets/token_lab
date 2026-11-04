"""
test 답변으로 judge 검증 세트 만들기 (블라인드 라벨링, API 호출 없음)

test_v1(생각 끔)과 luna 기본 설정 run 에서 judge 가 채점한 key_fact 단위 판정을 모아 층화 추출한다.
NOT FOUND 답변은 judge 를 부르지 않았으므로 빠진다. judge 응답을 못 읽은 fact 도 뺀다.

    EVAL_DIR=data/evalsets/claude-v1 python src/judge_check_test.py \\
        --run 생각끔=results/runs/20261102-205826 --run 기본=results/runs/luna-default-20261103

층화 (random.Random(seed)):
    - judge YES 40 / NO 40
    - 각 판정 안에서 압축 조건 5개 · 유형 4개 · 설정 2개가 고르게 (조건 8, 유형 10, 설정 20 이 목표)
    - 부분 점수 문항(0 < answer_accuracy < 1)의 fact 를 판정마다 최소 PARTIAL_MIN 행
    - 한 trial(설정, 문항, 조건)에서는 한 행, 한 문항은 최대 2행
    판정 NO 는 조건별 개수가 적어(rule 7) 목표를 못 채우면 다른 조건으로 채운다.
담당자 A~D 는 판정·조건이 고르게 돌아가도록 20행씩. 시트의 행 순서는 섞는다 (판정이 줄지어 나오지 않게).

출력
    시트  docs/results/judge_check_test.csv      judge 판정 없음
    정답  docs/results/judge_check_test_key.csv  row_id 로 judge 판정·원래 기록 연결
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment import load_items

COMPRESSORS = ("none", "rule", "llmlingua2_r50", "llmlingua2_r30", "rule>llmlingua2")
COND_LABEL = {"none": "none", "rule": "rule", "llmlingua2_r50": "LL2-r50", "llmlingua2_r30": "LL2-r30",
              "rule>llmlingua2": "rule>LL2"}
TYPES = ("fact", "code", "procedure", "multi")
ASSIGNEES = ("A", "B", "C", "D")
N_PER_LABEL = 40
PARTIAL_MIN = 12
SHEET_FIELDS = ["row_id", "담당자", "qid", "유형", "설정", "압축 조건", "fact_idx", "질문", "핵심 사실", "참고 정답",
                "모델 답변", "human", "메모"]
KEY_FIELDS = ["row_id", "judge", "run", "compressor", "answer_accuracy", "partial"]


def candidates(runs: list[tuple[str, Path]], items: dict) -> list[dict]:
    out = []
    for setting, run in runs:
        for line in open(run / "trials.jsonl", encoding="utf-8"):
            t = json.loads(line)
            if t["compressor"] not in COMPRESSORS or t["not_found"] or t["qid"] not in items:
                continue
            acc = t.get("answer_accuracy")
            for i, f in enumerate(t.get("fact_results") or []):
                if f.get("satisfied") is None:
                    continue
                assert f["fact"] == items[t["qid"]]["key_facts"][i], (t["qid"], i)
                out.append({"setting": setting, "run": run.name, "qid": t["qid"], "type": t["qtype"],
                            "compressor": t["compressor"], "fact_idx": i, "fact": f["fact"],
                            "judge": "O" if f["satisfied"] else "X", "acc": acc,
                            "partial": acc is not None and 0 < acc < 1, "response": t["response"]})
    return out


def pick(pool: list[dict], n: int, settings: list[str], rng: random.Random, taken: Counter, used: set) -> list[dict]:
    """한 판정(YES 또는 NO) 안에서 n 행. 부분 점수 행을 먼저 PARTIAL_MIN 까지, 그다음 고르게.
    매번 고를 수 있는 후보 중 (조건, 유형, 설정) 의 지금까지 뽑힌 수가 가장 적은 것을 고른다
    (같으면 섞인 순서). 그래서 드문 칸은 가진 만큼 다 들어가고, 나머지는 고르게 채워진다."""
    rng.shuffle(pool)
    keys = ("compressor", "type", "setting")
    cnt = {k: Counter() for k in keys}
    chosen = []

    def ok(c):
        return (c["setting"], c["qid"], c["compressor"]) not in used and taken[c["qid"]] < 2

    def take_best(cands):
        best = min((c for c in cands if ok(c)), key=lambda c: tuple(cnt[k][c[k]] for k in keys), default=None)
        if best is None:
            return False
        chosen.append(best)
        used.add((best["setting"], best["qid"], best["compressor"]))
        taken[best["qid"]] += 1
        for k in keys:
            cnt[k][best[k]] += 1
        return True

    partial = [c for c in pool if c["partial"]]
    while sum(x["partial"] for x in chosen) < PARTIAL_MIN and take_best(partial):
        pass
    while len(chosen) < n and take_best(pool):
        pass
    return chosen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, metavar="설정=RUN_DIR")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sheet", default="docs/results/judge_check_test.csv")
    ap.add_argument("--key", default="docs/results/judge_check_test_key.csv")
    args = ap.parse_args()
    runs = [(s, Path(p)) for s, p in (r.split("=", 1) for r in args.run)]
    items = {it["id"]: it for it in load_items("test", None, None)}
    pool = candidates(runs, items)
    rng = random.Random(args.seed)
    taken, used = Counter(), set()
    rows = []
    for j in ("X", "O"):                   # NO 가 적으므로 먼저 고른다
        rows += pick([c for c in pool if c["judge"] == j], N_PER_LABEL, [s for s, _ in runs], rng, taken, used)

    # 담당자: (판정, 조건, 유형) 순으로 늘어놓고 돌아가며 배정 -> 사람마다 판정·조건이 고르게
    rows.sort(key=lambda r: (r["judge"], r["compressor"], r["type"], r["qid"]))
    for i, r in enumerate(rows):
        r["assignee"] = ASSIGNEES[i % len(ASSIGNEES)]
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["row_id"] = f"T{i:03d}"
    rows.sort(key=lambda r: (r["assignee"], r["row_id"]))

    with open(args.sheet, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(SHEET_FIELDS)
        for r in rows:
            it = items[r["qid"]]
            w.writerow([r["row_id"], r["assignee"], r["qid"], r["type"], r["setting"], COND_LABEL[r["compressor"]],
                        r["fact_idx"], it["question"], r["fact"], it["answer"], r["response"], "", ""])
    with open(args.key, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(KEY_FIELDS)
        for r in sorted(rows, key=lambda r: r["row_id"]):
            w.writerow([r["row_id"], r["judge"], r["run"], r["compressor"], r["acc"], int(r["partial"])])

    print("후보 fact", len(pool), Counter(c["judge"] for c in pool))
    for name, key in (("판정", "judge"), ("조건", "compressor"), ("유형", "type"), ("설정", "setting"),
                      ("담당자", "assignee")):
        print(name, dict(Counter(r[key] for r in rows)))
    for j in ("O", "X"):
        rs = [r for r in rows if r["judge"] == j]
        print(f"judge {j}: 조건 {dict(Counter(r['compressor'] for r in rs))} 유형 {dict(Counter(r['type'] for r in rs))} "
              f"설정 {dict(Counter(r['setting'] for r in rs))} 부분 점수 {sum(r['partial'] for r in rs)}")
    for a in ASSIGNEES:
        rs = [r for r in rows if r["assignee"] == a]
        print(f"담당자 {a}: {len(rs)}행, 판정 {dict(Counter(r['judge'] for r in rs))}, 조건 {dict(Counter(r['compressor'] for r in rs))}")
    print("문항 수", len({r["qid"] for r in rows}), "저장", args.sheet, args.key)


if __name__ == "__main__":
    main()
