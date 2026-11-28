"""
예산형 history 압축기: window_budget(B), query_select(B)

기록 토큰 = system 과 현재 턴을 뺀 과거 메시지 본문을 token_counter 로 센 합 (replay 의 history_tokens_compressed 와 같은 단위).
최근 keep_recent 턴은 예산을 넘어도 원문으로 남기고 info.overflow=True 로 표시한다 (잘라 내지 않는다).

예산은 절대 토큰(window_budget(2000)) 또는 비율(window_budget(r=0.5)) 로 준다.
비율 예산 = 그 턴의 **원본** 과거 기록 토큰 × r (반올림, 최소 1). 체인 안에서도 앞 단계가 압축하기 전의 원본을 기준으로 한다
(HistoryCompressor.compress_history 가 원본 과거 기록을 RAW_PAST 에 넣어 둔다).
"""

from __future__ import annotations

import re

from multiturn.history_compressors.base import RAW_PAST, HistoryCompressor, HistoryResult, split_turns
from multiturn.prompt import DOC_BLOCK_RE

_QUESTION_RE = re.compile(r"Question: (.*?)(?:\n\nAnswer format:|\Z)", re.S)
_DOC_HEADER_RE = re.compile(r"^## Document: (.+)$", re.M)


def default_token_counter(text: str) -> int:
    from llm import count_tokens
    return count_tokens(text)


def history_tokens(messages: list[dict], token_counter) -> int:
    return sum(token_counter(m["content"]) for m in messages if m["role"] != "system")


def question_of(user_content: str) -> str:
    m = _QUESTION_RE.search(user_content)
    return m.group(1).strip() if m else user_content.strip()


def budget_info(messages, budget, token_counter, **extra) -> dict:
    n = history_tokens(messages, token_counter)
    return {"history_budget": budget, "history_tokens": n, "overflow": n > budget, **extra}


class BudgetCompressor(HistoryCompressor):
    family = "budget"

    def __init__(self, budget: int | None = None, keep_recent: int = 1, token_counter=None, ratio: float | None = None):
        if (budget is None) == (ratio is None):
            raise ValueError("예산은 budget(토큰) 과 ratio(비율) 중 하나만 준다")
        if budget is not None and budget <= 0:
            raise ValueError("예산은 양의 정수")
        if ratio is not None and not 0 < ratio <= 1:
            raise ValueError("비율 예산 r 은 0 초과 1 이하")
        if keep_recent < 0:
            raise ValueError("keep_recent 는 0 이상")
        self.budget = budget
        self.ratio = ratio
        self.keep_recent = keep_recent
        self.count = token_counter or default_token_counter
        self.name = f"{self.family}({budget})" if ratio is None else f"{self.family}(r={ratio:g})"

    def effective_budget(self, past: list[dict]) -> int:
        """이 턴에 쓸 예산 (토큰). 비율 예산이면 원본 과거 기록(RAW_PAST, 없으면 past) 토큰 × r."""
        if self.ratio is None:
            return self.budget
        raw = RAW_PAST.get(None)
        return max(1, round(self.ratio * history_tokens(raw if raw is not None else past, self.count)))

    def config(self):
        return {"name": self.name, "family": self.family, "budget": self.budget, "ratio": self.ratio,
                "keep_recent": self.keep_recent}


def _ratio_extra(comp, budget) -> dict:
    return {"history_budget_ratio": comp.ratio} if comp.ratio is not None else {}


class WindowBudget(BudgetCompressor):
    """최근 턴부터 턴 단위로 예산이 찰 때까지 원문으로 남긴다. 최근 keep_recent 턴은 넘쳐도 남긴다."""
    family = "window_budget"

    def compress_past(self, past, current_user, budget_tokens, state):
        budget = self.effective_budget(past)
        turns = split_turns(past)
        kept: list[list[dict]] = []
        used = 0
        for i, t in enumerate(reversed(turns)):
            n = history_tokens(t, self.count)
            if i < self.keep_recent or used + n <= budget:
                kept.insert(0, t)
                used += n
            else:
                break
        msgs = [m for t in kept for m in t]
        return HistoryResult(messages=msgs, info=budget_info(msgs, budget, self.count, turns_total=len(turns),
                                                             turns_kept=len(kept), **_ratio_extra(self, budget)))


