"""
멀티턴 replay 통계: 쌍체 부트스트랩, 시나리오 군집 부트스트랩, 비열등 판정.

짝 = (시나리오, 턴, sample) 이 같은 none trial 과 압축 trial.
    주 판정 (unit="turn")       (시나리오, 턴) 단위로 sample 을 평균한 차이를 재추출한다.
                                같은 턴의 sample 끼리는 독립이 아니라서 sample 을 단위로 쓰지 않는다.
    보조 (unit="scenario")      시나리오 단위로 재추출하는 군집 부트스트랩. 같은 시나리오 안의 턴들도 독립이 아니다.
                                시나리오 수가 적으면(파일럿 3개) 구간이 넓고 불안정하다.

비열등: 차이(압축 − none) 신뢰구간 하한 > −margin × none 정확도 이면 "비열등".
백분위수 계산은 싱글턴 stats.percentile 을 그대로 쓴다.
"""

from __future__ import annotations

import random
from collections import defaultdict

from stats import percentile


def pair_rows(rows: list[dict], comp: str, base: str = "none", base_sample: int | None = None) -> list[tuple[dict, dict]]:
    """(base trial, comp trial) 짝. answer_accuracy 가 None(채점 실패)인 짝은 뺀다.
    base_sample 을 주면 base 는 그 sample 로 고정한다 (none 대 none 잡음 기준선용)."""
    by_key = {}
    for r in rows:
        if r["compressor"] == base and (base_sample is None or r["sample_idx"] == base_sample):
            by_key[(r["scenario_id"], r["turn"], r["sample_idx"] if base_sample is None else None)] = r
    out = []
    for r in rows:
        if r["compressor"] != comp:
            continue
        if comp == base and base_sample is not None and r["sample_idx"] == base_sample:
            continue
        b = by_key.get((r["scenario_id"], r["turn"], r["sample_idx"] if base_sample is None else None))
        if b is None or b.get("answer_accuracy") is None or r.get("answer_accuracy") is None:
            continue
        out.append((b, r))
    return out


def _units(pairs, unit: str) -> dict:
    """unit 별 [(base_acc, comp_acc), ...]."""
    groups = defaultdict(list)
    for b, c in pairs:
        key = (c["scenario_id"], c["turn"]) if unit == "turn" else c["scenario_id"]
        groups[key].append((b["answer_accuracy"], c["answer_accuracy"]))
    return groups


def bootstrap_diff(pairs, unit: str = "turn", boot: int = 10000, seed: int = 42, level: float = 0.95) -> dict:
    """정확도 차이(압축 − base)의 점추정과 부트스트랩 구간. 점추정은 모든 짝의 평균."""
    if not pairs:
        return {"n_pairs": 0, "n_units": 0}
    groups = _units(pairs, unit)
    keys = sorted(groups)

    def stat(sample_keys):
        vals = [v for k in sample_keys for v in groups[k]]
        base = sum(b for b, _ in vals) / len(vals)
        comp = sum(c for _, c in vals) / len(vals)
        return base, comp, comp - base

    base, comp, diff = stat(keys)
    rng = random.Random(seed)
    diffs = []
    for _ in range(boot):
        diffs.append(stat([keys[rng.randrange(len(keys))] for _ in keys])[2])
    a = (1 - level) / 2
    return {
        "unit": unit, "n_pairs": len(pairs), "n_units": len(keys),
        "base_accuracy": round(base, 4), "comp_accuracy": round(comp, 4), "diff": round(diff, 4),
        "diff_ci": [round(percentile(diffs, a), 4), round(percentile(diffs, 1 - a), 4)],
        "retention_pct": round(100 * comp / base, 2) if base > 0 else None,
    }


def non_inferiority(res: dict, margin: float) -> dict:
    """하한 > −margin × base 정확도 이면 비열등."""
    if not res.get("n_pairs"):
        return {"margin": margin, "threshold": None, "non_inferior": None}
    threshold = -margin * res["base_accuracy"]
    return {"margin": margin, "threshold": round(threshold, 4), "non_inferior": res["diff_ci"][0] > threshold}
