"""근거 줄만 지우기 (진단용).

문항의 근거 인용문(evidence quote)이 들어 있는 줄만 문맥에서 지우고 나머지는 그대로 둔다.
"정답 근거는 빠지고 주제 문맥은 남은" 상태를 만들어, 모델이 NOT FOUND 대신 기억으로 답을 채우는지 본다.

줄 찾기 (공백은 하나로 줄여 비교)
    한 줄 인용문      그 인용문을 포함하는 문맥 줄
    여러 줄 인용문    인용문 줄 순서대로 이어지는 문맥 구간 (빈 줄은 건너뜀). 못 찾으면 줄 단위로 찾는다
    줄 단위로 찾을 때는 너무 짧은 줄(코드 펜스, `app = FastAPI()` 등 흔한 줄)이 다른 곳에서 지워지지 않게
    MIN_LINE_CHARS 이상인 줄만 본다
info: dropped_lines, dropped_tokens, quotes, unmatched_quotes (못 찾은 인용문 앞부분)
"""

from __future__ import annotations

import re

from compressors.base import CompressResult, Compressor, PromptParts

MIN_LINE_CHARS = 30


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _find_block(lines: list[str], qlines: list[str]) -> list[int] | None:
    """qlines 가 순서대로 이어지는 lines 구간의 줄 번호들 (빈 줄은 건너뜀). 없으면 None."""
    idx = [i for i, l in enumerate(lines) if _norm(l)]
    for start in range(len(idx)):
        hit = []
        for k, q in enumerate(qlines):
            if start + k >= len(idx):
                break
            c = _norm(lines[idx[start + k]])
            if not (q in c or (c in q and len(c) >= min(len(q), MIN_LINE_CHARS))):
                break
            hit.append(idx[start + k])
        if len(hit) == len(qlines):
            return hit
    return None


def evidence_lines(context: str, quotes: tuple[str, ...]) -> tuple[set[int], list[str]]:
    """(지울 줄 번호, 못 찾은 인용문)."""
    lines = context.split("\n")
    drop: set[int] = set()
    unmatched = []
    for quote in quotes:
        qlines = [_norm(x) for x in quote.split("\n") if _norm(x)]
        if not qlines:
            continue
        found: set[int] = set()
        if len(qlines) == 1:
            found = {i for i, l in enumerate(lines) if qlines[0] in _norm(l)}
        else:
            block = _find_block(lines, qlines)
            found = set(block or [])
        if not found:
            q = _norm(quote)
            found = {i for i, l in enumerate(lines)
                     if len(_norm(l)) >= MIN_LINE_CHARS and (_norm(l) in q or q in _norm(l))}
        if found:
            drop |= found
        else:
            unmatched.append(quote[:60])
    return drop, unmatched


class DropEvidence(Compressor):
    name = "drop_evidence"
    targets = ("context",)

    def compress(self, parts: PromptParts) -> CompressResult:
        self._quotes = parts.evidence
        return super().compress(parts)

    def compress_context(self, question: str, context: str) -> str:
        from llm import count_tokens   # 토크나이저는 실제로 지울 때만 불러온다

        lines = context.split("\n")
        drop, unmatched = evidence_lines(context, self._quotes)
        dropped = [lines[i] for i in sorted(drop)]
        self.add_info(quotes=len(self._quotes), dropped_lines=len(dropped),
                      dropped_tokens=count_tokens("\n".join(dropped)) if dropped else 0,
                      unmatched_quotes=unmatched)
        return "\n".join(l for i, l in enumerate(lines) if i not in drop)

    def config(self) -> dict:
        return {"min_line_chars": MIN_LINE_CHARS}
