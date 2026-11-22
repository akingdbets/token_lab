"""none, window(n), per_message(<싱글턴 압축기>)."""

from __future__ import annotations

import re

from multiturn.history_compressors.base import HistoryCompressor, HistoryResult, split_turns
from multiturn.prompt import DOC_BLOCK_RE

_QUESTION_RE = re.compile(r"Question: (.*?)(?:\n\nAnswer format:|\Z)", re.S)


class NoHistoryCompression(HistoryCompressor):
    name = "none"

    def compress_past(self, past, current_user, budget_tokens, state):
        return HistoryResult(messages=past)


class Window(HistoryCompressor):
    """최근 n 턴(user + assistant)만 원문으로 남기고 나머지는 지운다. n=0 이면 기록을 모두 지운다."""

    def __init__(self, n: int):
        if n < 0:
            raise ValueError("window(n) 의 n 은 0 이상")
        self.n = n
        self.name = f"window({n})"

    def compress_past(self, past, current_user, budget_tokens, state):
        turns = split_turns(past)
        kept = turns[-self.n:] if self.n else []
        return HistoryResult(messages=[m for t in kept for m in t],
                             info={"turns_total": len(turns), "turns_kept": len(kept)})

    def config(self):
        return {"name": self.name, "n": self.n}


class PerMessage(HistoryCompressor):
    """과거 user 메시지의 <documentation> 블록에만 싱글턴 압축기(compressors/)를 적용한다.
    질문 줄·형식 줄과 assistant 답변은 그대로 둔다. 기존 압축기 코드는 건드리지 않고 PromptParts 로 감싸 부른다.
    문맥(context)만 압축하는 압축기만 받는다 (targets 가 context 뿐)."""

    def __init__(self, single_name: str):
        from compressors import get_compressor
        self.single = get_compressor(single_name)
        if tuple(self.single.targets) != ("context",):
            raise ValueError(f"per_message 는 context 만 압축하는 압축기만 받습니다: {single_name} targets={self.single.targets}")
        self.single_name = single_name
        self.name = f"per_message({single_name})"

    def compress_past(self, past, current_user, budget_tokens, state):
        from compressors import PromptParts

        out, pt, ct, n_docs = [], 0, 0, 0
        statuses: dict[str, int] = {}
        for m in past:
            m = dict(m)
            if m["role"] == "user":
                mq = _QUESTION_RE.search(m["content"])
                question = mq.group(1).strip() if mq else ""

                def repl(match):
                    nonlocal pt, ct, n_docs
                    r = self.single.compress(PromptParts(system="", context=match.group(2), question=question))
                    pt += r.llm_prompt_tokens
                    ct += r.llm_completion_tokens
                    n_docs += 1
                    st = (r.info or {}).get("status")
                    if st:                    # llmlingua2 는 실패하면 원문을 그대로 돌려주고 status 에 fallback_* 를 남긴다
                        statuses[st] = statuses.get(st, 0) + 1
                    return match.group(1) + r.context + match.group(3)

                m["content"] = DOC_BLOCK_RE.sub(repl, m["content"])
            out.append(m)
        return HistoryResult(messages=out, llm_prompt_tokens=pt, llm_completion_tokens=ct,
                             info={"doc_blocks_compressed": n_docs, "single_status": statuses})

    def config(self):
        cfg = self.single.config() if hasattr(self.single, "config") else {}
        return {"name": self.name, "single": self.single_name, "single_config": cfg}
