"""
대화 기록 압축기 (멀티턴). 인터페이스는 base.py 참고.

이름 문법 (싱글턴 compressors 의 ">" 조합과 같다)
    none
    window(<n>)                   최근 n 턴만 원문 유지
    per_message(<싱글턴 이름>)     과거 user 메시지의 문서 블록에만 싱글턴 압축기 적용 (rule, llmlingua2, rule>llmlingua2 ...)
    a>b                           a 다음 b. 괄호 안의 ">" 는 나누지 않는다: per_message(rule>llmlingua2)

    from multiturn.history_compressors import get_history_compressor
    hc = get_history_compressor("window(2)>per_message(rule)")
    res = hc.compress_history(history, current_user)
"""

from __future__ import annotations

import re

from multiturn.history_compressors.base import HistoryChain, HistoryCompressor, HistoryResult, split_turns
from multiturn.history_compressors.simple import (
    CompressorFallbackError, MissingDependencyError, NoHistoryCompression, PerMessage, Window,
)

_STAGE_RE = re.compile(r"^([a-z_]+)(?:\((.*)\))?$")


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


def _stage(spec: str) -> HistoryCompressor:
    m = _STAGE_RE.match(spec)
    if not m:
        raise KeyError(f"알 수 없는 history 압축기: {spec}")
    name, arg = m.group(1), m.group(2)
    if name == "none" and arg is None:
        return NoHistoryCompression()
    if name == "window" and arg is not None and arg.strip().isdigit():
        return Window(int(arg))
    if name == "per_message" and arg:
        return PerMessage(arg.strip())
    raise KeyError(f"알 수 없는 history 압축기: {spec} (none | window(n) | per_message(<싱글턴 이름>))")


def get_history_compressor(spec: str) -> HistoryCompressor:
    stages = [_stage(s) for s in split_top_level(spec)]
    return stages[0] if len(stages) == 1 else HistoryChain(stages)


def split_compressor_list(arg: str) -> list[str]:
    """--compressors "none,window(2),per_message(rule)" -> 이름 목록 (괄호 안 쉼표는 나누지 않음)."""
    return split_top_level(arg, sep=",")


__all__ = ["CompressorFallbackError", "MissingDependencyError", "HistoryChain", "HistoryCompressor", "HistoryResult", "NoHistoryCompression", "PerMessage",
           "Window", "get_history_compressor", "split_compressor_list", "split_top_level", "split_turns"]
