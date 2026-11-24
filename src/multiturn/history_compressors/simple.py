"""none, window(n), per_message(<싱글턴 압축기>), on_arrival(<싱글턴 압축기>)."""

from __future__ import annotations

import importlib
import re
import threading

from multiturn.history_compressors.base import HistoryCompressor, HistoryResult, split_turns
from multiturn.prompt import DOC_BLOCK_RE

# llmlingua 패키지가 필요한 싱글턴 압축기 모듈. 이 압축기들은 llmlingua 가 없거나 추론이 실패하면
# 예외를 삼키고 원문을 그대로 돌려준다 (compressors/llmlingua2.py fallback_on_error=True, status="fallback_error").
# 멀티턴 실험에서는 그런 조용한 대체를 허용하지 않는다: 시작 시점에 import 를 확인하고, 실행 중 fallback_error 가 나오면 멈춘다.
LLMLINGUA_MODULES = ("compressors.llmlingua2", "compressors.repair", "compressors.question_preserve")


class MissingDependencyError(RuntimeError):
    """압축기에 필요한 패키지가 없다. 원문으로 대체하지 않고 멈춘다."""


class CompressorFallbackError(RuntimeError):
    """싱글턴 압축기가 오류를 삼키고 원문을 돌려줬다 (status=fallback_error). 압축하지 않은 결과를 압축 결과로 쓰지 않는다."""


def _stages(single) -> list:
    return list(getattr(single, "stages", None) or [single])


def needs_llmlingua(single) -> bool:
    return any(type(st).__module__ in LLMLINGUA_MODULES for st in _stages(single))


def require_llmlingua(name: str) -> None:
    try:
        importlib.import_module("llmlingua")
    except Exception as e:      # 패키지가 없거나, torch 등 의존성이 없어 import 가 실패
        raise MissingDependencyError(
            f"{name} 는 llmlingua 가 필요합니다 ({type(e).__name__}: {e}). "
            "pip install -r requirements.txt (llmlingua==0.2.2) 후 다시 실행하세요. "
            "원문으로 대체해서 돌리지 않습니다.") from e

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
        self.requires_llmlingua = needs_llmlingua(self.single)
        if self.requires_llmlingua:
            require_llmlingua(self.name)     # 시작 시점(압축기 생성)에 멈춘다

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
                    for st in _statuses(r.info):
                        statuses[st] = statuses.get(st, 0) + 1
                        if st == "fallback_error":
                            raise CompressorFallbackError(
                                f"{self.name}: 싱글턴 압축기가 오류로 원문을 돌려줬습니다 "
                                f"({_error_detail(r.info)}). 원문을 압축 결과로 쓰지 않고 멈춥니다.")
                    return match.group(1) + r.context + match.group(3)

                m["content"] = DOC_BLOCK_RE.sub(repl, m["content"])
            out.append(m)
        return HistoryResult(messages=out, llm_prompt_tokens=pt, llm_completion_tokens=ct,
                             info={"doc_blocks_compressed": n_docs, "single_status": statuses})

    def config(self):
        cfg = self.single.config() if hasattr(self.single, "config") else {}
        return {"name": self.name, "single": self.single_name, "single_config": cfg}


