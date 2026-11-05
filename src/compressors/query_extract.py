"""
턴마다 그 턴의 질문으로 문장을 골라 남기는 추출형 압축 (query-aware extractive)

멀티턴에서 압축 결과를 재사용하지 않고, 턴마다 원문에서 다시 고른다. 문장 단위로 통째로
남기거나 지우므로 남은 글자는 원문 그대로다 (sentence_select 와 같은 단위·보호 규칙).
rule 뒤에 붙인다: "rule>qx_bm25_loose_r50".

sentence_select 와 다른 점은 후보 단위의 점수뿐이다.
    bm25   질문 단어로 문서 안 후보 단위를 BM25 로 매긴다. 모델·API 없음, 결과가 항상 같다.
           식별자는 통째로도, snake_case/CamelCase 조각으로도 센다 (create_access_token -> create, access, token).
    임베딩 코사인 점수(emb)는 매 턴 임베딩 호출이 들고 실험 계획에 없어 뺐다.

선택
    keep_ratio  점수 높은 순으로 후보 글자의 이 비율까지 남긴다 (기본). 상한이라, 점수 0 인
                (질문과 겹치는 데가 없는) 후보로 예산을 채우지는 않는다.
    후보 점수가 모두 0 이면 고를 근거가 없으므로 그 문서는 그대로 둔다.
    min_score   주면 비율 대신 기준점 방식: 점수가 이 값 이상인 후보만 남긴다 (문서마다 남는 양이 다르다).
                기준값은 dev 에서 정한다. bm25 점수는 문서마다 척도가 달라, 문서 안 최고점으로 나눈 값(0~1)에 적용한다.

비용 메모
    턴마다 문맥이 바뀌므로 답변 모델의 프롬프트 캐시를 못 쓴다. 멀티턴 절감 계산에서 원문+캐시와 비교한다.
"""

from __future__ import annotations

from compressors.lexical import bm25_scores, terms  # noqa: F401  (terms 는 테스트·하위 호환용)
from compressors.sentence_select import SentenceSelectCompressor, Unit

POLICY_VERSION = "query-extract-v1"


class QueryExtractCompressor(SentenceSelectCompressor):
    """그 턴의 질문과 관련 높은 문장·목록 항목만 남긴다. 보호 단위는 항상 남는다."""

    def __init__(
        self,
        *,
        keep_ratio: float = 0.5,
        min_score: float | None = None,
        protect: str = "loose",
        name: str | None = None,
        **kwargs,
    ):
        super().__init__(keep_ratio=keep_ratio, protect=protect, **kwargs)
        self.min_score = None if min_score is None else float(min_score)
        mode =f"t{round(self.min_score * 100):02d}" if self.min_score is not None else f"r{round(self.keep_ratio * 100):02d}"
        self.name = name or f"qx_bm25_{protect}_{mode}"
        self.scorer_name = "bm25"

    def config(self) -> dict:
        cfg = super().config()
        cfg.update(
            method="query_extract",
            policy_version=POLICY_VERSION,
            scorer="bm25",
            min_score=self.min_score,
            uses_question=True,
        )
        cfg.pop("model_name", None)       # BM25 는 모델을 쓰지 않는다
        cfg.pop("model_revision", None)
        return cfg

    def _extra_info(self) -> dict:
        return {"method": "query_extract", "policy_version": POLICY_VERSION, "uses_question": True,
                "scorer": "bm25", "min_score": self.min_score}

    def _score_candidates(self, question: str, texts: list[str]) -> list[float]:
        scores = bm25_scores(question, texts)
        top = max(scores, default=0.0)
        return [s / top if top > 0 else 0.0 for s in scores]   # 문서 안 최고점 = 1

    def _select(self, units: list[Unit], candidates: list[int], scores: list[float]) -> list[bool]:
        if not any(score > 0 for score in scores):
            # 질문과 겹치는 후보가 하나도 없으면 고를 근거가 없다: 그대로 둔다
            return [True] * len(units)
        if self.min_score is None:
            # 비율은 상한이다: 점수 0(질문과 무관)인 후보로 예산을 채우지 않는다
            keep = super()._select(units, candidates, scores)
            for i, score in zip(candidates, scores):
                if score <= 0:
                    keep[i] = False
            return keep
        keep = [True] * len(units)
        for i, score in zip(candidates, scores):
            keep[i] = score >= self.min_score
        return keep
