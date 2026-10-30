"""
압축기별 통계: bootstrap 신뢰구간, McNemar 검정, 비용 환산 (API 호출 없음)

기존 run 의 trials.jsonl 로 none 과 같은 문항끼리 짝지어 계산한다. 끊겨서 나눠 돌린 run 은 여러 개를 넘겨 합친다.

    python src/stats.py results/runs/<run_id> [<run_id2> ...] [--exclude c0015,c0039] [--by-type]
        [--price-in 1.25 --price-out 10] [--binary full|correct] [--boot 10000] [--seed 42]

지표 (정의는 experiment.summarize 와 같다)
    answer_accuracy          key_facts 충족 비율의 평균
    retention_pct            짝지은 문항의 압축 정확도 / none 정확도 × 100
    diff                     짝지은 문항의 압축 정확도 − none 정확도
    input_reduction_pct      입력 토큰 합의 절감률 (문항별 비율의 평균이 아니라 합의 비율)
신뢰구간: 문항을 복원 추출하는 paired bootstrap (percentile, 기본 95%). 압축기와 none 을 같은 문항 묶음으로 뽑는다
McNemar: 문항별 이진 정답(--binary)을 짝지어 정확 이항 검정(양측). b = none 만 맞힘, c = 압축기만 맞힘
    full     answer_accuracy == 1 (key_facts 를 모두 충족, 기본)
    correct  O/X judge(또는 단어 일치) 판정 (summary 의 binary_accuracy)
비용: 서버가 보고한 답변 토큰(prompt_tokens, completion_tokens)의 문항 평균. --price-in/--price-out (1M 토큰당 달러)을
    주면 1천 질의당 비용과 none 대비 절감액을 낸다. LLMLingua-2 처럼 로컬에서 도는 압축 비용(compress_sec)은 따로 적는다
결과: 표를 출력하고 첫 run 폴더에 stats.json 을 쓴다 (--out 으로 바꿀 수 있다).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path


def load_trials(run_dirs: list[Path]) -> list[dict]:
    """여러 run 의 trial 을 합친다. 같은 (문항, 압축기) 가 두 번 나오면 멈춘다."""
    seen = {}
    for run in run_dirs:
        for line in (run / "trials.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            t = json.loads(line)
            key = (t["qid"], t["compressor"])
            if key in seen:
                sys.exit(f"같은 문항·압축기가 두 run 에 있습니다: {key} ({seen[key]['run_id']}, {t['run_id']})")
            seen[key] = t
    return list(seen.values())


def fallback_qids(trials: list[dict]) -> set[str]:
    """압축 결과를 버리고 원문을 쓴(원문 대체) 문항."""
    return {t["qid"] for t in trials
            if ((t.get("info") or {}).get("trace") or {}).get("used_original")
            and t["compressor"] not in ("none", "empty")}


def is_right(t: dict, binary: str) -> bool:
    if binary == "correct":
        return bool(t.get("correct"))
    return t.get("answer_accuracy") is not None and t["answer_accuracy"] >= 1.0


def mcnemar_exact(b: int, c: int) -> float:
    """불일치 쌍 b, c 에 대한 정확 McNemar 검정(이항, 양측) p 값."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def percentile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def paired_stats(pairs: list[tuple[dict, dict]], boot: int, seed: int, level: float) -> dict:
    """pairs: [(none trial, 압축기 trial)]. 정확도·유지율·차이·절감률의 점추정과 bootstrap 신뢰구간."""
    def point(ps):
        base = sum(b["answer_accuracy"] for b, _ in ps) / len(ps)
        comp = sum(c["answer_accuracy"] for _, c in ps) / len(ps)
        raw = sum(c["input_tokens_raw"] for _, c in ps)
        red = 100 * (1 - sum(c["input_tokens"] for _, c in ps) / raw) if raw else None
        return {"answer_accuracy": comp, "baseline_answer_accuracy": base, "diff": comp - base,
                "retention_pct": 100 * comp / base if base > 0 else None, "input_reduction_pct": red}

    est = point(pairs)
    rng = random.Random(seed)
    draws = {k: [] for k in est}
    for _ in range(boot):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        for k, v in point(sample).items():
            if v is not None:
                draws[k].append(v)
    a = (1 - level) / 2
    out = {}
    for k, v in est.items():
        ci = [percentile(draws[k], a), percentile(draws[k], 1 - a)] if draws[k] else [None, None]
        out[k] = {"value": None if v is None else round(v, 4),
                  "ci": [None if x is None else round(x, 4) for x in ci]}
    return out


def cost(trials: list[dict], price_in: float | None, price_out: float | None) -> dict:
    n = len(trials)
    p = sum(t.get("prompt_tokens") or 0 for t in trials) / n
    c = sum(t.get("completion_tokens") or 0 for t in trials) / n
    out = {"prompt_tokens_mean": round(p, 1), "completion_tokens_mean": round(c, 1),
           "compress_sec_mean": round(sum(t.get("compress_sec") or 0 for t in trials) / n, 3)}
    if price_in is not None:
        out["usd_per_1k_queries"] = round(1000 * (p * price_in + c * (price_out or 0)) / 1e6, 4)
    return out


