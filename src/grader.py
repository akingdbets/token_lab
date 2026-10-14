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

import hashlib
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
    judge_usage_source: str | None = None   # api | estimate (judge 를 안 불렀으면 None)


def usage_source_of(sources, attr: str = "usage_source") -> str | None:
    """여러 호출(LLMResult 등)의 usage_source -> api | estimate | mixed (호출이 없으면 None)."""
    found = {getattr(x, attr, None) or "api" for x in sources}
    if not found:
        return None
    return found.pop() if len(found) == 1 else "mixed"


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
    usage_source = None

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
        usage_source = usage_source_of([res])

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
        judge_usage_source=usage_source,
    )


# ============================================================
# 신규 v0: key_facts 기반 답변 정확도 평가
# ============================================================

#
# fact_judge_v2
#   v1 은 출력 예시에 index 0, 1 두 개만 있어서 key_facts 가 3개 이상이어도
#   judge 가 결과를 2개만 돌려주는 경우가 많았다 (누락 index 는 불충족 처리 -> 정확도 과소 측정).
#   v2 는 key_facts 에 [i] 번호를 붙이고, 출력 예시를 실제 개수 N 에 맞춰 0..N-1 전부로 만들며,
#   "Return exactly N results" 를 명시한다.
#   응답의 index 집합이 {0..N-1} 과 다르면 1회 재요청하고, 그래도 다르면 fact 별 개별 판정으로 폴백한다.

FACT_JUDGE_PROMPT_VERSION = "fact_judge_v2"

FACT_JUDGE_PROMPT = """You are evaluating an answer to a technical question.

Question:
{question}

Reference answer:
{reference_answer}

Candidate answer:
{candidate_answer}

Below are the {n} essential facts that a correct answer should convey, numbered [0] to [{last}].

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

Return exactly {n} results, one per index, for every index from 0 to {last}.
Each index must appear exactly once. Replace each <true|false> with your judgement.

Return ONLY valid JSON in exactly this format:

{example}
"""

FACT_JUDGE_RETRY_PROMPT = """Your previous reply was incomplete or invalid: {problems}.

There are {n} facts, numbered [0] to [{last}]. Return exactly {n} results, one per index,
every index from 0 to {last} exactly once{missing_hint}.

Return ONLY valid JSON in exactly this format:

{example}
"""

FACT_JUDGE_SINGLE_PROMPT = """You are evaluating an answer to a technical question.

Question:
{question}

Reference answer:
{reference_answer}

Candidate answer:
{candidate_answer}

Fact:
{fact}

Does the candidate answer convey this fact correctly?

Rules:
- Judge meaning, not exact wording. Paraphrases are acceptable.
- The fact is satisfied only if the candidate answer actually conveys it.
- If the candidate answer contradicts the fact, answer NO.
- Do not give credit merely because related keywords appear.

Reply with exactly one word: YES or NO."""

# 프롬프트 문구가 같은 버전 이름으로 바뀌었는지 확인용 (trial 기록에 남긴다)
FACT_JUDGE_PROMPT_HASH = hashlib.sha256(
    "\n---\n".join(
        (FACT_JUDGE_PROMPT, FACT_JUDGE_RETRY_PROMPT, FACT_JUDGE_SINGLE_PROMPT)
    ).encode("utf-8")
).hexdigest()[:12]

JUDGE_MODES = ("batch", "per_fact")

# 답변 전체가 NOT FOUND 인지 (대소문자·앞뒤 공백·마침표 무시). 이 경우 judge 를 부르지 않는다
_NOT_FOUND_ONLY = re.compile(r"[\s.]*not\s+found[\s.]*", re.IGNORECASE)


