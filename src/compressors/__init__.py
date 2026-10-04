"""
문맥 압축기 모음

모든 압축기는 같은 인터페이스를 따른다 (팀 Spec이 정해지면 여기만 고친다).

    compress(question: str, context: str) -> CompressResult

    question  사용자 질문. 질문을 보지 않는 압축기는 무시한다
    context   LLM 에 넣을 문맥 원문 (여러 문서면 이미 합쳐진 문자열)
    반환      CompressResult(text=압축된 문맥, llm_prompt_tokens=..., llm_completion_tokens=...)
              LLM 을 쓰지 않는 압축기는 토큰 필드를 0 으로 둔다.
              압축에 쓴 LLM 토큰은 순 토큰 절감률 계산에 들어간다.

압축기 등록
    REGISTRY 에 이름 -> 압축기 객체를 추가한다. 실험 실행기는 이름으로만 고른다.
        python src/experiment.py --compressors none,rule

사용 예
    from compressors import get_compressor
    res = get_compressor("rule").compress("질문", "문맥 원문")
    print(res.text)
"""

from __future__ import annotations

from compressors.base import CompressResult, Compressor
from compressors.identity import NoCompression
from compressors.rule import RuleCompressor

REGISTRY: dict[str, Compressor] = {
    "none": NoCompression(),        # 기준선 (Baseline): 원문 그대로
    "rule": RuleCompressor(),       # 규칙 기반 문맥 정제 (마크다운 휴리스틱)
}


def get_compressor(name: str) -> Compressor:
    if name not in REGISTRY:
        raise KeyError(f"등록되지 않은 압축기: {name} (등록됨: {', '.join(REGISTRY)})")
    return REGISTRY[name]


__all__ = ["CompressResult", "Compressor", "REGISTRY", "get_compressor"]
