"""
요약형 history 압축기 (상태가 쌓인다): rolling_summary(B), frozen_summary(B)

상태는 replay 가 (시나리오, 압축기, 예산, sample) 체인마다 initial_state(sample_idx) 로 만들고,
턴 0 부터 차례로 compress_history(..., state=이전 HistoryResult.state) 로 넘긴다.

rolling_summary(B)
    기록이 예산 B 를 넘으면 최근 keep_recent 턴을 뺀 미요약 턴 전부를 (기존 요약이 있으면 그것과 합쳐) 요약 하나로 다시 쓴다.
    [system] [<conversation_summary turns="0-k">] [최근 원문 턴...] [현재 턴]
frozen_summary(B)
    넘치면 새로 넘친 턴만 새 요약 블록으로 만들어 기존 블록 뒤에 붙인다. 기존 블록은 절대 다시 쓰지 않는다
    (블록마다 user 메시지 하나라서 앞쪽 메시지가 글자 그대로 남는다 -> 프롬프트 캐시 접두부 유지).
    블록이 2개 이상 쌓여 예산을 넘을 때만 전체 블록을 한 번 다시 요약한다 (재압축, info.recompressed).
    [system] [블록 1] [블록 2] ... [최근 원문 턴...] [현재 턴]

요약 실패 (빈 요약 또는 finish_reason=length)
    실패한 응답은 응답 캐시에 저장하지 않고, 같은 설정으로 최대 2번 다시 시도한다 (총 3번).
    그래도 실패하면 HistoryResult.info.summary_failed=True 로 돌려준다 (messages 는 비어 있음).
    원문을 남기는 식의 대체는 하지 않는다. replay 가 그 체인을 그 턴부터 summary_failed 로 표시하고 남은 턴을 건너뛴다.

요약기는 접을 과거 턴과 이전 요약만 받는다. 현재 턴 메시지·정답·key_facts·key_entities 를 받는 인자가 없다.
요약에 쓴 LLM 토큰(실패한 시도 포함, 추론 포함)은 HistoryResult.llm_prompt_tokens / llm_completion_tokens 에 담고,
호출별 LLMResult 는 info["_llm_results"] 로 넘긴다 (replay 가 비용 계산 뒤 지운다. JSON 으로 저장하지 않음).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from multiturn.history_compressors.base import HistoryCompressor, HistoryResult, split_turns
from multiturn.history_compressors.budget import BudgetCompressor, budget_info, history_tokens

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
MIN_TARGET_TOKENS = 200
SUMMARY_HEADER = "Summary of earlier turns (documentation excerpts and answers), written by a summarizer:"


@dataclass
class SummaryPrompt:
    version: str
    sha256: str
    system: str
    previous_block: str
    user: str


def load_summary_prompt(version: str = "v1") -> SummaryPrompt:
    path = PROMPTS_DIR / f"mt_summary_{version}.md"
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    sections, cur = {}, None
    for line in text.split("\n"):
        m = re.match(r"## (\w+)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
        elif cur:
            sections[cur].append(line)
    sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    missing = {"system", "previous_block", "user"} - sections.keys()
    if missing:
        raise ValueError(f"{path}: 섹션이 없습니다: {sorted(missing)}")
    return SummaryPrompt(version, hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                         sections["system"], sections["previous_block"], sections["user"])


def format_turns(turns: list[tuple[int, list[dict]]]) -> str:
    parts = []
    for idx, msgs in turns:
        body = "\n".join(f"[{m['role']}]\n{m['content']}" for m in msgs)
        parts.append(f"### Turn {idx}\n{body}")
    return "\n\n".join(parts)


def summary_message(text: str, first: int, last: int) -> dict:
    return {"role": "user",
            "content": f'<conversation_summary turns="{first}-{last}">\n{SUMMARY_HEADER}\n{text.strip()}\n</conversation_summary>'}


def summary_ok(res) -> bool:
    return bool((res.text or "").strip()) and res.finish_reason != "length"


@dataclass
class SummaryOutcome:
    text: str | None
    results: list = field(default_factory=list)     # 시도마다 LLMResult
    cache_hits: list = field(default_factory=list)
    failed: bool = False
    reason: str | None = None

    @property
    def prompt_tokens(self):
        return sum(r.prompt_tokens for r in self.results)

    @property
    def completion_tokens(self):
        return sum(r.completion_tokens for r in self.results)


class Summarizer:
    """요약 LLM 호출. cached 는 multiturn.response_cache.CachedLLM (요약 모델을 감쌈)."""

    def __init__(self, cached, prompt: SummaryPrompt | None = None, max_attempts: int = 3):
        self.cached = cached
        self.prompt = prompt or load_summary_prompt("v1")
        self.max_attempts = max_attempts

    def build_messages(self, turns: list[tuple[int, list[dict]]], previous: str | None, target_tokens: int) -> list[dict]:
        prev = self.prompt.previous_block.format(summary=previous.strip()) + "\n\n" if previous else ""
        user = self.prompt.user.format(previous=prev, turns=format_turns(turns) or "(none)",
                                       target_tokens=max(int(target_tokens), MIN_TARGET_TOKENS))
        return [{"role": "system", "content": self.prompt.system}, {"role": "user", "content": user}]

    def summarize(self, turns: list[tuple[int, list[dict]]], previous: str | None, target_tokens: int,
                  sample_idx: int) -> SummaryOutcome:
        messages = self.build_messages(turns, previous, target_tokens)
        out = SummaryOutcome(text=None)
        for _ in range(self.max_attempts):
            res, hit = self.cached.chat(messages, sample_idx=sample_idx, store_if=summary_ok)
            out.results.append(res)
            out.cache_hits.append(hit)
            if summary_ok(res):
                out.text = res.text.strip()
                return out
            out.reason = "length" if res.finish_reason == "length" else "empty"
        out.failed = True
        return out

    def config(self) -> dict:
        llm = self.cached.llm
        return {"prompt": [self.prompt.version, self.prompt.sha256], "max_attempts": self.max_attempts,
                "sampling": llm.sampling_info(), "backend": llm.backend, "base_url": llm.base_url}


class SummaryCompressor(BudgetCompressor):
    stateful = True

    def __init__(self, budget: int | None, summarizer: Summarizer | None, keep_recent: int = 1, token_counter=None,
                 ratio: float | None = None):
        super().__init__(budget, keep_recent, token_counter, ratio=ratio)
        if summarizer is None:
            raise ValueError(f"{self.name} 는 요약기가 필요합니다 (--summary-model, --summary-reasoning-effort, "
                             "--summary-max-tokens)")
        self.summarizer = summarizer

    def initial_state(self, sample_idx: int) -> dict:
        return {"sample_idx": sample_idx, "through": 0, "blocks": [], "recompress_turns": [], "turn": 0}

    def config(self):
        return {**super().config(), "summarizer": self.summarizer.config()}

    # 공통
    def _fail(self, outcome, info):
        return HistoryResult(messages=[], llm_prompt_tokens=outcome.prompt_tokens,
                             llm_completion_tokens=outcome.completion_tokens, state=None,
                             info={**info, "summary_failed": True, "summary_fail_reason": outcome.reason,
                                   "summary_attempts": len(outcome.results), "_llm_results": outcome.results})

    def _call(self, state, calls, turns, previous, target):
        o = self.summarizer.summarize(turns, previous, target, state["sample_idx"])
        calls.append(o)
        return o

    def _finish(self, state, msgs, calls, budget=None, **extra):
        budget = self.budget if budget is None else budget
        if self.ratio is not None:
            extra["history_budget_ratio"] = self.ratio
        info = budget_info(msgs, budget, self.count, summary_calls=sum(len(c.results) for c in calls),
                           summary_cache_hits=sum(sum(c.cache_hits) for c in calls),
                           summary_blocks=len(state["blocks"]), summarized_through=state["through"], **extra)
        info["_llm_results"] = [r for c in calls for r in c.results]
        return HistoryResult(messages=msgs, llm_prompt_tokens=sum(c.prompt_tokens for c in calls),
                             llm_completion_tokens=sum(c.completion_tokens for c in calls), state=state, info=info)

    def _block_msgs(self, state):
        return [summary_message(b["text"], b["first"], b["last"]) for b in state["blocks"]]


class RollingSummary(SummaryCompressor):
    family = "rolling_summary"

    def compress_past(self, past, current_user, budget_tokens, state):
        budget = self.effective_budget(past)
        state = dict(state or self.initial_state(0))
        state["blocks"] = list(state["blocks"])
        turns = split_turns(past)
        raw = turns[state["through"]:]
        calls = []
        msgs = self._block_msgs(state) + [m for t in raw for m in t]
        if history_tokens(msgs, self.count) > budget and len(raw) > self.keep_recent:
            fold_n = len(raw) - self.keep_recent
            fold = [(state["through"] + i, t) for i, t in enumerate(raw[:fold_n])]
            recent = raw[fold_n:]
            previous = state["blocks"][0]["text"] if state["blocks"] else None
            target = budget - history_tokens([m for t in recent for m in t], self.count)
            o = self._call(state, calls, fold, previous, target)
            if o.failed:
                return self._fail(o, budget_info([], budget, self.count))
            state["through"] += fold_n
            state["blocks"] = [{"text": o.text, "first": 0, "last": state["through"] - 1}]
            msgs = self._block_msgs(state) + [m for t in recent for m in t]
        return self._finish(state, msgs, calls, budget)


class FrozenSummary(SummaryCompressor):
    family = "frozen_summary"

    def compress_past(self, past, current_user, budget_tokens, state):
        budget = self.effective_budget(past)
        state = dict(state or self.initial_state(0))
        state["blocks"] = list(state["blocks"])
        state["recompress_turns"] = list(state["recompress_turns"])
        turns = split_turns(past)
        k = len(turns)                      # 현재 턴 번호 (과거 턴 수)
        raw = turns[state["through"]:]
        calls = []
        recompressed = False
        msgs = self._block_msgs(state) + [m for t in raw for m in t]
        if history_tokens(msgs, self.count) > budget and len(raw) > self.keep_recent:
            fold_n = len(raw) - self.keep_recent
            fold = [(state["through"] + i, t) for i, t in enumerate(raw[:fold_n])]
            recent = raw[fold_n:]
            recent_msgs = [m for t in recent for m in t]
            target = (budget - history_tokens(self._block_msgs(state), self.count)
                      - history_tokens(recent_msgs, self.count))
            o = self._call(state, calls, fold, None, target)          # 새 블록: 이전 요약은 넣지 않는다
            if o.failed:
                return self._fail(o, budget_info([], budget, self.count))
            first = state["through"]
            state["through"] += fold_n
            state["blocks"].append({"text": o.text, "first": first, "last": state["through"] - 1})
            msgs = self._block_msgs(state) + recent_msgs
            if history_tokens(msgs, self.count) > budget and len(state["blocks"]) >= 2:
                previous = "\n\n".join(m["content"] for m in self._block_msgs(state))
                o = self._call(state, calls, [], previous, budget - history_tokens(recent_msgs, self.count))
                if o.failed:
                    return self._fail(o, budget_info([], budget, self.count, recompressed=True))
                state["blocks"] = [{"text": o.text, "first": 0, "last": state["through"] - 1}]
                state["recompress_turns"].append(k)
                recompressed = True
                msgs = self._block_msgs(state) + recent_msgs
        return self._finish(state, msgs, calls, budget, recompressed=recompressed,
                            recompress_turns=list(state["recompress_turns"]))
