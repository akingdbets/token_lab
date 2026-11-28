# 채점 버전 비교: fact_judge_v2 대 v3 (사람 라벨)

생성: `python src/judge_version_agreement.py docs/results/judge_check_test.csv` (2026-11-27T22:16:14)

- judge: deepseek-flash, per_fact, 응답 캐시 없이 v2·v3 각각 호출. 시트 80행 (human O/X).
- 프롬프트: v2 `7e441ad04bab`, v3 `5e7fe8303199`. 시트에 대안이 없어 v3 는 v2 와 같은 글자의 프롬프트를 보냈다.

| 버전 | 행 | 일치 | 일치율 | FP (사람 X, judge O) | FN (사람 O, judge X) | kappa | 못 읽음 |
|---|---|---|---|---|---|---|---|
| v2 | 80 | 69 | 0.863 | 1 | 10 | 0.721 | 0 |
| v3 | 80 | 68 | 0.850 | 2 | 10 | 0.694 | 0 |

v2 와 v3 판정이 같은 행: 77 / 80 (다른 행은 같은 프롬프트의 반복 호출 변동).

**판정 규칙(v3 가 v2 보다 낮지 않으면 v3) 결과: v2 사용 (v3 가 낮음).**

한계: 이 시트에는 accept_alternatives 가 없어, 대안 블록이 붙은 판정의 정확도는 재지 못했다. multiturn-v2 검수 때 대안이 있는 key_fact 행을 사람이 라벨링해 따로 확인한다.

judge 비용: $0.0588