# ---------------- query_select ----------------

def _units_of_turn(turn_idx: int, turn: list[dict]) -> list[dict]:
    """한 과거 턴의 선택 단위: 문서 블록의 문장·코드 구간, 그리고 질문·답변 쌍."""
    from compressors.question_preserve import units as qp_units

    out = []
    user = next((m["content"] for m in turn if m["role"] == "user"), "")
    answer = "\n".join(m["content"] for m in turn if m["role"] == "assistant")
    order = 0
    for block in DOC_BLOCK_RE.finditer(user):
        doc = block.group(2)
        headers = [(h.start(), h.group(1).strip()) for h in _DOC_HEADER_RE.finditer(doc)]
        for a, z, kind in qp_units(doc):
            if kind == "header":
                continue
            page = next((name for pos, name in reversed(headers) if pos <= a), "")
            text = doc[a:z].strip()
            if text:
                out.append({"turn": turn_idx, "order": order, "kind": kind, "label": f"document {page}".strip(),
                            "text": text})
                order += 1
    q = question_of(user)
    out.append({"turn": turn_idx, "order": order, "kind": "qa", "label": "Q/A",
                "text": f"[turn {turn_idx} · Q] {q}\n[turn {turn_idx} · A] {answer.strip()}"})
    return out


def render_selected(selected: list[dict]) -> str:
    lines = ["<selected_history>"]
    last = None
    for u in sorted(selected, key=lambda u: (u["turn"], u["order"])):
        if u["kind"] == "qa":
            lines.append(u["text"])
            last = None
            continue
        head = (u["turn"], u["label"])
        if head != last:
            lines.append(f"[turn {u['turn']} · {u['label']}]")
            last = head
        lines.append(u["text"])
    lines.append("</selected_history>")
    return "\n".join(lines)


def select_history(question: str, past: list[dict], budget: int, token_counter, keep_recent: int = 1) -> tuple[list[dict], dict]:
    """현재 질문과 과거 기록·예산·토큰 카운터만 받아 기록을 고른다 (정답·key_facts·evidence·turn_type·depends_on 을 받지 않음).

    최근 keep_recent 턴은 원문으로 남긴다. 나머지 턴에서 BM25 점수(compressors.question_preserve.bm25) 가 0 보다 큰 조각을
    점수 순으로 예산까지 고르고, 원래 순서대로 <selected_history> 메시지 하나에 넣는다 (어느 턴에서 왔는지 표시)."""
    from compressors.question_preserve import bm25

    turns = split_turns(past)
    recent = turns[len(turns) - keep_recent:] if keep_recent else []
    older = turns[:len(turns) - len(recent)]
    recent_msgs = [m for t in recent for m in t]
    remaining = budget - history_tokens(recent_msgs, token_counter)
    cands = [u for i, t in enumerate(older) for u in _units_of_turn(i, t)]
    info = {"candidates": len(cands), "selected": 0}
    if not cands or remaining <= 0:
        return recent_msgs, info
    text, spans, pos = "", [], 0
    for u in cands:
        spans.append((pos, pos + len(u["text"]), u["kind"]))
        text += u["text"] + "\n"
        pos = len(text)
    scores = bm25(question, text, spans)
    ranked = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: (-scores[i], i))
    chosen: list[dict] = []
    for i in ranked:
        trial = chosen + [cands[i]]
        if token_counter(render_selected(trial)) <= remaining:
            chosen = trial
    info["selected"] = len(chosen)
    if not chosen:
        return recent_msgs, info
    return [{"role": "user", "content": render_selected(chosen)}] + recent_msgs, info


class QuerySelect(BudgetCompressor):
    family = "query_select"

    def compress_past(self, past, current_user, budget_tokens, state):
        budget = self.effective_budget(past)
        msgs, sel = select_history(question_of(current_user), past, budget, self.count, self.keep_recent)
        return HistoryResult(messages=msgs, info=budget_info(msgs, budget, self.count, **sel, **_ratio_extra(self, budget)))
