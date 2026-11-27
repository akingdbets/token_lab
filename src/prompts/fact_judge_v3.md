# fact_judge_v3

fact_judge_v2 의 per_fact 판정(FACT_JUDGE_SINGLE_PROMPT)에 "문서상 정당한 다른 답(accept_alternatives)" 을 더한 버전이다.
grader.py 가 아래 `## alternatives_block` 을 읽어, 대안이 있는 fact 에만 `Fact:` 블록 바로 뒤에 넣는다.
**대안이 없는 fact 는 v2 의 FACT_JUDGE_SINGLE_PROMPT 와 글자 그대로 같은 프롬프트가 된다** (tests/test_grader.py 로 확인).
batch 모드는 지원하지 않는다 (multiturn 실험은 per_fact).

`{alternatives}` 는 대안마다 `- ` 로 시작하는 줄이다.

## alternatives_block

Alternative answers that are also correct for this fact (the candidate satisfies the fact if it conveys the fact itself or any one of these alternatives):
{alternatives}
