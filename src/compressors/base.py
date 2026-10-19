"""압축기 공통 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

PARTS = ("system", "context", "question")


@dataclass
class PromptParts:
    """LLM 입력을 이루는 세 부분. 답변 메시지는 system + user(context, question) 로 조립된다."""
    system: str                         # system 지시문 전체 (persona 줄을 끼운 뒤)
    context: str                        # 근거 문서 문맥 (여러 문서면 이미 합쳐진 문자열)
    question: str                       # 사용자 질문
    # 문항의 근거 인용문 (평가셋 evidence[].quote). 압축 대상이 아니라 drop_evidence 같은 진단용 압축기만 읽는다
    evidence: tuple[str, ...] = ()


@dataclass
class CompressResult:
    system: str                         # 압축된 system (대상이 아니면 입력 그대로)
    context: str                        # 압축된 문맥
    question: str                       # 압축된 질문
    llm_prompt_tokens: int = 0          # 압축 과정에서 LLM 에 넣은 토큰 (LLM 기반 압축기만)
    llm_completion_tokens: int = 0      # 압축 과정에서 LLM 이 낸 토큰
    info: dict = field(default_factory=dict)   # 압축기별 부가 정보 (규칙별 적용 횟수 등)

    @property
    def parts(self) -> PromptParts:
        return PromptParts(system=self.system, context=self.context, question=self.question)

    @property
    def text(self) -> str:
        """하위 호환: 예전 CompressResult.text (압축된 문맥)."""
        return self.context


class Compressor:
    """압축기 기본형.

    name 과 targets 를 정하고, targets 에 든 부분의 훅만 재정의하면 된다.
        compress_context(question, context) -> str
        compress_question(question, context) -> str
        compress_system(system, question) -> str
    훅은 모두 압축 전 원본 parts 를 받는다 (한 압축기 안에서 부분끼리 순서 의존이 없도록).
    LLM 을 쓰는 훅은 self.add_llm_tokens(...), 부가 정보는 self.add_info(...) 로 남긴다.
    """
    name: str = "base"
    targets: tuple[str, ...] = ("context",)

    def compress(self, parts: PromptParts) -> CompressResult:
        bad = set(self.targets) - set(PARTS)
        if bad:
            raise ValueError(f"{self.name}: 알 수 없는 압축 대상 {sorted(bad)}")
        self._prompt_tokens = self._completion_tokens = 0
        self._info: dict = {}
        out = replace(parts)
        if "system" in self.targets:
            out.system = self.compress_system(parts.system, parts.question)
        if "context" in self.targets:
            out.context = self.compress_context(parts.question, parts.context)
        if "question" in self.targets:
            out.question = self.compress_question(parts.question, parts.context)
        return CompressResult(system=out.system, context=out.context, question=out.question,
                              llm_prompt_tokens=self._prompt_tokens,
                              llm_completion_tokens=self._completion_tokens, info=self._info)

    # ---- 기법별 훅 (targets 에 든 것만 재정의) ----

    def compress_context(self, question: str, context: str) -> str:
        raise NotImplementedError(f"{self.name}: targets 에 context 가 있으면 compress_context 를 구현해야 합니다")

    def compress_question(self, question: str, context: str) -> str:
        raise NotImplementedError(f"{self.name}: targets 에 question 이 있으면 compress_question 을 구현해야 합니다")

    def compress_system(self, system: str, question: str) -> str:
        raise NotImplementedError(f"{self.name}: targets 에 system 이 있으면 compress_system 을 구현해야 합니다")

    # ---- 훅에서 쓰는 기록 도구 ----

    def add_llm_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._prompt_tokens += prompt_tokens
        self._completion_tokens += completion_tokens

    def add_info(self, **info) -> None:
        self._info.update(info)

    def config(self) -> dict:
        """실험 로그에 남길 설정값 (재현용)."""
        return {}


class Chain(Compressor):
    """압축기를 순서대로 이어 붙인다 (--compressors "rule>llmlingua2").
    앞 단계 출력 parts 가 다음 단계 입력이고, LLM 토큰은 단계별로 합산한다."""

    def __init__(self, stages: list[Compressor]):
        self.stages = stages
        self.name = ">".join(s.name for s in stages)
        self.targets = tuple(p for p in PARTS if any(p in s.targets for s in stages))

    def compress(self, parts: PromptParts) -> CompressResult:
        pt = ct = 0
        info = {}
        for i, stage in enumerate(self.stages):
            res = stage.compress(parts)
            nxt = res.parts
            nxt.evidence = parts.evidence     # 근거 인용문은 다음 단계에도 그대로 넘긴다
            parts = nxt
            pt += res.llm_prompt_tokens
            ct += res.llm_completion_tokens
            info[f"{i + 1}:{stage.name}"] = res.info
        return CompressResult(system=parts.system, context=parts.context, question=parts.question,
                              llm_prompt_tokens=pt, llm_completion_tokens=ct, info=info)

    def config(self) -> dict:
        return {f"{i + 1}:{s.name}": s.config() for i, s in enumerate(self.stages)}
