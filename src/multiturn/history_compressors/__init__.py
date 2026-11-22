"""
대화 기록 압축기 (멀티턴). 인터페이스는 base.py 참고.

이름 문법 (싱글턴 compressors 의 ">" 조합과 같다)
    none
    window(<n>)                   최근 n 턴만 원문 유지
    per_message(<싱글턴 이름>)     과거 user 메시지의 문서 블록에만 싱글턴 압축기 적용 (rule, llmlingua2, rule>llmlingua2 ...)
    a>b                           a 다음 b. 괄호 안의 ">" 는 나누지 않는다: per_message(rule>llmlingua2)

예산형 (기록 토큰 예산 B, budget.py / summary.py). 최근 keep_recent 턴은 넘쳐도 원문으로 남기고 overflow 로 표시
    window_budget(<B>)            최근 턴부터 예산이 찰 때까지 원문
    query_select(<B>)             현재 질문 BM25 로 과거 조각을 골라 <selected_history> 로
    rolling_summary(<B>)          넘치면 오래된 턴을 요약 하나로 다시 씀 (상태형, summarizer 필요)
    frozen_summary(<B>)           넘치면 새 블록만 덧붙임, 쌓여 넘칠 때만 재압축 (상태형, summarizer 필요)
    replay 의 --history-budget 1000,2000 을 주면 예산 없이 쓴 이름(window_budget 등)을 예산마다 펼친다 (expand_budgets)

요약 추론 조건 접미사 (요약형만)
    rolling_summary(2000)[sre=none]   요약기의 reasoning_effort 조건. replay 의 --summary-reasoning-effort server_default,none 을
                                      주면 요약형 이름을 조건마다 펼친다 (expand_summary_efforts). summarizer 는 {조건: Summarizer} 로 넘긴다

    from multiturn.history_compressors import get_history_compressor
    hc = get_history_compressor("window(2)>per_message(rule)")
    res = hc.compress_history(history, current_user)
"""

from __future__ import annotations

import re

from multiturn.history_compressors.base import HistoryChain, HistoryCompressor, HistoryResult, split_turns
from multiturn.history_compressors.budget import QuerySelect, WindowBudget, select_history
from multiturn.history_compressors.simple import (
    CompressorFallbackError, MissingDependencyError, NoHistoryCompression, PerMessage, Window,
)
from multiturn.history_compressors.summary import FrozenSummary, RollingSummary, Summarizer

BUDGET_FAMILIES = {"window_budget": WindowBudget, "query_select": QuerySelect,
                   "rolling_summary": RollingSummary, "frozen_summary": FrozenSummary}
STATEFUL_FAMILIES = ("rolling_summary", "frozen_summary")

_STAGE_RE = re.compile(r"^([a-z_]+)(?:\((.*)\))?$")
_SRE_RE = re.compile(r"^(.*?)\[sre=([a-z_]+)\]$")


def split_sre(spec: str) -> tuple[str, str | None]:
    """"rolling_summary(2000)[sre=none]" -> ("rolling_summary(2000)", "none")."""
    m = _SRE_RE.match(spec.strip())
    return (m.group(1), m.group(2)) if m else (spec.strip(), None)


def split_top_level(spec: str, sep: str = ">") -> list[str]:
    """괄호 밖의 sep 로만 나눈다."""
    parts, depth, cur = [], 0, []
    for ch in spec:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"괄호가 맞지 않습니다: {spec}")
        if ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if depth != 0:
        raise ValueError(f"괄호가 맞지 않습니다: {spec}")
    parts.append("".join(cur).strip())
    if any(not p for p in parts):
        raise ValueError(f"빈 단계가 있습니다: {spec}")
    return parts


def _stage(spec: str, token_counter=None, summarizer=None, keep_recent: int = 1) -> HistoryCompressor:
    m = _STAGE_RE.match(spec)
    if not m:
        raise KeyError(f"알 수 없는 history 압축기: {spec}")
    name, arg = m.group(1), m.group(2)
    if name in BUDGET_FAMILIES:
        if arg is None or not arg.strip().isdigit():
            raise KeyError(f"{name} 는 예산이 필요합니다: {name}(<토큰 수>) 또는 --history-budget")
        cls = BUDGET_FAMILIES[name]
        if name in STATEFUL_FAMILIES:
            return cls(int(arg), summarizer, keep_recent=keep_recent, token_counter=token_counter)
        return cls(int(arg), keep_recent=keep_recent, token_counter=token_counter)
    if name == "none" and arg is None:
        return NoHistoryCompression()
    if name == "window" and arg is not None and arg.strip().isdigit():
        return Window(int(arg))
    if name == "per_message" and arg:
        return PerMessage(arg.strip())
    raise KeyError(f"알 수 없는 history 압축기: {spec} (none | window(n) | per_message(<싱글턴 이름>))")


