"""
반복 실행 집계: 같은 설정으로 여러 번 돌린 run 을 묶어 평균·표준편차와 none 대비 검정을 낸다 (API 호출 없음)

    python src/repeat_stats.py results/runs/<run1> results/runs/<run2> results/runs/<run3> [--out stats.json]

지표 (run 마다 summary.json 값 -> 평균, 표본 표준편차, 최소, 최대)
    input_reduction_pct, billed_input_reduction_pct, answer_accuracy, answer_accuracy_retention_pct,
    semantic_loss, not_found_rate, memory_suspect_rate, type 별 answer_accuracy

검정 (압축기마다 none 과 짝지음, 양측)
    Wilcoxon 부호 순위 검정: 문항별 정확도를 run 평균한 값의 차이 (압축 − none). 차이 0 인 문항은 뺀다.
        동점은 평균 순위, p 값은 정확 분포 (문항 수가 적어 정규 근사를 쓰지 않는다)
    McNemar 정확 검정: (문항, run) 짝마다 완전 정답(answer_accuracy == 1) 여부.
        b = none 정답·압축 오답, c = none 오답·압축 정답, p = 이항 분포 B(b+c, 0.5) 양측.
        같은 문항의 여러 run 은 독립이 아니므로 run 별 McNemar 도 함께 낸다
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

METRICS = ("input_reduction_pct", "billed_input_reduction_pct", "answer_accuracy",
           "answer_accuracy_retention_pct", "semantic_loss", "not_found_rate", "memory_suspect_rate")


def describe(xs: list) -> dict:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    return {"n": len(xs), "mean": round(st.mean(xs), 4),
            "std": round(st.stdev(xs), 4) if len(xs) > 1 else None,
            "min": round(min(xs), 4), "max": round(max(xs), 4)}


def mcnemar_exact(b: int, c: int) -> float | None:
    """양측 정확 McNemar p 값. b+c == 0 이면 None (불일치 짝 없음)."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, p), 6)


def wilcoxon_exact(diffs: list[float]) -> dict:
    """Wilcoxon 부호 순위 검정 (양측, 정확 분포, 동점은 평균 순위, 0 은 제외)."""
    d = [x for x in diffs if abs(x) > 1e-12]
    n = len(d)
    if n == 0:
        return {"n_nonzero": 0, "w_plus": None, "w_minus": None, "p": None}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(d[order[j + 1]]) - abs(d[order[i]])) < 1e-12:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    # 순위 x2 는 정수 -> 부분집합 합의 분포를 세어 정확 p
    r2 = [int(round(2 * r)) for r in ranks]
    total = sum(r2)
    counts = [0] * (total + 1)
    counts[0] = 1
    for r in r2:
        for s in range(total, r - 1, -1):
            counts[s] += counts[s - r]
    w2 = int(round(2 * w_plus))
    all_ = 2 ** n
    lower = sum(counts[: w2 + 1]) / all_
    upper = sum(counts[w2:]) / all_
    return {"n_nonzero": n, "w_plus": w_plus, "w_minus": total / 2 - w_plus,
            "p": round(min(1.0, 2 * min(lower, upper)), 6)}


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    t = [json.loads(l) for l in open(run_dir / "trials.jsonl", encoding="utf-8") if l.strip()]
    return s, t


def aggregate(runs: list[tuple[dict, list[dict]]], base: str = "none") -> dict:
    comps = list(dict.fromkeys(c for s, _ in runs for c in s["results"]))
    out = {"n_runs": len(runs), "compressors": {}}
    for c in comps:
        rs = [s["results"][c] for s, _ in runs if c in s["results"]]
        entry = {"metrics": {m: describe([r.get(m) for r in rs]) for m in METRICS}}
        types = list(dict.fromkeys(t for r in rs for t in r.get("by_type", {})))
        entry["by_type_accuracy"] = {t: describe([r["by_type"].get(t, {}).get("answer_accuracy") for r in rs])
                                     for t in types}
        if c != base:
            entry["tests"] = paired_tests([t for _, t in runs], base, c)
        out["compressors"][c] = entry
    return out


def paired_tests(trial_sets: list[list[dict]], base: str, comp: str) -> dict:
    acc = lambda ts, name: {t["qid"]: t["answer_accuracy"] for t in ts if t["compressor"] == name}
    per_run = [(acc(ts, base), acc(ts, comp)) for ts in trial_sets]
    # Wilcoxon: 문항별 run 평균 정확도
    qids = sorted(set.intersection(*[{q for q in b if b[q] is not None and q in c and c[q] is not None}
                                     for b, c in per_run]))
    mean = lambda q, k: st.mean(pr[k][q] for pr in per_run)
    diffs = [mean(q, 1) - mean(q, 0) for q in qids]
    # McNemar: (문항, run) 짝의 완전 정답 여부
    def bc(pairs):
        b = sum(x == 1.0 and y != 1.0 for x, y in pairs)
        c = sum(x != 1.0 and y == 1.0 for x, y in pairs)
        return b, c
    pooled = [(b[q], c[q]) for b, c in per_run for q in qids]
    b, c = bc(pooled)
    runs_mc = []
    for bb, cc in per_run:
        b1, c1 = bc([(bb[q], cc[q]) for q in qids])
        runs_mc.append({"b": b1, "c": c1, "p": mcnemar_exact(b1, c1)})
    return {
        "n_items": len(qids),
        "mean_diff": round(st.mean(diffs), 4) if diffs else None,
        "wilcoxon": wilcoxon_exact(diffs),
        "mcnemar_pooled": {"b_base_only": b, "c_comp_only": c, "p": mcnemar_exact(b, c)},
        "mcnemar_per_run": runs_mc,
        "items_worse": [q for q, d in zip(qids, diffs) if d < 0],
    }


def main():
    ap = argparse.ArgumentParser(description="반복 실행 run 묶어 평균·표준편차·검정")
    ap.add_argument("runs", nargs="+", help="results/runs/<run_id> 폴더 (2개 이상)")
    ap.add_argument("--base", default="none")
    ap.add_argument("--out", help="결과 json 경로")
    args = ap.parse_args()
    if len(args.runs) < 2:
        sys.exit("run 이 2개 이상 필요합니다")
    runs = [load_run(Path(r)) for r in args.runs]
    res = {"runs": args.runs, **aggregate(runs, args.base)}
    text = json.dumps(res, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    for c, e in res["compressors"].items():
        m = e["metrics"]
        fmt = lambda k: "-" if m[k]["mean"] is None else f"{m[k]['mean']}±{m[k]['std']}"
        line = (f"{c:<16} 절감 {fmt('input_reduction_pct')}  정확도 {fmt('answer_accuracy')}  "
                f"유지율 {fmt('answer_accuracy_retention_pct')}  NOT FOUND {fmt('not_found_rate')}")
        if "tests" in e:
            t = e["tests"]
            line += f"  Wilcoxon p={t['wilcoxon']['p']}  McNemar p={t['mcnemar_pooled']['p']}"
        print(line)


if __name__ == "__main__":
    main()
