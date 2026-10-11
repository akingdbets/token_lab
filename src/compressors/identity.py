"""압축하지 않음 (Baseline)."""

from __future__ import annotations

from compressors.base import Compressor


class NoCompression(Compressor):
    name = "none"
    targets = ("context",)

    def compress_context(self, question: str, context: str) -> str:
        return context
