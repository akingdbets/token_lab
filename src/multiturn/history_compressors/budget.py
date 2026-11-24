"""
예산형 history 압축기: window_budget(B), query_select(B)

기록 토큰 = system 과 현재 턴을 뺀 과거 메시지 본문을 token_counter 로 센 합 (replay 의 history_tokens_compressed 와 같은 단위).
최근 keep_recent 턴은 예산을 넘어도 원문으로 남기고 info.overflow=True 로 표시한다 (잘라 내지 않는다).
"""

from __future__ import annotations

import re

from multiturn.history_compressors.base import HistoryCompressor, HistoryResult, split_turns
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

    def __init__(self, budget: int, keep_recent: int = 1, token_counter=None):
        if budget <= 0:
            raise ValueError("예산은 양의 정수")
        if keep_recent < 0:
            raise ValueError("keep_recent 는 0 이상")
        self.budget = budget
        self.keep_recent = keep_recent
        self.count = token_counter or default_token_counter
        self.name = f"{self.family}({budget})"

    def config(self):
        return {"name": self.name, "family": self.family, "budget": self.budget, "keep_recent": self.keep_recent}


class WindowBudget(BudgetCompressor):
    """최근 턴부터 턴 단위로 예산이 찰 때까지 원문으로 남긴다. 최근 keep_recent 턴은 넘쳐도 남긴다."""
    family = "window_budget"

    def compress_past(self, past, current_user, budget_tokens, state):
        turns = split_turns(past)
        kept: list[list[dict]] = []
        used = 0
        for i, t in enumerate(reversed(turns)):
            n = history_tokens(t, self.count)
            if i < self.keep_recent or used + n <= self.budget:
                kept.insert(0, t)
                used += n
            else:
                break
        msgs = [m for t in kept for m in t]
        return HistoryResult(messages=msgs, info=budget_info(msgs, self.budget, self.count, turns_total=len(turns),
                                                             turns_kept=len(kept)))


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
        msgs, sel = select_history(question_of(current_user), past, self.budget, self.count, self.keep_recent)
        return HistoryResult(messages=msgs, info=budget_info(msgs, self.budget, self.count, **sel))
