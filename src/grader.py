"""
답변 채점기

역할
1. 기존 평가 데이터셋 생성 과정에서 사용하는 단어 기반 판정
   - closed_book_knows()

2. 실험에서 생성된 답변의 정확도 평가
   - key_facts 각각을 LLM Judge가 충족/불충족으로 판정
   - 충족한 key_facts / 전체 key_facts = 답변 정확도

v0에서는 key_fact마다 동일한 가중치를 사용한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


# ============================================================
# 기존 단어 기반 판정
# dataset_builder.py에서 사용하므로 유지
# ============================================================

SHORT_ANSWER_WORDS = 5


def word_tokens(s: str) -> list[str]:
    """단어 단위 비교용 토큰."""
    return re.findall(r"[a-z0-9_]+", s.lower())


def contains_words(haystack: list[str], needle: str) -> bool:
    """needle의 단어들이 haystack에 연속으로 존재하는지 확인."""
    n = word_tokens(needle)

    if not n:
        return False

    return any(
        haystack[i:i + len(n)] == n
        for i in range(len(haystack) - len(n) + 1)
    )


def is_short(answer: str) -> bool:
    return len(answer.split()) <= SHORT_ANSWER_WORDS


def closed_book_knows(
    response: str,
    a: str,
    entities: list[str],
) -> tuple[bool, str]:
    """
    기존 dataset_builder.py의 closed-book 검사에서 사용.

    짧은 답:
        정답 문자열이 답변에 포함되어 있는지 검사

    긴 답:
        핵심 엔티티 절반 이상이 답변에 포함되어 있는지 검사
    """

    resp = word_tokens(response)

    if is_short(a):
        return (
            contains_words(resp, a),
            "answer_words_in_response",
        )

    ents = [e for e in entities if word_tokens(e)]

    if not ents:
        return False, "no_entities"

    need = -(-len(ents) // 2)

    hit = sum(
        contains_words(resp, e)
        for e in ents
    )

    return (
        hit >= need,
        f"entities_in_response {hit}/{len(ents)} (need {need})",
    )


# ============================================================
# 기존 YES / NO 채점
# 기존 experiment.py 호환성을 위해 유지
# ============================================================

JUDGE_PROMPT = """You are grading an answer to a question about the FastAPI documentation.

Question: {q}
Reference answer: {a}
Candidate answer: {r}

Does the candidate answer contain the information in the reference answer, without contradicting it?
Extra correct details are fine.

Reply with exactly one word: YES or NO."""


@dataclass
class Grade:
    correct: bool
    method: str
    match: bool
    match_rule: str
    judge: bool | None
    judge_raw: str = ""
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0


def grade(
    question: str,
    answer: str,
    entities: list[str],
    response: str,
    judge_llm=None,
    always_judge: bool = False,
) -> Grade:
    """
    기존 grader 인터페이스.

    experiment.py 등 기존 코드가 깨지지 않도록 유지한다.
    """

    m, rule = closed_book_knows(
        response,
        answer,
        entities,
    )

    need_judge = (
        judge_llm is not None
        and (always_judge or not is_short(answer))
    )

    j = None
    raw = ""
    pt = 0
    ct = 0

    if need_judge:
        res = judge_llm.ask(
            JUDGE_PROMPT.format(
                q=question,
                a=answer,
                r=response,
            )
        )

        raw = res.text.strip()
        j = raw.upper().startswith("YES")

        pt = res.prompt_tokens
        ct = res.completion_tokens

    use_judge = (
        j is not None
        and not is_short(answer)
    )

    return Grade(
        correct=j if use_judge else m,
        method="judge" if use_judge else "match",
        match=m,
        match_rule=rule,
        judge=j,
        judge_raw=raw,
        judge_prompt_tokens=pt,
        judge_completion_tokens=ct,
    )


# ============================================================
# 신규 v0: key_facts 기반 답변 정확도 평가
# ============================================================

FACT_JUDGE_PROMPT = """You are evaluating an answer to a technical question.

Question:
{question}

Reference answer:
{reference_answer}

Candidate answer:
{candidate_answer}

Below are the essential facts that a correct answer should convey.

{facts}

For EACH fact, determine whether the candidate answer conveys that fact correctly.

Rules:
- Judge meaning, not exact wording.
- Paraphrases are acceptable.
- Do not require the exact words used in the fact.
- A fact is satisfied only if the candidate answer actually conveys it.
- If the candidate answer contradicts a fact, mark it false.
- Do not give credit merely because related keywords appear.
- Evaluate each fact independently.