def is_not_found_answer(answer: str) -> bool:
    return bool(_NOT_FOUND_ONLY.fullmatch(answer or ""))


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

    judge_mode
        batch              첫 응답이 바로 완전했음
        retry              재요청 1회로 완전해짐
        per_fact_fallback  재요청도 불완전해서 fact 별 개별 판정으로 채움
        per_fact           처음부터 fact 별 개별 판정 (--judge-mode per_fact)
        skipped            judge 를 부르지 않음 (judge_skipped 에 사유)

    judge_skipped
        not_found          답변이 NOT FOUND 뿐이라 judge 없이 모든 key_fact 를 불충족으로 처리
                           (judge 가 NOT FOUND 답변에 fact 를 충족으로 주는 오판 방지)
    """

    answer_accuracy: float

    satisfied_count: int
    total_count: int

    fact_results: list[FactResult] = field(default_factory=list)

    judge_raw: str = ""

    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0
    judge_usage_source: str | None = None   # api | estimate | mixed (judge 를 안 불렀으면 None)

    judge_prompt_version: str = FACT_JUDGE_PROMPT_VERSION
    judge_prompt_hash: str = FACT_JUDGE_PROMPT_HASH
    judge_mode: str = "batch"
    judge_retries: int = 0
    judge_missing_before_fix: list[int] = field(default_factory=list)  # 첫 응답에서 빠진 index
    judge_calls: int = 0
    judge_skipped: str | None = None


def _build_facts_text(key_facts: list[str]) -> str:
    """Judge prompt에 넣을 key_facts 목록 생성. [0], [1], ... 번호를 붙인다."""

    return "\n".join(
        f"[{i}] {fact}"
        for i, fact in enumerate(key_facts)
    )


def _build_output_example(n: int) -> str:
    """index 0..n-1 전부를 담은 출력 예시. satisfied 값은 placeholder."""

    rows = ",\n".join(
        f'    {{"index": {i}, "satisfied": <true|false>}}'
        for i in range(n)
    )

    return '{\n  "results": [\n' + rows + "\n  ]\n}"


@dataclass
class _Parsed:
    """judge JSON 응답 파싱 결과와 index 검증 정보."""

    values: dict[int, bool]          # 중복 없이 범위 안에 있는 index 의 판정
    missing: list[int]
    duplicates: list[int]
    out_of_range: list
    invalid: int = 0                 # index/satisfied 형식이 잘못된 항목 수
    json_error: bool = False

    @property
    def ok(self) -> bool:
        return not (self.missing or self.duplicates or self.out_of_range
                    or self.invalid or self.json_error)

    def problems(self) -> str:
        p = []
        if self.json_error:
            p.append("the reply was not valid JSON")
        if self.missing:
            p.append(f"missing index {self.missing}")
        if self.duplicates:
            p.append(f"duplicated index {self.duplicates}")
        if self.out_of_range:
            p.append(f"out-of-range index {self.out_of_range}")
        if self.invalid:
            p.append(f"{self.invalid} malformed item(s)")
        return "; ".join(p) or "unknown problem"


def _parse_fact_judgement(raw: str, n: int) -> _Parsed:
    """
    LLM Judge의 JSON 결과를 파싱하고 index 집합이 정확히 {0..n-1} 인지 검사한다.

    중복된 index 는 판정을 믿을 수 없으므로 values 에서 빼고 missing 으로도 센다.
    """

    json_error = False

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
        if not isinstance(raw_results, list):
            raise TypeError

    except (json.JSONDecodeError, AttributeError, TypeError):
        raw_results = []
        json_error = True

    seen: dict[int, bool] = {}
    duplicates: set[int] = set()
    out_of_range = []
    invalid = 0

    for item in raw_results:
        if not isinstance(item, dict):
            invalid += 1
            continue

        index = item.get("index")
        satisfied = item.get("satisfied")

        if isinstance(index, bool) or not isinstance(index, int) or not isinstance(satisfied, bool):
            invalid += 1
            continue

        if not 0 <= index < n:
            out_of_range.append(index)
            continue

        if index in seen:
            duplicates.add(index)
            continue

        seen[index] = satisfied

    values = {i: v for i, v in seen.items() if i not in duplicates}

    return _Parsed(
        values=values,
        missing=[i for i in range(n) if i not in values and i not in duplicates],
        duplicates=sorted(duplicates),
        out_of_range=out_of_range,
        invalid=invalid,
        json_error=json_error,
    )


def _judge_single_fact(
    question: str,
    reference_answer: str,
    fact: str,
    candidate_answer: str,
    judge_llm,
):
    """fact 하나만 YES/NO 로 판정. (satisfied, LLMResult) 반환."""

    res = judge_llm.ask(
        FACT_JUDGE_SINGLE_PROMPT.format(
            question=question,
            reference_answer=reference_answer,
            candidate_answer=candidate_answer,
            fact=fact,
        )
    )

    return res.text.strip().upper().startswith("YES"), res


def grade_answer_accuracy(
    question: str,
    reference_answer: str,
    key_facts: list[str],
    candidate_answer: str,
    judge_llm,
    mode: str = "batch",
) -> AnswerAccuracyResult:
    """
    key_facts를 기준으로 Candidate Answer의 답변 정확도를 계산한다.

    예:
        key_facts 4개 중 3개 충족

        answer_accuracy = 3 / 4 = 0.75

    v0에서는 모든 key_fact의 가중치를 동일하게 둔다.

    mode
        batch     한 번의 호출로 모든 fact 판정. 응답 index 가 {0..N-1} 과 다르면
                  누락 index 를 명시해 1회 재요청하고, 그래도 다르면 fact 별 개별 판정으로 폴백.
        per_fact  처음부터 fact 하나당 호출 1회 (YES/NO).

    답변이 NOT FOUND 뿐이면 mode 와 상관없이 judge 를 부르지 않고 모두 불충족 (judge_skipped="not_found").
    """

    if mode not in JUDGE_MODES:
        raise ValueError(f"알 수 없는 judge mode: {mode} ({JUDGE_MODES})")

    key_facts = [
        str(fact).strip()
        for fact in key_facts
        if str(fact).strip()
    ]

    if not key_facts:
        raise ValueError(
            "답변 정확도를 계산하려면 key_facts가 1개 이상 필요합니다."
        )

    if is_not_found_answer(candidate_answer):
        return AnswerAccuracyResult(
            answer_accuracy=0.0,
            satisfied_count=0,
            total_count=len(key_facts),
            fact_results=[FactResult(fact=fact, satisfied=False) for fact in key_facts],
            judge_mode="skipped",
            judge_skipped="not_found",
        )

    if judge_llm is None:
        raise ValueError(
            "key_facts 평가를 위해 judge_llm이 필요합니다."
        )

    n = len(key_facts)
    last = n - 1
    example = _build_output_example(n)

    pt = ct = calls = retries = 0
    responses = []
    raws: list[str] = []
    missing_before: list[int] = []
    values: dict[int, bool] | None = None
    judge_mode = mode

    def _use(res):
        nonlocal pt, ct, calls
        pt += res.prompt_tokens
        ct += res.completion_tokens
        calls += 1
        responses.append(res)

    if mode == "batch":
        prompt = FACT_JUDGE_PROMPT.format(
            question=question,
            reference_answer=reference_answer,
            candidate_answer=candidate_answer,
            facts=_build_facts_text(key_facts),
            n=n,
            last=last,
            example=example,
        )

        res = judge_llm.ask(prompt)
        _use(res)
        raws.append(res.text.strip())
        first = _parse_fact_judgement(res.text, n)

        if first.ok:
            values = first.values
        else:
            # 중복된 index 도 다시 받아야 하므로 누락에 포함
            missing_before = sorted(set(first.missing) | set(first.duplicates))
            retries = 1

            retry_prompt = FACT_JUDGE_RETRY_PROMPT.format(
                problems=first.problems(),
                n=n,
                last=last,
                missing_hint=(
                    f", including the missing index {missing_before}"
                    if missing_before
                    else ""
                ),
                example=example,
            )

            res = judge_llm.chat([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raws[0]},
                {"role": "user", "content": retry_prompt},
            ])
            _use(res)
            raws.append(res.text.strip())
            second = _parse_fact_judgement(res.text, n)

            # 재요청에는 누락분만 돌려줄 수도 있으므로 첫 응답의 유효한 판정과 합친다.
            # 단 재요청 응답 자체에 중복·범위 밖·형식 오류가 있으면 믿지 않는다.
            merged = {**first.values, **second.values}
            if (
                not (second.duplicates or second.out_of_range or second.invalid or second.json_error)
                and set(merged) == set(range(n))
            ):
                values = merged
                judge_mode = "retry"
            else:
                judge_mode = "per_fact_fallback"

    if values is None:
        # per_fact 모드이거나 batch 재요청까지 실패한 경우: fact 하나씩 판정
        values = {}
        for i, fact in enumerate(key_facts):
            ok, res = _judge_single_fact(
                question, reference_answer, fact, candidate_answer, judge_llm,
            )
            _use(res)
            raws.append(f"[{i}] {res.text.strip()}")
            values[i] = ok

    fact_results = [
        FactResult(fact=fact, satisfied=values[i])
        for i, fact in enumerate(key_facts)
    ]

    satisfied_count = sum(
        result.satisfied
        for result in fact_results
    )

    return AnswerAccuracyResult(
        answer_accuracy=satisfied_count / n,
        satisfied_count=satisfied_count,
        total_count=n,
        fact_results=fact_results,
        judge_raw="\n---\n".join(raws),
        judge_prompt_tokens=pt,
        judge_completion_tokens=ct,
        judge_usage_source=usage_source_of(responses),
        judge_mode=judge_mode,
        judge_retries=retries,
        judge_missing_before_fix=missing_before,
        judge_calls=calls,
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