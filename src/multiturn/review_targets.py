"""
multiturn-v2 사람 검수 대상 표시 (API 호출 없음). 턴의 review.target 에 사유 목록을 쓴다.

    python src/multiturn/review_targets.py data/evalsets/multiturn-v2/v2_*.json

사유 (2026-11-28 결정)
    (a) 질문을 고친 턴        review.question_changed, 또는 edits 기록에서 질문을 바꾼 턴 (standalone_same_fact 확인용)
    (b) 대안 판정            fact_meta 에 accept_alternatives 가 있는 턴 (alt_judge_label)
    (c) 남은 의심 턴          suspect_reasons (기억 답·간접 의존·recall knowledge 포함), 한 턴 한 주제 경고, grounded_memory 표시
    (d) 무작위 표본           (a)~(c) 가 아닌 턴에서 시나리오마다 10% (최소 1턴), 시드 고정
다시 돌리면 review.target 을 새로 계산한다 (같은 데이터·시드면 같은 결과).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SEED = 20261128
SAMPLE_RATE = 0.10
# 1차 손 수정(샘플 2개)에서 질문을 바꾼 턴 (그때는 question_changed 표시가 없었다)
ROUND1_QUESTION_CHANGED = {"v2_01_auth_switch": {13, 18}, "v2_02_response_design": {15, 16, 19}}


def reasons_abc(s: dict, t: dict, topic_turns: set) -> list[str]:
    from multiturn.scenario_v2 import suspect_reasons
    r = []
    rv = t.get("review") or {}
    if rv.get("question_changed") or t["turn"] in ROUND1_QUESTION_CHANGED.get(s["scenario_id"], set()):
        r.append("a: 질문 수정 (standalone_same_fact 확인)")
    if any((m or {}).get("accept_alternatives") for m in t.get("fact_meta") or []):
        r.append("b: 대안 판정 (alt_judge_label)")
    sus = suspect_reasons(s, t)
    if t["turn"] in topic_turns:
        sus.append("한 턴 한 주제 경고")
    if "grounded_memory" in (rv.get("flags") or []) and not any("grounded" in x for x in sus):
        sus.append("grounded_memory 표시")
    sus = [x for x in sus if not x.startswith("대안 판정")]
    if sus:
        r.append("c: " + "; ".join(sus))
    return r


def mark(scenarios: list[dict], seed: int = SEED, rate: float = SAMPLE_RATE) -> dict:
    from multiturn.scenario_v2 import topic_warnings
    rng = random.Random(seed)
    counts = {}
    for s in sorted(scenarios, key=lambda x: x["scenario_id"]):
        topic_turns = {int(w.split(" 턴 ")[1].split(":")[0]) for w in topic_warnings(s)}
        rest = []
        c = {"a": 0, "b": 0, "c": 0, "d": 0, "turns": len(s["turns"])}
        for t in s["turns"]:
            r = reasons_abc(s, t, topic_turns)
            rv = t.setdefault("review", {})
            rv["target"] = r
            for x in r:
                c[x[0]] += 1
            if not r:
                rest.append(t)
        n = max(1, round(len(rest) * rate)) if rest else 0
        for t in rng.sample(rest, n):
            t["review"]["target"] = [f"d: 무작위 표본 (시드 {seed})"]
            c["d"] += 1
        c["targets"] = sum(1 for t in s["turns"] if t["review"]["target"])
        counts[s["scenario_id"]] = c
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description="multiturn-v2 검수 대상 표시")
    ap.add_argument("scenarios", nargs="+")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args(argv)
    data = [(p, json.loads(Path(p).read_text(encoding="utf-8"))) for p in a.scenarios]
    counts = mark([s for _, s in data], a.seed)
    for p, s in data:
        Path(p).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