class OnArrival(PerMessage):
    """문서가 첨부된 그 턴에 <documentation> 블록을 싱글턴 압축기로 압축해서 보내고, 이후 턴에서도 그 압축본을 그대로 둔다.
    per_message 와 달리 **현재 턴 사용자 메시지의 문서도 압축한다** (질문 줄·형식 줄과 assistant 답변은 압축하지 않는다).

    한 번 압축한 문서는 다시 바꾸지 않는다: (문서 원문, 그 문서가 온 턴의 질문) 으로 결과를 기억해 두고 재사용한다.
    replay 는 턴 k 의 기록을 기준 궤적의 원문에서 다시 만들기 때문에, 과거 문서도 "도착했을 때와 같은 입력" 으로
    압축된다 (각 user 메시지의 자기 질문을 쓴다). 그래서 연속 턴에서 이전 요청 + 이전 답변이 다음 요청의 접두부와 같다.
    """

    compresses_current_docs = True

    def __init__(self, single_name: str):
        super().__init__(single_name)
        self.name = f"on_arrival({single_name})"
        self._arrived: dict[tuple[str, str], tuple[str, dict]] = {}   # (문서 원문, 질문) -> (압축본, info)
        self._arrived_lock = threading.Lock()

    def _compress_user(self, content: str, counters: dict) -> str:
        from compressors import PromptParts

        mq = _QUESTION_RE.search(content)
        question = mq.group(1).strip() if mq else ""

        def repl(match):
            key = (match.group(2), question)
            with self._arrived_lock:
                hit = self._arrived.get(key)
            if hit is None:
                r = self.single.compress(PromptParts(system="", context=match.group(2), question=question))
                for st in _statuses(r.info):
                    if st == "fallback_error":
                        raise CompressorFallbackError(
                            f"{self.name}: 싱글턴 압축기가 오류로 원문을 돌려줬습니다 "
                            f"({_error_detail(r.info)}). 원문을 압축 결과로 쓰지 않고 멈춥니다.")
                counters["pt"] += r.llm_prompt_tokens
                counters["ct"] += r.llm_completion_tokens
                counters["new"] += 1
                hit = (r.context, {"statuses": _statuses(r.info)})
                with self._arrived_lock:
                    hit = self._arrived.setdefault(key, hit)   # 동시에 압축했으면 먼저 기록된 것을 쓴다
            else:
                counters["reused"] += 1
            for st in hit[1]["statuses"]:
                counters["statuses"][st] = counters["statuses"].get(st, 0) + 1
            counters["docs"] += 1
            return match.group(1) + hit[0] + match.group(3)

        return DOC_BLOCK_RE.sub(repl, content)

    def _new_counters(self) -> dict:
        return {"pt": 0, "ct": 0, "docs": 0, "new": 0, "reused": 0, "statuses": {}}

    def compress_past(self, past, current_user, budget_tokens, state):
        c = self._new_counters()
        out = [dict(m, content=self._compress_user(m["content"], c)) if m["role"] == "user" else dict(m)
               for m in past]
        return HistoryResult(messages=out, llm_prompt_tokens=c["pt"], llm_completion_tokens=c["ct"],
                             info={"doc_blocks_compressed": c["docs"], "doc_blocks_new": c["new"],
                                   "doc_blocks_reused": c["reused"], "single_status": c["statuses"]})

    def compress_history(self, history, current_user, budget_tokens=None, state=None):
        res = super().compress_history(history, current_user, budget_tokens, state)
        c = self._new_counters()
        res.messages[-1] = {"role": "user", "content": self._compress_user(current_user, c)}
        res.llm_prompt_tokens += c["pt"]
        res.llm_completion_tokens += c["ct"]
        res.info["current_doc_blocks_compressed"] = c["docs"]
        res.info["current_doc_blocks_new"] = c["new"]
        for st, n in c["statuses"].items():
            res.info["single_status"][st] = res.info["single_status"].get(st, 0) + n
        return res


def _statuses(info) -> list[str]:
    """싱글턴 CompressResult.info 의 status (Chain 이면 단계별 info 안)."""
    if not isinstance(info, dict):
        return []
    out = [info["status"]] if isinstance(info.get("status"), str) else []
    for v in info.values():
        if isinstance(v, dict):
            out.extend(_statuses(v))
    return out


def _error_detail(info) -> str:
    if isinstance(info, dict):
        if info.get("error_type") or info.get("error"):
            return f"{info.get('error_type')}: {info.get('error')}"
        for v in info.values():
            d = _error_detail(v)
            if d:
                return d
    return ""

