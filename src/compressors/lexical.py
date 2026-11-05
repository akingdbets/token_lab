"""
질문과 문장의 단어 일치 점수 (모델·API 없음, 결과가 항상 같다)

query_extract(qx_*)와 supplement(sup_*)가 같이 쓴다. 점수 함수는 모두 같은 모양이다.

    scorer(question, texts) -> list[float]     texts 하나마다 점수 하나, 0 이면 질문과 겹치는 단어 없음

    bm25         texts 를 말뭉치로 보고 질문의 BM25. 식별자는 통째로 + snake_case/CamelCase 조각으로 센다
    word_cosine  질문과 문장의 단어 빈도 벡터 코사인. feature/question-guided-repair-v1 (PR #57) 의
                 relevance() 와 같은 계산 (\\w+ 소문자, 같은 불용어). 두 점수를 같은 압축기에서 비교하려고 옮겨 왔다
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable

_STOP = frozenset(
    "a an the is are was were be been being do does did how what which when where who whom why "
    "with in on of to and or for by from as at it its this that these those can could should would "
    "will i you we they my your our their if then than so into about".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*|\d+(?:\.\d+)*")

# PR #57 repair.py 의 불용어와 단어 정의 (word_cosine 이 그 결과와 같도록 따로 둔다)
_REPAIR_STOP = frozenset("a an the is are was were do does how what which when where with in on of to and for".split())
_REPAIR_WORD = re.compile(r"\w+")


def terms(text: str) -> list[str]:
    """BM25 검색어 조각. 식별자는 통째로 + 조각으로, 불용어는 뺀다."""
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
    """texts 를 말뭉치로 보고 질문의 BM25 점수를 매긴다."""
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


def _bag(text: str) -> Counter:
    return Counter(w.lower() for w in _REPAIR_WORD.findall(text) if w.lower() not in _REPAIR_STOP)


def word_cosine_scores(question: str, texts: list[str]) -> list[float]:
    """질문과 각 문장의 단어 빈도 코사인 (PR #57 relevance() 와 같은 값)."""
    q = _bag(question)
    q_norm = math.sqrt(sum(v * v for v in q.values()))
    scores = []
    for text in texts:
        s = _bag(text)
        denom = q_norm * math.sqrt(sum(v * v for v in s.values()))
        scores.append(sum(v * s[k] for k, v in q.items()) / denom if denom else 0.0)
    return scores


SCORERS: dict[str, Callable[[str, list[str]], list[float]]] = {
    "bm25": bm25_scores,
    "wcos": word_cosine_scores,
}
