"""대화 기록 압축기 공통 인터페이스.

    compress_history(history, current_user, budget_tokens=None, state=None) -> HistoryResult

    history       지금까지의 대화 기록 [system?, user, assistant, user, assistant, ...] (최종 답변만, 추론 없음)
    current_user  현재 턴 사용자 메시지 (압축하지 않는다)
    budget_tokens 기록 토큰 예산 (예산을 쓰는 압축기용. 지금 압축기들은 쓰지 않는다)
    state         상태를 가진 압축기(재귀 요약, 고정 요약 등)용. 이전 호출의 HistoryResult.state 를 넘긴다

    HistoryResult.messages = [system] + 압축된 과거 기록 + [current_user]   (바로 보낼 수 있는 형태)

규칙
    - system 메시지와 현재 턴 사용자 메시지는 압축하지 않는다. 압축 대상은 과거 기록(user/assistant)뿐이다.
      기본 클래스가 이를 나눠 compress_past 에 과거 기록만 넘기고, 돌려받은 뒤 다시 붙인다.
    - 압축에 LLM 을 쓰면 그 토큰을 HistoryResult.llm_prompt_tokens / llm_completion_tokens 에 담는다 (순 절감률 계산용).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

# 이 턴의 원본 과거 기록 (system·현재 턴 제외, 압축 전). 비율 예산(budget.py) 이 읽는다.
# 바깥 compress_history 호출이 넣고, 체인의 단계들은 compress_past 만 부르므로 원본이 유지된다.
RAW_PAST: contextvars.ContextVar = contextvars.ContextVar("raw_past", default=None)


@dataclass
class HistoryResult:
    messages: list[dict]
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    state: object = None
    info: dict = field(default_factory=dict)


def split_turns(past: list[dict]) -> list[list[dict]]:
    """과거 기록을 턴 단위로 묶는다. user 메시지가 새 턴을 연다."""
    turns: list[list[dict]] = []
    for m in past:
        if m["role"] == "user" or not turns:
            turns.append([m])
        else:
            turns[-1].append(m)
    return turns


class HistoryCompressor:
    name: str = "base"

    def compress_history(self, history: list[dict], current_user: str, budget_tokens: int | None = None,
                         state=None) -> HistoryResult:
        if any(m["role"] == "system" for m in history[1:]):
            raise ValueError("system 메시지는 기록 맨 앞에만 둘 수 있습니다")
        system = history[:1] if history and history[0]["role"] == "system" else []
        past = [dict(m) for m in history[len(system):]]
        token = RAW_PAST.set([dict(m) for m in past])
        try:
            res = self.compress_past(past, current_user, budget_tokens, state)
        finally:
            RAW_PAST.reset(token)
        res.messages = [dict(m) for m in system] + res.messages + [{"role": "user", "content": current_user}]
        return res

    def compress_past(self, past: list[dict], current_user: str, budget_tokens: int | None,
                      state) -> HistoryResult:
        raise NotImplementedError

    def config(self) -> dict:
        return {"name": self.name}


class HistoryChain(HistoryCompressor):
    """"window(2)>per_message(rule)" 처럼 순서대로 적용. 앞 단계 출력이 다음 단계 입력, LLM 토큰은 합산.
    state 는 단계별 리스트.

    상태형(요약형) 단계는 마지막 단계일 때만 받는다: "on_arrival(rule)>frozen_summary(8000)".
    이때 체인 전체가 상태형이 되고(initial_state), 요약 단계의 info(summary_calls, recompressed, overflow,
    summary_failed, _llm_results ...)를 replay 가 읽을 수 있게 최상위 info 로 올린다.
    on_arrival 처럼 현재 턴 문서를 압축하는 단계가 있으면 현재 턴 메시지에도 그 단계를 적용한다."""

    def __init__(self, stages: list[HistoryCompressor]):
        self.stages = stages
        self.name = ">".join(s.name for s in stages)
        flags = [getattr(s, "stateful", False) for s in stages]
        if any(flags[:-1]):
            raise ValueError(f"상태형 압축기는 체인의 마지막 단계에만 둘 수 있습니다: {self.name}")
        self.stateful = flags[-1]
        self.compresses_current_docs = any(getattr(s, "compresses_current_docs", False) for s in stages)

    def initial_state(self, sample_idx: int) -> list:
        return [s.initial_state(sample_idx) if getattr(s, "stateful", False) else None for s in self.stages]

    def compress_past(self, past, current_user, budget_tokens, state):
        states = list(state) if state else [None] * len(self.stages)
        pt = ct = 0
        info, new_states = {}, []
        for i, (stage, st) in enumerate(zip(self.stages, states)):
            r = stage.compress_past(past, current_user, budget_tokens, st)
            pt += r.llm_prompt_tokens
            ct += r.llm_completion_tokens
            stage_info = dict(r.info)
            if self.stateful and getattr(stage, "stateful", False):
                info.update({k: v for k, v in stage_info.items() if k not in info})   # 요약 단계 info 를 최상위로
                stage_info.pop("_llm_results", None)                                   # 객체는 최상위에만 (JSON 저장 안 함)
            info[f"{i + 1}:{stage.name}"] = stage_info
            if r.info.get("summary_failed"):
                return HistoryResult(messages=[], llm_prompt_tokens=pt, llm_completion_tokens=ct, state=None, info=info)
            past = r.messages
            new_states.append(r.state)
        return HistoryResult(messages=past, llm_prompt_tokens=pt, llm_completion_tokens=ct,
                             state=new_states, info=info)

    def compress_history(self, history, current_user, budget_tokens=None, state=None):
        res = super().compress_history(history, current_user, budget_tokens, state)
        if self.compresses_current_docs and not res.info.get("summary_failed"):
            content = current_user
            for st in self.stages:
                if getattr(st, "compresses_current_docs", False):
                    c = st._new_counters()
                    content = st._compress_user(content, c)
                    res.llm_prompt_tokens += c["pt"]
                    res.llm_completion_tokens += c["ct"]
                    res.info[f"current_doc_blocks_compressed:{st.name}"] = c["docs"]
            res.messages[-1] = {"role": "user", "content": content}
        return res

    def config(self) -> dict:
        return {"name": self.name, "stages": [s.config() for s in self.stages]}
