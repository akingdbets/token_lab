"""
정답 채점

평가셋 생성(dataset_builder)과 실험(experiment)이 같은 판정 기준을 쓰도록 한곳에 둔다.

판정 두 가지
    match   단어 일치 규칙. LLM 없이 결정적.
            - 짧은 정답(5단어 이하): 정답 단어들이 답변에 연속으로 그대로 있으면 정답
            - 긴 정답: 핵심 엔티티 중 절반 이상(올림)이 답변에 있으면 정답
    judge   LLM 채점 (config.judge_model). 긴 서술형 정답(절차형 등)용

최종 정답 여부(grade 의 correct)
    짧은 정답은 match, 긴 정답은 judge 를 쓴다. 둘 다 항상 기록해 나중에 비교할 수 있게 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SHORT_ANSWER_WORDS = 5


def word_tokens(s: str) -> list[str]:
    """단어 단위 비교용 토큰 (소문자, 영숫자와 _ 만). "AsyncIterable[Item]" -> [asynciterable, item]."""
    return re.findall(r"[a-z0-9_]+", s.lower())


def contains_words(haystack: list[str], needle: str) -> bool:
    """needle 의 단어들이 haystack 에 연속으로 그대로 있는지. "50" 은 "500" 에 걸리지 않는다."""
    n = word_tokens(needle)
    if not n:
        return False
    return any(haystack[i:i + len(n)] == n for i in range(len(haystack) - len(n) + 1))


def is_short(answer: str) -> bool:
    return len(answer.split()) <= SHORT_ANSWER_WORDS


def closed_book_knows(response: str, a: str, entities: list[str]) -> tuple[bool, str]:
    """답변(response)이 정답을 맞혔는지 (단어 일치 규칙). (판정, 사용한 규칙)을 돌려준다.
    - 짧은 답(5단어 이하): 정답이 답변에 단어 단위로 그대로 있으면 안다
    - 긴 답: 핵심 엔티티 중 절반 이상(올림)이 답변에 단어 단위로 있으면 안다
      (엔티티가 없으면 판정할 수 없어 모른다로 둔다)"""
    resp = word_tokens(response)
    if is_short(a):
        return contains_words(resp, a), "answer_words_in_response"
    ents = [e for e in entities if word_tokens(e)]
    if not ents:
        return False, "no_entities"
    need = -(-len(ents) // 2)            # 절반 올림
    hit = sum(contains_words(resp, e) for e in ents)
    return hit >= need, f"entities_in_response {hit}/{len(ents)} (need {need})"


JUDGE_PROMPT = """You are grading an answer to a question about the FastAPI documentation.

Question: {q}
Reference answer: {a}
Candidate answer: {r}

Does the candidate answer contain the information in the reference answer, without contradicting it?
Extra correct details are fine. Reply with exactly one word: YES or NO."""


@dataclass
class Grade:
    correct: bool           # 최종 판정 (짧은 정답은 match, 긴 정답은 judge)
    method: str             # "match" | "judge"
    match: bool
    match_rule: str
    judge: bool | None      # judge 를 부르지 않았으면 None
    judge_raw: str = ""
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0


def grade(question: str, answer: str, entities: list[str], response: str,
          judge_llm=None, always_judge: bool = False) -> Grade:
    """judge_llm 이 None 이면 judge 없이 match 만 쓴다 (긴 정답도 match 로 판정)."""
    m, rule = closed_book_knows(response, answer, entities)
    need_judge = judge_llm is not None and (always_judge or not is_short(answer))
    j, raw, pt, ct = None, "", 0, 0
    if need_judge:
        res = judge_llm.ask(JUDGE_PROMPT.format(q=question, a=answer, r=response))
        raw = res.text.strip()
        j = raw.upper().startswith("YES")
        pt, ct = res.prompt_tokens, res.completion_tokens
    use_judge = j is not None and not is_short(answer)
    return Grade(correct=j if use_judge else m, method="judge" if use_judge else "match",
                 match=m, match_rule=rule, judge=j, judge_raw=raw,
                 judge_prompt_tokens=pt, judge_completion_tokens=ct)
