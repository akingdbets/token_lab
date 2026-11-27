"""
대화 기록 압축기 (멀티턴). 인터페이스는 base.py 참고.

이름 문법 (싱글턴 compressors 의 ">" 조합과 같다)
    none
    window(<n>)                   최근 n 턴만 원문 유지
    per_message(<싱글턴 이름>)     과거 user 메시지의 문서 블록에만 싱글턴 압축기 적용 (rule, llmlingua2, rule>llmlingua2 ...)
    on_arrival(<싱글턴 이름>)      문서가 온 턴에 문서 블록을 압축해 보내고 이후에도 그 압축본 유지.
                                  **현재 턴 문서도 압축한다** (다른 압축기는 현재 턴을 건드리지 않는다). 질문·답변은 그대로
    a>b                           a 다음 b. 괄호 안의 ">" 는 나누지 않는다: per_message(rule>llmlingua2)
                                  요약형은 마지막 단계에만: on_arrival(rule)>frozen_summary(8000)[sre=none]

예산형 (기록 토큰 예산 B, budget.py / summary.py). 최근 keep_recent 턴은 넘쳐도 원문으로 남기고 overflow 로 표시
    B 는 절대 토큰(2000) 또는 비율(r=0.5: 그 턴의 원본 과거 기록 토큰의 50%). 예: window_budget(r=0.5)
    window_budget(<B>)            최근 턴부터 예산이 찰 때까지 원문
    query_select(<B>)             현재 질문 BM25 로 과거 조각을 골라 <selected_history> 로
    rolling_summary(<B>)          넘치면 오래된 턴을 요약 하나로 다시 씀 (상태형, summarizer 필요)
    frozen_summary(<B>)           넘치면 새 블록만 덧붙임, 쌓여 넘칠 때만 재압축 (상태형, summarizer 필요)
    replay 의 --history-budget 1000,2000,r=0.5 를 주면 예산 없이 쓴 이름(window_budget 등)을 예산마다 펼친다 (expand_budgets)

문서 블록 대체형 (notes.py). 직전 keep_recent 턴과 현재 턴 문서는 원문
    presummary                    과거 문서 블록의 페이지 본문을 미리 만든 페이지 요약으로 (presummary_store 필요)
    fact_notes                    과거 턴의 문서 블록을 그 턴 끝에 뽑은 사실 메모로 (notes_extractor 필요, 체인 불가)

실험 세트 (expand_sets): "v2" 는 COMPRESSOR_SETS["v2"] 로 펼친다.
    v2 = none, window_budget, query_select, rolling_summary, per_message(rule), per_message(llmlingua2),
         on_arrival(rule), presummary, fact_notes   (예산형은 --history-budget, 요약형은 --summary-reasoning-effort 로 다시 펼침)
    v2 에서 뺀 것 (코드는 그대로): window(n), frozen_summary, on_arrival(llmlingua2)

per_message(llmlingua2) / on_arrival(llmlingua2) 주의
    llmlingua2 는 각 user 메시지의 질문(문서가 들어온 턴의 질문)에 나온 식별자를 보호한다 (compressors/llmlingua2.py
    _question_identifiers). 그래서 이후 턴이 같은 문서의 다른 부분을 물으면 그 부분의 식별자는 보호되지 않아 불리할 수 있다.
    (rule 은 질문을 받기만 하고 어떤 규칙에도 쓰지 않는다.)

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
    CompressorFallbackError, MissingDependencyError, NoHistoryCompression, OnArrival, PerMessage, Window,
)
from multiturn.history_compressors.notes import (
    FactNotes, MissingPresummaryError, NotesExtractor, NotesFailedError, PreSummary, PresummaryStore,
)
from multiturn.history_compressors.summary import FrozenSummary, RollingSummary, Summarizer

BUDGET_FAMILIES = {"window_budget": WindowBudget, "query_select": QuerySelect,
                   "rolling_summary": RollingSummary, "frozen_summary": FrozenSummary}
STATEFUL_FAMILIES = ("rolling_summary", "frozen_summary")
COMPRESSOR_SETS = {
    "v2": ["none", "window_budget", "query_select", "rolling_summary", "per_message(rule)", "per_message(llmlingua2)",
           "on_arrival(rule)", "presummary", "fact_notes"],
}
_RATIO_RE = re.compile(r"^r=(\d*\.?\d+)$")


def parse_budget(arg: str):
    """"2000" -> 2000, "r=0.5" -> 0.5 (float). 그 밖은 KeyError."""
    a = arg.strip()
    if a.isdigit():
        return int(a)
    m = _RATIO_RE.match(a)
    if m:
        return float(m.group(1))
    raise KeyError(f"예산은 <토큰 수> 또는 r=<비율>: {arg}")


def budget_spec(b) -> str:
    """예산 값 -> 이름 안 표기. 2000 -> "2000", 0.5 / "r=0.5" -> "r=0.5"."""
    if isinstance(b, str):
        b = parse_budget(b)
    return str(b) if isinstance(b, int) else f"r={b:g}"


def parse_budget_list(arg: str) -> list:
    """--history-budget "2000,r=0.5" -> [2000, "r=0.5"]."""
    out = []
    for x in arg.split(","):
        if x.strip():
            v = parse_budget(x)
            out.append(v if isinstance(v, int) else budget_spec(v))
    return out

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


def _stage(spec: str, token_counter=None, summarizer=None, keep_recent: int = 1, presummary_store=None,
           notes_extractor=None) -> HistoryCompressor:
    m = _STAGE_RE.match(spec)
    if not m:
        raise KeyError(f"알 수 없는 history 압축기: {spec}")
    name, arg = m.group(1), m.group(2)
    if name in BUDGET_FAMILIES:
        if arg is None:
            raise KeyError(f"{name} 는 예산이 필요합니다: {name}(<토큰 수>), {name}(r=<비율>) 또는 --history-budget")
        b = parse_budget(arg)
        budget, ratio = (b, None) if isinstance(b, int) else (None, b)
        cls = BUDGET_FAMILIES[name]
        if name in STATEFUL_FAMILIES:
            return cls(budget, summarizer, keep_recent=keep_recent, token_counter=token_counter, ratio=ratio)
        return cls(budget, keep_recent=keep_recent, token_counter=token_counter, ratio=ratio)
    if name == "none" and arg is None:
        return NoHistoryCompression()
    if name == "presummary" and arg is None:
        return PreSummary(presummary_store, keep_recent=keep_recent, token_counter=token_counter)
    if name == "fact_notes" and arg is None:
        return FactNotes(notes_extractor, keep_recent=keep_recent)
    if name == "window" and arg is not None and arg.strip().isdigit():
        return Window(int(arg))
    if name == "per_message" and arg:
        return PerMessage(arg.strip())
    if name == "on_arrival" and arg:
        return OnArrival(arg.strip())
    raise KeyError(f"알 수 없는 history 압축기: {spec} "
                   "(none | window(n) | per_message(<싱글턴 이름>) | on_arrival(<싱글턴 이름>) | presummary | fact_notes)")


def get_history_compressor(spec: str, token_counter=None, summarizer=None, keep_recent: int = 1,
                           presummary_store=None, notes_extractor=None) -> HistoryCompressor:
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
    stages = [_stage(s, token_counter, summarizer, keep_recent, presummary_store, notes_extractor)
              for s in split_top_level(base)]
    if len(stages) > 1 and any(getattr(s, "per_sample", False) for s in stages):
        raise ValueError(f"fact_notes 는 체인에 넣지 않습니다: {spec}")
    if len(stages) > 1 and any(getattr(s, "stateful", False) for s in stages[:-1]):
        raise ValueError(f"상태형 압축기는 체인의 마지막 단계에만 둘 수 있습니다: {spec}")
    if effort is not None and not any(getattr(s, "stateful", False) for s in stages):
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


def budget_of(spec: str) -> int | str | None:
    """예산형 이름의 예산: 절대 토큰이면 int, 비율이면 "r=0.5" (문자열), 예산형이 아니면 None."""
    spec = split_sre(spec)[0]
    m = _STAGE_RE.match(spec.strip())
    if m and m.group(1) in BUDGET_FAMILIES and m.group(2):
        try:
            b = parse_budget(m.group(2))
        except KeyError:
            return None
        return b if isinstance(b, int) else budget_spec(b)
    return None


def is_stateful(spec: str) -> bool:
    """요약형이거나, 마지막 단계가 요약형인 체인 (on_arrival(rule)>frozen_summary(8000))."""
    base = split_sre(spec)[0]
    return any(family_of(st) in STATEFUL_FAMILIES for st in split_top_level(base))


def expand_sets(names: list[str]) -> list[str]:
    """실험 세트 이름(v2)을 압축기 이름으로 펼친다. 나머지는 그대로, 중복은 처음 것만."""
    out = []
    for n in names:
        out.extend(COMPRESSOR_SETS.get(n.strip(), [n]))
    seen = set()
    return [n for n in out if not (n in seen or seen.add(n))]


def expand_budgets(names: list[str], budgets: list) -> list[str]:
    """예산 없이 쓴 예산형 이름을 예산마다 펼친다 (2000 또는 "r=0.5"). 예산이 필요한데 budgets 가 비면 오류."""
    out = []
    for n in names:
        if n in BUDGET_FAMILIES:
            if not budgets:
                raise ValueError(f"{n} 는 --history-budget 이 필요합니다")
            out.extend(f"{n}({budget_spec(b)})" for b in budgets)
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


__all__ = ["BUDGET_FAMILIES", "COMPRESSOR_SETS", "FactNotes", "MissingPresummaryError", "NotesExtractor",
           "NotesFailedError", "PreSummary", "PresummaryStore", "budget_spec", "expand_sets", "parse_budget",
           "parse_budget_list", "FrozenSummary", "QuerySelect", "RollingSummary", "STATEFUL_FAMILIES", "Summarizer",
           "WindowBudget", "budget_of", "expand_budgets", "expand_summary_efforts", "family_of", "is_stateful",
           "label_of", "select_history", "split_sre", "summary_effort_of",
           "CompressorFallbackError", "MissingDependencyError", "HistoryChain", "HistoryCompressor", "HistoryResult", "NoHistoryCompression", "PerMessage",
           "Window", "get_history_compressor", "split_compressor_list", "split_top_level", "split_turns"]