Return ONLY valid JSON in exactly this format:

{{
  "results": [
    {{"index": 0, "satisfied": true}},
    {{"index": 1, "satisfied": false}}
  ]
}}
"""


@dataclass
class FactResult:
    """key_fact 하나에 대한 평가 결과."""

    fact: str
    satisfied: bool


@dataclass
class AnswerAccuracyResult:
    """
    key_facts 기반 답변 정확도 평가 결과.

    answer_accuracy
        = 충족한 key_facts 수 / 전체 key_facts 수
    """

    answer_accuracy: float

    satisfied_count: int
    total_count: int

    fact_results: list[FactResult] = field(default_factory=list)

    judge_raw: str = ""

    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0


def _build_facts_text(key_facts: list[str]) -> str:
    """Judge prompt에 넣을 key_facts 목록 생성."""

    return "\n".join(
        f"{i}. {fact}"
        for i, fact in enumerate(key_facts)
    )


def _parse_fact_judgement(
    raw: str,
    key_facts: list[str],
) -> list[FactResult]:
    """
    LLM Judge의 JSON 결과를 FactResult 목록으로 변환한다.

    잘못된 JSON이나 누락된 index가 있으면 해당 fact는
    안전하게 불충족(False)으로 처리한다.
    """

    try:
        text = raw.strip()

        # 혹시 ```json ... ``` 형태로 반환한 경우 제거
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        data = json.loads(text)

        raw_results = data.get("results", [])

    except (json.JSONDecodeError, AttributeError):
        raw_results = []

    result_map: dict[int, bool] = {}

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        index = item.get("index")
        satisfied = item.get("satisfied")

        if (
            isinstance(index, int)
            and 0 <= index < len(key_facts)
            and isinstance(satisfied, bool)
        ):
            result_map[index] = satisfied

    return [
        FactResult(
            fact=fact,
            satisfied=result_map.get(i, False),
        )
        for i, fact in enumerate(key_facts)
    ]


def grade_answer_accuracy(
    question: str,
    reference_answer: str,
    key_facts: list[str],
    candidate_answer: str,
    judge_llm,
) -> AnswerAccuracyResult:
    """
    key_facts를 기준으로 Candidate Answer의 답변 정확도를 계산한다.

    예:
        key_facts 4개 중 3개 충족

        answer_accuracy = 3 / 4 = 0.75

    v0에서는 모든 key_fact의 가중치를 동일하게 둔다.
    """

    key_facts = [
        str(fact).strip()
        for fact in key_facts
        if str(fact).strip()
    ]

    if not key_facts:
        raise ValueError(
            "답변 정확도를 계산하려면 key_facts가 1개 이상 필요합니다."
        )

    if judge_llm is None:
        raise ValueError(
            "key_facts 평가를 위해 judge_llm이 필요합니다."
        )

    facts_text = _build_facts_text(key_facts)

    prompt = FACT_JUDGE_PROMPT.format(
        question=question,
        reference_answer=reference_answer,
        candidate_answer=candidate_answer,
        facts=facts_text,
    )

    res = judge_llm.ask(prompt)

    raw = res.text.strip()

    fact_results = _parse_fact_judgement(
        raw,
        key_facts,
    )

    satisfied_count = sum(
        result.satisfied
        for result in fact_results
    )

    total_count = len(fact_results)

    answer_accuracy = (
        satisfied_count / total_count
        if total_count
        else 0.0
    )

    return AnswerAccuracyResult(
        answer_accuracy=answer_accuracy,
        satisfied_count=satisfied_count,
        total_count=total_count,
        fact_results=fact_results,
        judge_raw=raw,
        judge_prompt_tokens=res.prompt_tokens,
        judge_completion_tokens=res.completion_tokens,
    )


# ============================================================
# 압축 전/후 답변 정확도 비교
# ============================================================

def answer_accuracy_retention(
    original_accuracy: float,
    compressed_accuracy: float,
) -> float | None:
    """
    답변 정확도 유지율.

    압축 전 답변 정확도를 기준으로
    압축 후 정확도가 얼마나 유지됐는지 계산한다.

    compressed_accuracy / original_accuracy

    original_accuracy가 0이면 나눗셈이 불가능하므로 None.
    """

    if original_accuracy == 0:
        return None

    return compressed_accuracy / original_accuracy