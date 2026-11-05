"""
턴마다 그 턴의 질문으로 문장을 골라 남기는 추출형 압축 (query-aware extractive)

멀티턴에서 압축 결과를 재사용하지 않고, 턴마다 원문에서 다시 고른다. 문장 단위로 통째로
남기거나 지우므로 남은 글자는 원문 그대로다 (sentence_select 와 같은 단위·보호 규칙).
rule 뒤에 붙인다: "rule>qx_bm25_loose_r50".

sentence_select 와 다른 점은 후보 단위의 점수뿐이다.
    bm25   질문 단어로 문서 안 후보 단위를 BM25 로 매긴다. 모델·API 없음, 결과가 항상 같다.
           식별자는 통째로도, snake_case/CamelCase 조각으로도 센다 (create_access_token -> create, access, token).
    emb    질문과 후보 단위의 임베딩 코사인 (CFG.embed_model, 기본 bge-m3).
           단위 임베딩은 질문과 무관해 프로세스 안에서 캐시한다 (같은 문서의 다음 턴은 질문 임베딩 1회만 든다).

선택
    keep_ratio  점수 높은 순으로 후보 글자의 이 비율까지 남긴다 (기본). 상한이라, 점수 0 인
                (질문과 겹치는 데가 없는) 후보로 예산을 채우지는 않는다.
    후보 점수가 모두 0 이면 고를 근거가 없으므로 그 문서는 그대로 둔다.
    min_score   주면 비율 대신 기준점 방식: 점수가 이 값 이상인 후보만 남긴다 (문서마다 남는 양이 다르다).
                기준값은 dev 에서 정한다. bm25 점수는 문서마다 척도가 달라, 문서 안 최고점으로 나눈 값(0~1)에 적용한다.

비용 메모
    턴마다 문맥이 바뀌므로 답변 모델의 프롬프트 캐시를 못 쓴다. 멀티턴 절감 계산에서 원문+캐시와 비교한다.
    emb 의 임베딩 호출은 답변 LLM 토큰이 아니므로 llm_prompt_tokens 에 넣지 않고 info 의 embed_calls 로 남긴다.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable

from compressors.sentence_select import SentenceSelectCompressor, Unit

POLICY_VERSION = "query-extract-v1"

_STOP = frozenset(
    "a an the is are was were be been being do does did how what which when where who whom why "
    "with in on of to and or for by from as at it its this that these those can could should would "
    "will i you we they my your our their if then than so into about".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*|\d+(?:\.\d+)*")


def terms(text: str) -> list[str]:
    """검색어 조각. 식별자는 통째로 + 조각으로, 불용어는 뺀다."""
    out: list[str] = []
    for raw in _WORD.findall(text):
        word = raw.lower()
        parts = [p.lower() for p in re.split(r"_+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", raw) if p]
        if word not in _STOP:
            out.append(word)
        if len(parts) > 1:
            out.extend(p for p in parts if p not in _STOP and len(p) > 1)
    return out


def bm25_scores(question: str, texts: list[str], k1: float = 1.2, b: float = 0.75) -> list[float]:
    """문서 안 후보 단위들을 말뭉치로 보고 질문의 BM25 점수를 매긴다."""
    docs = [terms(t) for t in texts]
    n = len(docs)
    if not n:
        return []
    avgdl = sum(map(len, docs)) / n or 1.0
    df = Counter(term for d in docs for term in set(d))
    query = list(dict.fromkeys(terms(question)))
    scores = []
    for d in docs:
        tf = Counter(d)
        score = 0.0
        for term in query:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(d) / avgdl))
        scores.append(score)
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    denom = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / denom if denom else 0.0


class QueryExtractCompressor(SentenceSelectCompressor):
    """그 턴의 질문과 관련 높은 문장·목록 항목만 남긴다. 보호 단위는 항상 남는다."""

    def __init__(
        self,
        *,
        scorer: str = "bm25",
        keep_ratio: float = 0.5,
        min_score: float | None = None,
        protect: str = "loose",
        embed: Callable[[str], list[float]] | None = None,
        name: str | None = None,
        **kwargs,
    ):
        if scorer not in ("bm25", "emb"):
            raise ValueError("scorer는 bm25 또는 emb 여야 합니다")
        super().__init__(keep_ratio=keep_ratio, protect=protect, **kwargs)
        self.query_scorer = scorer
        self.min_score = None if min_score is None else float(min_score)
        self._embed = embed
        self._embed_cache: dict[str, list[float]] = {}
        self._embed_calls = 0
        mode = f"t{round(self.min_score * 100):02d}" if self.min_score is not None else f"r{round(self.keep_ratio * 100):02d}"
        self.name = name or f"qx_{scorer}_{protect}_{mode}"
        self.scorer_name = scorer

    def config(self) -> dict:
        cfg = super().config()
        cfg.update(
            method="query_extract",
            policy_version=POLICY_VERSION,
            scorer=self.query_scorer,
            min_score=self.min_score,
            uses_question=True,
        )
        if self.query_scorer == "bm25":
            cfg.pop("model_name", None)
            cfg.pop("model_revision", None)
        else:
            from config import CFG
            cfg.update(model_name=getattr(CFG, "embed_model", None), model_revision=None)
        return cfg

    def _extra_info(self) -> dict:
        info = {"method": "query_extract", "policy_version": POLICY_VERSION, "uses_question": True,
                "scorer": self.query_scorer, "min_score": self.min_score}
        if self.query_scorer == "emb":
            info["embed_calls"] = self._embed_calls
        return info

    def compress_context(self, question: str, context: str) -> str:
        self._embed_calls = 0
        return super().compress_context(question, context)

    def _vector(self, text: str) -> list[float]:
        if self._embed is None:
            from llm import LLM
            self._embed = LLM(role="embed").embed
        if text not in self._embed_cache:
            self._embed_cache[text] = self._embed(text)
            self._embed_calls += 1
        return self._embed_cache[text]

    def _score_candidates(self, question: str, texts: list[str]) -> list[float]:
        if self.query_scorer == "bm25":
            scores = bm25_scores(question, texts)
            top = max(scores, default=0.0)
            return [s / top if top > 0 else 0.0 for s in scores]   # 문서 안 최고점 = 1
        q = self._vector(question)
        return [_cosine(q, self._vector(t)) for t in texts]

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
