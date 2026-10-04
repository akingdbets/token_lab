"""압축기 공통 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompressResult:
    text: str                           # 압축된 문맥
    llm_prompt_tokens: int = 0          # 압축 과정에서 LLM 에 넣은 토큰 (LLM 기반 압축기만)
    llm_completion_tokens: int = 0      # 압축 과정에서 LLM 이 낸 토큰
    info: dict = field(default_factory=dict)   # 압축기별 부가 정보 (규칙별 적용 횟수 등)


class Compressor:
    """압축기 기본형. name 과 compress 만 구현하면 실험 실행기에 붙는다."""
    name: str = "base"

    def compress(self, question: str, context: str) -> CompressResult:
        raise NotImplementedError

    def config(self) -> dict:
        """실험 로그에 남길 설정값 (재현용)."""
        return {}