def get_history_compressor(spec: str, token_counter=None, summarizer=None, keep_recent: int = 1) -> HistoryCompressor:
    """summarizer 는 Summarizer 하나 또는 {요약 reasoning_effort 조건: Summarizer}. 조건 접미사 [sre=...] 로 고른다."""
    base, effort = split_sre(spec)
    if isinstance(summarizer, dict):
        if effort is None:
            summarizer = summarizer.get(None) if None in summarizer else (
                next(iter(summarizer.values())) if len(summarizer) == 1 else None)
        else:
            if effort not in summarizer:
                raise KeyError(f"{spec}: 요약 조건 {effort} 의 요약기가 없습니다 (있음: {sorted(map(str, summarizer))})")
            summarizer = summarizer[effort]
    stages = [_stage(s, token_counter, summarizer, keep_recent) for s in split_top_level(base)]
    if len(stages) > 1 and any(getattr(s, "stateful", False) for s in stages):
        raise ValueError(f"상태형 압축기는 체인으로 쓸 수 없습니다: {spec}")
    if effort is not None and not getattr(stages[0], "stateful", False):
        raise ValueError(f"[sre=...] 는 요약형 압축기에만 붙입니다: {spec}")
    comp = stages[0] if len(stages) == 1 else HistoryChain(stages)
    comp.name = spec.strip()
    return comp


def family_of(spec: str) -> str:
    spec = split_sre(spec)[0]
    m = _STAGE_RE.match(spec.strip())
    return m.group(1) if m and ">" not in spec else spec


def summary_effort_of(spec: str) -> str | None:
    return split_sre(spec)[1]


def label_of(spec: str) -> str:
    """예산을 뺀 비교표 이름: "rolling_summary(2000)[sre=none]" -> "rolling_summary[sre=none]"."""
    base, effort = split_sre(spec)
    fam = family_of(base)
    lab = fam if budget_of(base) else base
    return f"{lab}[sre={effort}]" if effort else lab


def budget_of(spec: str) -> int | None:
    spec = split_sre(spec)[0]
    m = _STAGE_RE.match(spec.strip())
    if m and m.group(1) in BUDGET_FAMILIES and m.group(2) and m.group(2).isdigit():
        return int(m.group(2))
    return None


def is_stateful(spec: str) -> bool:
    return family_of(spec) in STATEFUL_FAMILIES


def expand_budgets(names: list[str], budgets: list[int]) -> list[str]:
    """예산 없이 쓴 예산형 이름을 예산마다 펼친다. 예산이 필요한데 budgets 가 비면 오류."""
    out = []
    for n in names:
        if n in BUDGET_FAMILIES:
            if not budgets:
                raise ValueError(f"{n} 는 --history-budget 이 필요합니다")
            out.extend(f"{n}({b})" for b in budgets)
        else:
            out.append(n)
    seen = set()
    return [n for n in out if not (n in seen or seen.add(n))]


def expand_summary_efforts(names: list[str], efforts: list[str]) -> list[str]:
    """조건 접미사 없는 요약형 이름을 요약 reasoning_effort 조건마다 펼친다."""
    out = []
    for n in names:
        if is_stateful(n) and summary_effort_of(n) is None and efforts:
            out.extend(f"{n}[sre={e}]" for e in efforts)
        else:
            out.append(n)
    seen = set()
    return [n for n in out if not (n in seen or seen.add(n))]


def split_compressor_list(arg: str) -> list[str]:
    """--compressors "none,window(2),per_message(rule)" -> 이름 목록 (괄호 안 쉼표는 나누지 않음)."""
    return split_top_level(arg, sep=",")


__all__ = ["BUDGET_FAMILIES", "FrozenSummary", "QuerySelect", "RollingSummary", "STATEFUL_FAMILIES", "Summarizer",
           "WindowBudget", "budget_of", "expand_budgets", "expand_summary_efforts", "family_of", "is_stateful",
           "label_of", "select_history", "split_sre", "summary_effort_of",
           "CompressorFallbackError", "MissingDependencyError", "HistoryChain", "HistoryCompressor", "HistoryResult", "NoHistoryCompression", "PerMessage",
           "Window", "get_history_compressor", "split_compressor_list", "split_top_level", "split_turns"]
