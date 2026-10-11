"""
프롬프트 압축기 모음

LLM 입력(지시문 + 문서 + 질문)을 압축한다. 모든 압축기는 같은 인터페이스를 따른다.

    compress(parts: PromptParts) -> CompressResult

    PromptParts(system, context, question)
        system    답변 system 지시문 전체 (persona 줄을 끼운 뒤)
        context   근거 문서 문맥 (여러 문서면 이미 합쳐진 문자열)
        question  사용자 질문
    CompressResult(system, context, question, llm_prompt_tokens, llm_completion_tokens, info)
        압축된 세 부분. 압축 대상(targets)이 아닌 부분은 입력 그대로 통과한다.
        LLM 을 쓰지 않는 압축기는 토큰 필드가 0 이다.
        압축에 쓴 LLM 토큰은 순 입력 토큰 절감률 계산에 들어간다.

새 압축기 만들기
    Compressor 를 상속해 name, targets 를 정하고 targets 에 든 부분의 훅만 재정의한다.
    compress() 는 기본 구현이 훅을 불러 CompressResult 를 만든다.

        class TruncateQuestion(Compressor):
            name = "truncate_q"
            targets = ("question",)             # "context", "question", "system" 의 부분집합

            def compress_question(self, question: str, context: str) -> str:
                return question[: len(question) // 2]

        훅 (모두 압축 전 원본을 받는다)
            compress_context(question, context) -> str
            compress_question(question, context) -> str
            compress_system(system, question) -> str
        LLM 을 쓰는 훅은 self.add_llm_tokens(prompt, completion), 부가 정보는 self.add_info(key=...) 로 남긴다.

    REGISTRY 에 이름 -> 압축기 객체를 추가하면 --compressors 로 고를 수 있다.

압축기 조합
    ">" 로 순서대로 이어 붙인다. 앞 단계 출력이 다음 단계 입력이고, LLM 토큰은 단계별로 합산한다.
    기록되는 압축기 이름은 조합 문자열 그대로다. 셸에서는 ">" 가 리다이렉트이므로 따옴표로 감싼다.
        python src/experiment.py --compressors "none,rule,rule>llmlingua2"   # llmlingua2 를 등록한 뒤

사용 예
    from compressors import PromptParts, get_compressor
    res = get_compressor("rule").compress(PromptParts(system="...", context="문맥 원문", question="질문"))
    print(res.context)
"""

from __future__ import annotations

from compressors.base import PARTS, Chain, CompressResult, Compressor, PromptParts
from compressors.identity import NoCompression
from compressors.rule import RuleCompressor

REGISTRY: dict[str, Compressor] = {
    "none": NoCompression(),        # 기준선 (Baseline): 원문 그대로
    "rule": RuleCompressor(),       # 규칙 기반 문맥 정제 (마크다운 휴리스틱)
}


def get_compressor(name: str) -> Compressor:
    """이름으로 압축기를 고른다. "a>b" 는 a 다음 b 를 적용하는 조합."""
    stages = [n.strip() for n in name.split(">")]
    for n in stages:
        if n not in REGISTRY:
            raise KeyError(f"등록되지 않은 압축기: {n} (등록됨: {', '.join(REGISTRY)})")
    if len(stages) == 1:
        return REGISTRY[stages[0]]
    return Chain([REGISTRY[n] for n in stages])


__all__ = ["PARTS", "Chain", "CompressResult", "Compressor", "PromptParts", "REGISTRY", "get_compressor"]