def compare(trials: list[dict], comps: list[str], args) -> dict:
    base = {t["qid"]: t for t in trials if t["compressor"] == "none" and t.get("answer_accuracy") is not None}
    if not base:
        sys.exit("none 결과가 없습니다 (짝지을 기준이 필요)")
    out = {"none": {"n": len(base), "cost": cost(list(base.values()), args.price_in, args.price_out)}}
    for comp in comps:
        rs = [t for t in trials if t["compressor"] == comp and t.get("answer_accuracy") is not None
              and t["qid"] in base]
        if not rs:
            continue
        pairs = [(base[t["qid"]], t) for t in rs]
        b = sum(is_right(n, args.binary) and not is_right(c, args.binary) for n, c in pairs)
        c_ = sum(not is_right(n, args.binary) and is_right(c, args.binary) for n, c in pairs)
        s = {"n": len(pairs), **paired_stats(pairs, args.boot, args.seed, args.level),
             "mcnemar": {"binary": args.binary, "none_only": b, "compressor_only": c_,
                         "p_value": round(mcnemar_exact(b, c_), 4)},
             "cost": cost([c for _, c in pairs], args.price_in, args.price_out)}
        base_cost = cost([n for n, _ in pairs], args.price_in, args.price_out)
        if "usd_per_1k_queries" in s["cost"]:
            saved = base_cost["usd_per_1k_queries"] - s["cost"]["usd_per_1k_queries"]
            s["cost"]["usd_saved_per_1k_queries"] = round(saved, 4)
            s["cost"]["usd_saved_pct"] = (round(100 * saved / base_cost["usd_per_1k_queries"], 2)
                                          if base_cost["usd_per_1k_queries"] else None)
        out[comp] = s
    return out


def fmt_ci(d: dict, pct: bool = False) -> str:
    if d["value"] is None:
        return "-"
    f = (lambda x: f"{x:.1f}") if pct else (lambda x: f"{x:.3f}")
    return f"{f(d['value'])} [{f(d['ci'][0])}, {f(d['ci'][1])}]"


def print_table(res: dict, title: str):
    print(f"\n== {title}")
    print(f"{'압축기':<16}{'n':>4}  {'정확도 [CI]':<24}{'유지율% [CI]':<24}{'입력 절감% [CI]':<24}"
          f"{'McNemar b/c p':<16}{'답변 입력 토큰':>12}")
    for comp, s in res.items():
        if comp == "none":
            print(f"{'none':<16}{s['n']:>4}  {'':<24}{'':<24}{'':<24}{'':<16}{s['cost']['prompt_tokens_mean']:>12}")
            continue
        m = s["mcnemar"]
        print(f"{comp:<16}{s['n']:>4}  {fmt_ci(s['answer_accuracy']):<24}{fmt_ci(s['retention_pct'], True):<24}"
              f"{fmt_ci(s['input_reduction_pct'], True):<24}"
              f"{m['none_only']}/{m['compressor_only']} {m['p_value']:<10}{s['cost']['prompt_tokens_mean']:>12}")


def main():
    ap = argparse.ArgumentParser(description="압축기별 bootstrap 신뢰구간·McNemar·비용 환산")
    ap.add_argument("run_dirs", nargs="+", type=Path, help="results/runs/<run_id> (여러 개면 합친다)")
    ap.add_argument("--exclude", default="", help="뺄 문항 (쉼표 구분)")
    ap.add_argument("--exclude-fallback", action="store_true", help="원문 대체가 일어난 문항을 뺀다")
    ap.add_argument("--by-type", action="store_true", help="유형별로도 계산")
    ap.add_argument("--binary", choices=("full", "correct"), default="full", help="McNemar 이진 정답 기준")
    ap.add_argument("--boot", type=int, default=10000, help="bootstrap 반복 수")
    ap.add_argument("--level", type=float, default=0.95, help="신뢰수준")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--price-in", type=float, help="입력 1M 토큰당 달러")
    ap.add_argument("--price-out", type=float, help="출력 1M 토큰당 달러")
    ap.add_argument("--out", type=Path, help="결과 JSON (기본: 첫 run 폴더/stats.json)")
    args = ap.parse_args()

    trials = load_trials(args.run_dirs)
    excluded = {q.strip() for q in args.exclude.split(",") if q.strip()}
    if args.exclude_fallback:
        excluded |= fallback_qids(trials)
    trials = [t for t in trials if t["qid"] not in excluded]
    comps = [c for c in dict.fromkeys(t["compressor"] for t in trials) if c != "none"]

    out = {"runs": [r.as_posix() for r in args.run_dirs], "excluded": sorted(excluded),
           "binary": args.binary, "boot": args.boot, "level": args.level, "seed": args.seed,
           "price_in": args.price_in, "price_out": args.price_out,
           "all": compare(trials, comps, args)}
    print_table(out["all"], f"전체 (제외 {len(excluded)}문항: {', '.join(sorted(excluded)) or '-'})")
    if args.by_type:
        out["by_type"] = {}
        for qtype in dict.fromkeys(t["qtype"] for t in trials):
            out["by_type"][qtype] = compare([t for t in trials if t["qtype"] == qtype], comps, args)
            print_table(out["by_type"][qtype], qtype)

    path = args.out or args.run_dirs[0] / "stats.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {path.as_posix()}")


if __name__ == "__main__":
    main()
