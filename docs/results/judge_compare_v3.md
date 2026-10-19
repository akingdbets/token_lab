# judge 검증 v3 — deepseek-flash 틀린 답 세트 (FP 확인)

deepseek-flash(per_fact) 가 틀린 답에 O 를 주는지 보려고, dev 문항의 정답을 일부러 틀리게 바꾼 답 25개를 채점했다.
사람 라벨 일치율(`judge_check_v3.csv`, gpt-6-luna 답변)은 라벨이 채워진 뒤 이 문서에 이어서 적는다.

**결과: 틀리게 만든 fact 30개에 모두 X (FP 0/30), 그대로 둔 fact 15개에 모두 O (FN 0/15).**

- 세트: `docs/results/judge_fp_set_v1.csv` (25문항, fact 한 줄당 한 행 45행). 열: qid, type, method, how, fact_idx, key_fact, wrong_answer, expected, human, note
  - `how` 에 어떻게 틀리게 했는지, `expected` 에 fact 별 기대 판정 (틀리게 만든 fact X, 그대로 둔 fact O)
  - `human` 칸은 비어 있다. 사람이 기대 판정이 맞는지 확인해 O/X 를 채우면 스크립트가 expected 대신 쓴다
- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/judge_fp_check.py docs/results/judge_fp_set_v1.csv`
- 결과 파일: `results/judge_fp/judge_fp_set_v1.jsonl`, `.summary.json` (커밋 안 함)
- judge: deepseek-flash, per_fact, fact_judge_v2 `7e441ad04bab`, temperature 0, seed 42, max_tokens 4096, reasoning_effort 서버 기본값 (실험과 같음)
- 호출 45회 (fact 하나당 1회). 이번 스크립트는 토큰 합계를 기록하지 않았다
- git commit `d94173d`

## 틀리게 만든 방법별

| 방법 | 문항 | 기대 X fact | FP (X 인데 O) | 기대 O fact | FN (O 인데 X) |
|---|---|---|---|---|---|
| value_swap (값 바꾸기: 15 → 30, 400 → 403 ...) | 10 | 11 | 0 | 0 | 0 |
| near_miss_name (비슷한 이름: anyio → asyncio, StaticPool → NullPool ...) | 5 | 5 | 0 | 0 | 0 |
| part_swap (종합형 한쪽만 틀리게) | 3 | 4 | 0 | 4 | 0 |
| step_wrong (절차 한 단계를 다른 동작으로) | 2 | 3 | 0 | 4 | 0 |
| contradiction (정답과 반대 주장) | 2 | 3 | 0 | 2 | 0 |
| step_drop (절차 한 단계 빼기) | 1 | 1 | 0 | 3 | 0 |
| step_drop+wrong_value | 1 | 2 | 0 | 2 | 0 |
| reversal (순서 뒤집기) | 1 | 1 | 0 | 0 | 0 |
| **전체** | **25** | **30** | **0** | **15** | **0** |

- 그럴듯한 오답도 걸렀다: c0002 "30" (실제 15, 같은 예제의 ACCESS_TOKEN_EXPIRE_MINUTES 값), c0035 "401" (실제 400, JWT 버전 값), c0025 `@pytest.mark.asyncio` (실제 anyio)
- 일부만 틀린 답에서 맞는 fact 는 O, 틀린 fact 는 X 로 정확히 나눴다 (c0003 OOXX, c0006 OOOX, c0029 OOOX, c0039 XOO, c0040 XXO, c0148 OXX)

## 해석과 한계

- **명백히 틀린 답은 잘 거른다.** 값·이름·순서가 바뀌거나 단계가 빠지면 정답을 근거로 X 를 준다
- **빈 답변에는 O 를 줬다** (closed_book_luna.md: 빈 답변 4건의 fact 10개 중 7개 O). 답변에 판단할 내용이 없으면 프롬프트의 정답(reference answer)을 보고 판정하는 것으로 보인다.
  실험·closed-book 경로 모두 빈 답변과 NOT FOUND 는 이제 judge 를 부르지 않는다
- **경계 사례는 흔들린다.** c0015 fact 1 ("create_access_token 으로 만든 서명된 JWT") 은 답변이 "signed, expiring JWT" 라고만 할 때 반복 실행마다 O/X 가 갈렸다 (baseline_dev_v2 재현성)
- 이 세트는 "분명히 틀린" 답만 담았다. 맞는 말을 다른 표현으로 한 답(FN 위험)이나, 핵심을 흐리게 말한 답(FP 위험)은 들어 있지 않다.
  그 판정은 gpt-6-luna 실제 답변의 사람 라벨(`judge_check_v3.csv`)로 확인한다
- 기대 판정은 만든 사람(Claude)이 정한 값이다. `human` 칸으로 사람 확인을 받으면 확정된다

## 다음

1. `judge_fp_set_v1.csv` 의 human 칸 확인 (45행, 기대 판정이 맞는지)
2. `judge_check_v3.csv` 사람 라벨 → `python src/judge_agreement.py docs/results/judge_check_v3.csv --judged docs/results/judge_check_v3_judged.csv`
   로 일치율·FP·FN·kappa 를 내고 qwen2.5:7b v2 (0.914, kappa 0.617) 와 비교
3. 필요하면 다음 세트에 경계 사례(부분 정답, 다른 표현, 흐린 답)를 추가
