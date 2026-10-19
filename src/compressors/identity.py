"""압축하지 않음 (Baseline)."""

from __future__ import annotations

from compressors.base import Compressor


class NoCompression(Compressor):
    name = "none"
    targets = ("context",)

    def compress_context(self, question: str, context: str) -> str:
        return context


class EmptyContext(Compressor):
    """문서를 비운다 (바닥값). system·question 은 그대로.
    실험과 같은 답변 지시문(문서에서만 답하고 없으면 NOT FOUND)으로 문서 없이 얼마나 맞히는지 본다.
    보정 유지율의 기준점이 된다 (experiment.calibrated_retention)."""
    name = "empty"
    targets = ("context",)

    def compress_context(self, question: str, context: str) -> str:
        return ""
