"""압축하지 않음 (Baseline)."""

from __future__ import annotations

from compressors.base import CompressResult, Compressor


class NoCompression(Compressor):
    name = "none"

    def compress(self, question: str, context: str) -> CompressResult:
        return CompressResult(text=context)
