"""
key_fact 태그별 집계 분리 (setup 항목)

시나리오 v2 부터 turn["fact_meta"][i]["tags"] 에 "setup" 이 붙을 수 있다. 같은 턴의 사용자 발화에 답이 그대로 있는
설정 확인용 항목이라 기록 압축과 관계없이 맞힐 수 있다. 그래서
    - 주 정확도(answer_accuracy, 유지율, 정확도 유지 확인)는 setup 항목을 빼고 계산한다.
    - setup 항목 정확도는 따로 setup_accuracy 로 낸다.
    - 채점은 setup 항목도 그대로 한다 (fact 별 결과는 행에 남기고 집계에서만 분리).

setup 태그가 없는 턴(v1 시나리오 전부)은 채점 결과를 그대로 쓴다 (answer_accuracy 등이 지금과 같다).
턴의 key_fact 가 전부 setup 이면 주 정확도는 None (주 집계에서 빠진다. 채점 실패와 같은 처리).
"""

from __future__ import annotations

SETUP_TAG = "setup"


def setup_indices(turn: dict) -> set[int]:
    """turn 의 key_facts 가운데 setup 태그가 붙은 항목 번호 (fact_meta 가 없으면 빈 집합)."""
    meta = turn.get("fact_meta") or []
    return {i for i, m in enumerate(meta) if SETUP_TAG in ((m or {}).get("tags") or [])}


def _acc(flags: list) -> tuple[float | None, int, int]:
    if not flags:
        return None, 0, 0
    sat = sum(1 for f in flags if f is True)
    return (None if any(f is None for f in flags) else sat / len(flags)), sat, len(flags)


def split_grade(turn: dict, g) -> dict:
    """채점 결과 g (grader.AnswerAccuracyResult) 를 주 항목·setup 항목으로 나눈 행 필드.

    answer_accuracy / satisfied_facts / total_facts: 주 항목 (setup 제외). setup 이 없으면 g 값 그대로
    answer_accuracy_all / satisfied_facts_all / total_facts_all: setup 포함 전체 (원래 채점 결과)
    setup_accuracy / setup_satisfied / setup_total: setup 항목만 (없으면 None / 0 / 0)
    fact_satisfied: key_fact 별 충족 여부 (채점 그대로), setup_fact_indices: setup 항목 번호
    """
    idx = setup_indices(turn)
    flags = [r.satisfied for r in (getattr(g, "fact_results", None) or [])]
    base = {"answer_accuracy_all": g.answer_accuracy, "satisfied_facts_all": g.satisfied_count,
            "total_facts_all": g.total_count, "fact_satisfied": flags, "setup_fact_indices": sorted(idx)}
    if not idx or len(flags) != g.total_count:
        # setup 이 없거나 fact 별 결과가 없다 (판정 전 실패 등): 원래 값을 그대로 쓴다
        return {**base, "answer_accuracy": g.answer_accuracy, "satisfied_facts": g.satisfied_count,
                "total_facts": g.total_count, "setup_accuracy": None, "setup_satisfied": 0, "setup_total": 0}
    main_acc, main_sat, main_n = _acc([f for i, f in enumerate(flags) if i not in idx])
    s_acc, s_sat, s_n = _acc([f for i, f in enumerate(flags) if i in idx])
    return {**base, "answer_accuracy": main_acc, "satisfied_facts": main_sat, "total_facts": main_n,
            "setup_accuracy": s_acc, "setup_satisfied": s_sat, "setup_total": s_n}


def setup_failed_fields(turn: dict) -> dict:
    """요약 실패 행: 주 정확도와 같이 setup 도 0점 (setup 항목이 있을 때만)."""
    n = len(setup_indices(turn))
    return {"setup_accuracy": 0.0 if n else None, "setup_satisfied": 0, "setup_total": n}
