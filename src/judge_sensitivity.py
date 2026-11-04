"""
judge 판정 민감도 분석: 사람 라벨로 잰 judge 의 FN 비율(judge X 중 사람 O)을 key_fact 판정에 적용해
압축 조건별 정확도·유지율과 사전 기준("유지") 판단이 바뀌는지 본다 (API 호출 없음)

    python src/judge_sensitivity.py --run results/runs/luna-default-20261103 --rate 11/40 --rate 13/40

보정 대상
    - judge 가 채점한 trial 의 key_fact 중 judge 가 X(불충족)로 본 것만. 각각 확률 p 로 사실은 O 였다고 본다.
    - NOT FOUND·빈 답처럼 judge 를 거치지 않은 trial(fact_results 가 비어 있음)은 보정하지 않는다.
    - 사람 라벨에서 FP(judge O·사람 X)가 0 이라 O 판정은 내리지 않는다.
두 가지로 계산한다
    - 기대값: trial 정확도 = (충족 + p × judge X 수) / 사실 수. 정확도·유지율과 bootstrap CI
    - 시뮬레이션: judge X 사실을 확률 p 로 뒤집는 표본을 여러 번 뽑아, 표본마다 유지율 CI 와 Holm McNemar 로
      사전 기준을 판단한다 (유지 = 유지율 95% CI 하한 >= 95% 이고 Holm p >= 0.05, test_analysis_plan.md 1절)
bootstrap 은 문항 짝 단위, 같은 시드의 재표본을 보정 전·후에 함께 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys

from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stats import mcnemar_exact

COMPRESSORS = ("rule", "llmlingua2_r50", "llmlingua2_r30", "rule>llmlingua2")
RETAIN_CI_LOW, ALPHA = 95.0, 0.05


def load(run: Path) -> dict:
    """조건 -> qid -> (충족 수, judge X 수, 사실 수, 보정 대상 여부). answer_accuracy 가 없는 trial 은 뺀다."""
    out: dict = {}
    with open(run / "trials.jsonl", encoding="utf-8") as f:
        for t in map(json.loads, f):
            if t.get("answer_accuracy") is None:
                continue
            facts = t.get("fact_results") or []
            total = t.get("total_facts") or len(facts) or 1
            sat = sum(fr.get("satisfied") is True for fr in facts)
            neg = sum(fr.get("satisfied") is False for fr in facts)
            judged = bool(facts) and not t.get("not_found")
            if not judged:
                sat, neg = round(t["answer_accuracy"] * total), 0
            out.setdefault(t["compressor"], {})[t["qid"]] = (sat, neg, total)
    return out


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def analyze(run: Path, rates: list[tuple[str, float]], boot: int = 10000, draws: int = 500, seed: int = 42) -> dict:
    data = load(run)
    comps = [c for c in COMPRESSORS if c in data]
    # stats.py 와 같이 조건마다 none 과 따로 짝짓는다 (answer_accuracy 가 없는 trial 이 있는 문항만 빠진다)
    pairs = {}
    for c in comps:
        qids = sorted(q for q in data["none"] if q in data[c])
        pairs[c] = (np.array([data["none"][q] for q in qids], float), np.array([data[c][q] for q in qids], float))
    rng = np.random.default_rng(seed)
    weights: dict[int, np.ndarray] = {}

    def w_for(n):                                 # bootstrap 재표본의 문항별 뽑힌 횟수 (boot x n), 크기마다 한 번
        if n not in weights:
            r = np.random.default_rng(seed)
            idx = r.integers(0, n, size=(boot, n))
            weights[n] = np.stack([np.bincount(i, minlength=n) for i in idx]).astype(float)
        return weights[n]

    def ci(num, den):                            # num, den: n x D 문항별 정확도 -> 유지율 CI 하한·상한 (D 열마다)
        w = w_for(num.shape[0])
        r = 100 * (w @ num) / (w @ den)
        return np.percentile(r, 2.5, axis=0), np.percentile(r, 97.5, axis=0)

    def draw(a, p):                              # judge X 사실을 확률 p 로 O 로 뒤집은 정확도 (n x draws)
        flips = rng.binomial(a[:, 1].astype(int)[:, None], p, size=(len(a), draws)) if p else np.zeros((len(a), draws))
        return (a[:, 0][:, None] + flips) / a[:, 2][:, None]

    def summarize(p: float):
        res, pv, lows = {}, [], {}
        for c in comps:
            b, a = pairs[c]
            eb, ea = (b[:, 0] + p * b[:, 1]) / b[:, 2], (a[:, 0] + p * a[:, 1]) / a[:, 2]
            lo, hi = ci(ea[:, None], eb[:, None])
            res[c] = {"n": len(a), "acc": ea.mean(), "base": eb.mean(), "ret": 100 * ea.mean() / eb.mean(),
                      "ci": (lo[0], hi[0])}
            db, da = draw(b, p), draw(a, p)
            lows[c] = ci(da, db)[0]
            fb, fa = db >= 1.0 - 1e-9, da >= 1.0 - 1e-9
            pv.append([mcnemar_exact(int((fb[:, d] & ~fa[:, d]).sum()), int((~fb[:, d] & fa[:, d]).sum()))
                       for d in range(draws)])
        adj = np.array([holm(list(row)) for row in np.array(pv).T])           # draws x 조건
        for j, c in enumerate(comps):
            keep = (lows[c] >= RETAIN_CI_LOW) & (adj[:, j] >= ALPHA)
            res[c].update({"holm_p_median": float(np.median(adj[:, j])), "keep_share": float(keep.mean()),
                           "ci_low_median": float(np.median(lows[c]))})
        return res

    allc = ["none", *comps]
    out = {"run": str(run), "n": {c: len(pairs[c][1]) for c in comps}, "boot": boot, "draws": draws, "seed": seed,
           "facts_neg": {c: int(sum(v[1] for v in data[c].values())) for c in allc},
           "facts_total": {c: int(sum(v[2] for v in data[c].values())) for c in allc}, "rates": {}}
    for name, p in [("보정 전", 0.0), *rates]:
        out["rates"][name] = {"p": p, "res": summarize(p)}
    return out


def section(out: dict, fn_counts: tuple[int, int] | None = None) -> list[str]:
    comps = [c for c in COMPRESSORS if c in out["rates"]["보정 전"]["res"]]
    neg = out["facts_neg"]
    lines = ["## 6. 민감도 분석: judge FN 비율로 key_fact 판정 보정", "",
             f"run `{Path(out['run']).name}` (luna 기본, test_v1_default.md). none 과 짝지은 문항 "
             + ", ".join(f"{c} {k}" for c, k in out["n"].items()) + ". "
             f"judge 가 X 로 본 key_fact 는 조건별로 " + ", ".join(f"{c} {neg[c]}" for c in ["none", *comps])
             + " 개다 (사실 전체 " + ", ".join(f"{out['facts_total'][c]}" for c in ["none", *comps]) + ").", "",
             "- 각 judge X 사실이 확률 p 로 사실은 O 라고 보고 다시 계산했다. NOT FOUND·빈 답 trial 은 judge 를 "
             "거치지 않았으므로 보정하지 않는다. FP 가 0 이라 O 판정은 내리지 않는다.",
             f"- 정확도·유지율은 기대값이고, CI 는 문항 짝 bootstrap {out['boot']:,} 회 (시드 {out['seed']}) 다.",
             f"- \"유지\" 판단은 사전 기준(유지율 CI 하한 ≥ 95% 이고 Holm McNemar p ≥ 0.05)이다. McNemar 는 완전 정답 "
             f"이진값이라 기대값으로 계산할 수 없다. 그래서 judge X 사실을 확률 p 로 뒤집은 표본 {out['draws']} 개마다 "
             "판단하고, \"유지\" 로 나온 표본 비율을 적는다.", ""]
    if fn_counts:
        lines += [f"- 사람 라벨 기준 p = {fn_counts[0]}/{fn_counts[1]} (judge X 행 중 사람 O). 시트는 judge X 를 "
                  "따로 40 행 뽑았으므로 judge X 판정 전체에 대한 추정치로 쓴다.", ""]
    lines += ["| p | 조건 | 정확도 (none) | 유지율 [95% CI] | Holm p (중앙값) | 유지 판단 (표본 비율) |",
              "|---|---|---|---|---|---|"]
    for name, r in out["rates"].items():
        for c in comps:
            x = r["res"][c]
            verdict = "유지" if x["keep_share"] >= 0.5 else "손실"
            share = f"{verdict} ({100 * x['keep_share']:.0f}%)" if r["p"] else verdict
            lines.append(f"| {name}{'' if not r['p'] else f' (p = {r['p']:.3f})'} | {c} | {x['acc']:.3f} ({x['base']:.3f}) | "
                         f"{x['ret']:.1f}% [{x['ci'][0]:.1f}, {x['ci'][1]:.1f}] | {x['holm_p_median']:.3g} | {share} |")
    return lines + [""]


def parse_rate(s: str) -> tuple[str, float]:
    return s, float(Fraction(s))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="results/runs/luna-default-20261103")
    ap.add_argument("--rate", action="append", type=parse_rate, help="judge X 중 사람 O 비율 (예: 11/40). 여러 번")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--draws", type=int, default=500)
    args = ap.parse_args()
    out = analyze(Path(args.run), args.rate or [parse_rate("11/40")], args.boot, args.draws)
    print("\n".join(section(out)))


if __name__ == "__main__":
    main()
