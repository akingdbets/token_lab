# 문서 중복도와 압축 강건성

> **정확도는 잠정치.** deepseek-flash 채점은 사람 라벨 검증 전이다 (`judge_check_v3.csv`). 중복도·상태 분류는 채점과 무관하다.

압축해도 정확도가 거의 안 떨어지는 이유가 **문서 중복성**인지 확인한다.
가설은 정답 핵심어가 문맥 여러 곳(설명 문장과 예제 코드)에 있어서, 압축이 근거 문장을 지워도 다른 곳에서 답을 찾는다는 것이다.
API 호출 없이 저장된 run 의 문맥과 trial 만 쓴다.

## 결론

- **줄 단위로 근거를 지우는 drop_evidence 에서는 가설이 맞다.**
  - 정답이 문맥 한 곳에만 있는 문항(중복도 1)의 정확도는 0.28 이고, 두 곳 이상인 문항(2+)은 0.82 다 (정답 문항 4/13 vs 18/22, Fisher p = 0.004).
  - 근거가 사라진 trial 만 보면 0.30 vs 0.88 이다 (p = 0.004).
  - 근거는 사라졌지만 핵심어가 코드에 남은 trial 은 13/13 이 맞혔다.
- **토큰 단위로 지우는 LLMLingua-2 에서는 중복도가 정확도를 가르지 않는다.**
  - 3회 반복 run 기준 중복도 1 vs 2+ 정확도: r50 1.000 vs 0.924, r30 0.949 vs 0.934, rule>llmlingua2 0.949 vs 0.953. 모두 p > 0.29 다.
  - 근거 인용문이 절반 넘게 지워진 trial 을 봐도 중복도 1 쪽이 낮지 않다.
  - 이유: LLMLingua-2 는 근거 문장을 통째로 지우지 않는다. 주변 단어만 지우고 **정답 토큰은 근거 자리에 남긴다** (아래 "evidence" 24 trial, 정확도 0.875).
  - 그래서 LLMLingua-2 의 강건성은 "문서 중복"보다 "핵심 토큰을 남기는 압축 방식" 때문이다.
- **중복도가 높아도 틀리는 경우:**
  - **c0020 (중복도 7, 모두 설명 문장):** r30 은 `request` 를 문맥 전체에서 지워 3/3 NOT FOUND 다.
  - **설명 문장에만 남은 trial:** 정확도 0.83, NOT FOUND 0.17 로, 코드에 남은 trial(0.90, 0)이나 둘 다 남은 trial(0.97, 0)보다 약하다.
- **유형별:**
  - code 유형은 LLMLingua-2 에서 중복도와 상관없이 1.00 이다. drop_evidence 에서는 중복도 1 이면 6문항 모두 틀린다 (0.00 vs 0.67).
  - fact 유형이 가장 흔들린다.

## 실행

```
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/20261031-143214 results/runs/20261031-162640 results/runs/20261031-172011
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/20261028-195811
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/20261019-231040
```

| 묶음 | run | 압축기 | trial |
|---|---|---|---|
| 3회 반복 (본문) | `20261031-143214`, `-162640`, `-172011` | none, rule, llmlingua2 r70/r50/r30, rule>llmlingua2 | 630 |
| PR #30 이전 (보조) | `20261028-195811` | 같음 | 210 |
| drop_evidence | `20261019-231040` | none, rule, rule_fm_all, empty, drop_evidence | 175 |

- `20261028-195811` 은 PR #28·#30(식별자 쪼개짐 수정) 이전 코드로 돈 run 이라 LLMLingua-2 문맥이 3회 반복 run 과 다르다. 그래서 합치지 않고 따로 낸다.
- 여러 run 을 합친 묶음은 같은 문항의 trial 이 독립이 아니다. 그 묶음의 p 는 참고값이다.
- 모두 dev 35문항이다.

## 방법

- **정답 핵심어 매칭:** `experiment.core_matches` 와 같다 (main 의 `normalized-v2`).
  - 위치를 모두 세도록 `find_normalized` 를 `iter_normalized`(모든 위치를 냄)로 나눴다. 판정 결과는 그대로다.
  - 요청서에는 normalized-v1 이라고 되어 있다. main 에는 v1 을 좁힌 v2(PR #36)가 들어가 있어 그것을 썼다.
- **중복도:** none 문맥에서 정답 핵심어가 나오는 위치 수다.
  - 짧은 답은 정답이 나오는 위치 수다.
  - 긴 답은 key_entities 마다 위치를 센 뒤, 절반 규칙(ceil(n/2) 개)을 채우는 k 번째로 많은 개체의 위치 수다.
  - 위치가 ``` 펜스 안이면 코드, 밖이면 설명 문장이다 (제목·목록·인라인 코드 포함).
- **근거 자리:** none 문맥에서 평가셋 `evidence[].quote` 가 가장 잘 맞는 구간이다. 점수는 `evidence_retention.quote_kept` 와 같다.
  - 압축 문맥의 위치는 none 문맥과 단어 정렬(difflib)로 맞춘다. 압축은 지우기만 하기 때문이다.
  - 정렬에서 빠진 단어(압축이 식별자를 쪼갠 경우)는 앞뒤의 가장 가까운 정렬된 단어로 판정한다.
- **trial 상태:** 근거 보존율은 `evidence_retention.item_retention` 으로 잰다. 경계는 `memory_suspect.EVIDENCE_LOW` = 0.5 다.
  - **a:** 근거 보존율 ≥ 0.5 (근거 인용문이 남음)
  - **b:** 근거 보존율 < 0.5 이고 핵심어 있음. 남은 위치는 근거 자리 밖에서만 센다.
    - code: 코드에만 남음
    - prose: 설명 문장에만 남음
    - both: 코드만으로도, 설명만으로도 채움
    - mixed: 둘을 합쳐야 채움
    - evidence: 근거 자리 밖에는 없음. 인용문 단어는 대부분 지워졌는데 정답 단어만 제자리에 남은 경우다.
  - **c:** 근거 보존율 < 0.5 이고 핵심어 없음
- **NOT FOUND:** 답변이 `NOT FOUND` 로 시작한다 (`experiment.is_not_found`).
- **검정:** 정답(accuracy ≥ 0.5) trial 수의 Fisher 정확 검정, 양측이다.

검증

- **중복도 1인 13문항:** none 에서 근거 자리 밖 위치가 모두 0 이다.
  - 압축 문맥에서도 근거 자리 밖으로 잡힌 경우가 없다 (b-다른위치 0건).
  - 단어 정렬을 넣기 전에는 LLMLingua-2 가 쪼갠 `WebSocket Disconnect` 등이 근거 밖으로 잘못 잡혔다. 지금은 고쳐졌다.
- **중복도 2+ 인 22문항:** 모두 근거 자리 밖 위치가 1 이상이다.
- **테스트:** `tests/test_redundancy.py` 13개를 추가했다 (4절 상태 판정 4개 포함). 전체 140개가 통과한다.

## 1. 문항별 중복도 (none 문맥)

| 중복도 | 문항 수 | 설명에만 | 코드에만 | 둘 다 | 근거 자리에만 있음 |
|---|---|---|---|---|---|
| 0 (none 에서도 못 찾음) | 0 | - | - | - | - |
| 1 | 13 | 5 | 7 | 1 | 13 |
| 2+ | 22 | 2 | 3 | 17 | 0 |

중복도 2 이상인 문항은 대부분(17/22) 정답이 **설명 문장과 예제 코드 양쪽**에 있다. 문서가 개념을 설명하고 같은 식별자를 코드로 다시 보여 주기 때문이다.

| qid | 유형 | 답 | 위치 수 | 설명 | 코드 | 근거 밖 |
|---|---|---|---|---|---|---|
| c0040 | multi | 긴 | 8 | 4 | 3 | 7 |
| c0020 | fact | 짧은 | 7 | 7 | 0 | 6 |
| c0032 | code | 짧은 | 5 | 2 | 3 | 4 |
| c0035 | fact | 짧은 | 5 | 2 | 3 | 4 |
| c0038 | procedure | 긴 | 5 | 4 | 1 | 4 |
| c0146 | procedure | 긴 | 5 | 2 | 3 | 4 |
| c0023 | code | 짧은 | 4 | 0 | 4 | 3 |
| c0024 | procedure | 긴 | 4 | 1 | 3 | 3 |
| c0033 | code | 짧은 | 4 | 3 | 1 | 3 |
| c0001 | fact | 짧은 | 3 | 1 | 2 | 2 |
| c0003 | procedure | 긴 | 3 | 1 | 2 | 2 |
| c0006 | procedure | 긴 | 3 | 1 | 2 | 3 |
| c0015 | multi | 긴 | 3 | 1 | 2 | 2 |
| c0019 | code | 짧은 | 3 | 1 | 2 | 1 |
| c0025 | fact | 짧은 | 3 | 2 | 1 | 2 |
| c0027 | code | 짧은 | 3 | 1 | 2 | 2 |
| c0028 | code | 짧은 | 3 | 1 | 2 | 2 |
| c0029 | procedure | 긴 | 3 | 1 | 2 | 2 |
| c0018 | fact | 짧은 | 2 | 2 | 0 | 1 |
| c0026 | fact | 짧은 | 2 | 1 | 1 | 1 |
| c0039 | multi | 긴 | 2 | 0 | 2 | 1 |
| c0145 | procedure | 긴 | 2 | 0 | 2 | 1 |
| c0002 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0004 | fact | 짧은 | 1 | 1 | 0 | 0 |
| c0005 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0017 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0021 | fact | 짧은 | 1 | 1 | 0 | 0 |
| c0022 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0030 | fact | 짧은 | 1 | 1 | 0 | 0 |
| c0031 | fact | 짧은 | 1 | 1 | 0 | 0 |
| c0034 | fact | 짧은 | 1 | 1 | 0 | 0 |
| c0036 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0037 | code | 짧은 | 1 | 0 | 1 | 0 |
| c0147 | procedure | 긴 | 1 | 0 | 1 | 0 |
| c0148 | multi | 긴 | 1 | 1 | 1 | 0 |

긴 답의 설명·코드 값은 그 위치만으로 k 번째 값을 다시 구한 것이라, 합이 위치 수와 다를 수 있다 (c0006, c0148).

## 2. trial 상태별

### 3회 반복 (630 trial)

| 압축기 | 상태 | trial | 문항 | 정확도 | NOT FOUND | b 남은 위치 code/prose/both/mixed/evidence |
|---|---|---|---|---|---|---|
| none | a | 105 | 35 | 0.986 | 0.000 | |
| rule | a | 105 | 35 | 0.986 | 0.000 | |
| llmlingua2_r70 | a | 105 | 35 | 0.980 | 0.000 | |
| llmlingua2_r50 | a | 81 | 27 | 0.951 | 0.037 | |
| llmlingua2_r50 | b | 18 | 6 | 0.944 | 0.000 | 6/0/6/0/6 |
| llmlingua2_r50 | c | 6 | 2 | 1.000 | 0.000 | |
| llmlingua2_r30 | a | 57 | 19 | 1.000 | 0.000 | |
| llmlingua2_r30 | b | 39 | 13 | 0.940 | 0.026 | 21/0/9/0/9 |
| llmlingua2_r30 | c | 9 | 3 | 0.556 | 0.333 | |
| rule>llmlingua2 | a | 75 | 25 | 0.990 | 0.000 | |
| rule>llmlingua2 | b | 24 | 8 | 0.819 | 0.125 | 3/6/6/0/9 |
| rule>llmlingua2 | c | 6 | 2 | 1.000 | 0.000 | |

b 상태의 남은 위치별 (세 압축기 합계)

| 남은 위치 | trial | 정확도 | NOT FOUND |
|---|---|---|---|
| code | 30 | 0.900 | 0.000 |
| prose | 6 | 0.833 | 0.167 |
| both | 21 | 0.968 | 0.000 |
| evidence (근거 자리에만) | 24 | 0.875 | 0.125 |

- **r70 은 모든 trial 이 a 다.** rule 도 근거 인용문을 지우지 않는다.
- **c 상태는 문항이 적다.**
  - r30 의 c 는 c0004, c0030, c0020 이다.
  - c0004 와 c0030 은 정답 문장의 단어가 일부 지워져 핵심어 매칭에는 안 걸린다 (`20261028-195811` 의 r50 에서는 "last added", "override signature" 로 남았다. tests/test_memory_suspect_v2.py 참고). 모델이 남은 단어로 맞힌다.
  - c0020 은 3/3 NOT FOUND 다.
- **rule>llmlingua2 의 b 정확도(0.819)가 낮은 이유:** c0018·c0020 처럼 다른 위치에 남은 trial 과, c0021 처럼 근거 자리에 정답 단어만 남은 trial 에서 틀리거나 NOT FOUND 가 나온다.

### drop_evidence run (`20261019-231040`, 175 trial)

| 압축기 | 상태 | trial | 문항 | 정확도 | NOT FOUND | b 남은 위치 code/prose/both/mixed/evidence |
|---|---|---|---|---|---|---|
| none | a | 35 | 35 | 1.000 | 0.000 | |
| rule | a | 35 | 35 | 0.986 | 0.000 | |
| rule_fm_all | a | 35 | 35 | 0.971 | 0.000 | |
| empty | c | 35 | 35 | 0.000 | 1.000 | |
| drop_evidence | a | 8 | 8 | 0.458 | 0.500 | |
| drop_evidence | b | 16 | 16 | 0.875 | 0.062 | 5/3/8/0/0 |
| drop_evidence | c | 11 | 11 | 0.364 | 0.545 | |

drop_evidence 의 b (16 trial)

| 남은 위치 | trial | 정확도 | NOT FOUND | 문항 |
|---|---|---|---|---|
| code | 5 | 1.000 | 0.000 | |
| both | 8 | 1.000 | 0.000 | |
| prose | 3 | 0.333 | 0.333 | c0019 맞힘, c0018 틀림, c0020 NOT FOUND |

- drop_evidence 는 근거 줄을 통째로 지운다. 그래서 b 의 "evidence" 가 0 이다 (근거 자리에 정답 단어가 남지 않음).
- **c 11 trial 중 10 이 중복도 1 문항이다.** 그중 맞힌 3문항(c0004, c0030, c0147)은 정답 문장이 없어도 남은 코드 예시에서 추론할 수 있다 (c0004 는 `add_middleware` 등록 순서와 실행 순서 예시, c0030 은 원래 함수와 override 함수의 시그니처).
- **drop_evidence 의 a 8 trial 은 정확도 0.458, NOT FOUND 0.5 로 이상하다.** 아래 "한계" 1번 참고.

### PR #30 이전 run (`20261028-195811`, 보조)

같은 경향이다.

- r30 의 c 는 5 trial, 정확도 0.40, NOT FOUND 0.60 이다.
- b 의 남은 위치별 정확도: code 0.90 (10), both 0.89 (6), evidence 1.00 (5), prose 0/1 (NOT FOUND).

## 3. 중복도 1 vs 2 이상

### 압축기별 정확도 (괄호는 같은 그룹 none 대비 차이)

| 묶음 | 압축기 | 중복도 1 (13문항) | 중복도 2+ (22문항) | 정답 trial 1 / 2+ | Fisher p |
|---|---|---|---|---|---|
| 3회 반복 | none | 1.000 | 0.977 | 39/39 / 66/66 | 1.000 |
| | rule | 1.000 (+0.000) | 0.977 (+0.000) | 39/39 / 66/66 | 1.000 |
| | llmlingua2_r70 | 1.000 (+0.000) | 0.968 (-0.009) | 39/39 / 66/66 | 1.000 |
| | llmlingua2_r50 | 1.000 (+0.000) | 0.924 (-0.053) | 39/39 / 63/66 | 0.293 |
| | llmlingua2_r30 | 0.949 (-0.051) | 0.934 (-0.043) | 37/39 / 63/66 | 1.000 |
| | rule>llmlingua2 | 0.949 (-0.051) | 0.953 (-0.024) | 37/39 / 65/66 | 0.554 |
| PR #30 이전 | llmlingua2_r50 | 1.000 (+0.000) | 0.936 (-0.064) | 13/13 / 20/22 | 0.519 |
| | llmlingua2_r30 | 0.846 (-0.154) | 0.932 (-0.068) | 11/13 / 21/22 | 0.541 |
| | rule>llmlingua2 | 0.923 (-0.077) | 0.894 (-0.106) | 12/13 / 21/22 | 1.000 |
| drop_evidence run | none | 1.000 | 1.000 | 13/13 / 22/22 | 1.000 |
| | rule | 1.000 (+0.000) | 0.977 (-0.023) | 13/13 / 22/22 | 1.000 |
| | rule_fm_all | 1.000 (+0.000) | 0.955 (-0.045) | 13/13 / 22/22 | 1.000 |
| | empty | 0.000 (-1.000) | 0.000 (-1.000) | 0/13 / 0/22 | 1.000 |
| | **drop_evidence** | **0.282 (-0.718)** | **0.818 (-0.182)** | **4/13 / 18/22** | **0.004** |

### 근거가 사라진 trial (b + c) 만

| 묶음 | 압축기 | 중복도 1 정확도 (trial) | 중복도 2+ 정확도 (trial) | Fisher p |
|---|---|---|---|---|
| 3회 반복 | llmlingua2_r50 | 1.000 (12) | 0.917 (12) | 1.000 |
| | llmlingua2_r30 | 0.867 (15) | 0.869 (33) | 0.642 |
| | rule>llmlingua2 | 0.867 (15) | 0.844 (15) | 1.000 |
| drop_evidence run | drop_evidence | 0.300 (10) | 0.882 (17) | 0.004 |

3회 반복에서 근거가 사라진 trial 을 남은 위치까지 나누면 아래와 같다.

| 압축기 | 중복도 1 | 중복도 2+ |
|---|---|---|
| llmlingua2_r50 | 근거 자리에만 6 (1.000), c 6 (1.000) | 다른 위치 12 (0.917) |
| llmlingua2_r30 | 근거 자리에만 9 (0.889), c 6 (0.833) | 다른 위치 30 (0.956), c 3 (0.000, c0020) |
| rule>llmlingua2 | 근거 자리에만 9 (0.778), c 6 (1.000) | 다른 위치 15 (0.844) |

LLMLingua-2 에서 중복도 1 문항이 버티는 것은 정답 단어가 근거 자리에 남거나, 남은 단어로 추론할 수 있어서다 (c 의 c0004·c0030). 정답이 다른 위치에 있어서가 아니다.

### 유형별 (칸 = 중복도 1 / 2+ 정확도)

3회 반복

| 유형 | 문항 (1 / 2+) | none | rule | r70 | r50 | r30 | rule>llmlingua2 |
|---|---|---|---|---|---|---|---|
| code | 6 / 6 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| fact | 5 / 6 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.83 | 0.87 / 0.83 | 0.87 / 0.94 |
| multi | 1 / 3 | 1.00 / 0.94 | 1.00 / 0.89 | 1.00 / 1.00 | 1.00 / 0.89 | 1.00 / 1.00 | 1.00 / 0.94 |
| procedure | 1 / 7 | 1.00 / 0.95 | 1.00 / 0.98 | 1.00 / 0.90 | 1.00 / 0.95 | 1.00 / 0.94 | 1.00 / 0.92 |

drop_evidence run

| 유형 | 문항 (1 / 2+) | none | rule | rule_fm_all | empty | drop_evidence |
|---|---|---|---|---|---|---|
| code | 6 / 6 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / 0.00 | **0.00 / 0.67** |
| fact | 5 / 6 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / 0.00 | 0.40 / 0.67 |
| multi | 1 / 3 | 1.00 / 1.00 | 1.00 / 0.83 | 1.00 / 0.83 | 0.00 / 0.00 | 0.67 / 1.00 |
| procedure | 1 / 7 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.93 | 0.00 / 0.00 | 1.00 / 1.00 |

- **code 유형:** 중복도 1 이면 정답 식별자가 근거 코드 한 줄에만 있다. drop_evidence 가 그 줄을 지우면 6문항 모두 틀린다. LLMLingua-2 에서는 r30 까지 모두 1.00 이다. 근거가 사라진 trial 에서도 남은 위치가 대부분 코드다 (r30 b 의 code 21/39).
- **multi·procedure:** 중복도 1 이 각 1문항뿐이라 비교가 어렵다.

## 4. 근거 자리 안의 정답 핵심어로 다시 본 상태

위 결론은 "LLMLingua-2 에서는 정답 단어가 대부분 제자리에 남아서 중복성이 쓰일 일이 적었다"는 설명이다. 이 설명을 숫자로 확인한다.

2절의 상태 a 는 "근거 보존율 ≥ 0.5" 였는데, 이 기준은 한 줄짜리 코드 인용문에서 보존율을 과대평가한다 (한계 1). 그래서 이번에는 **근거 인용문 범위 안에 정답 핵심어가 남았는가**로 다시 나눈다.

```
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/20261031-143214 results/runs/20261031-162640 results/runs/20261031-172011 --compressors "llmlingua2_r50,llmlingua2_r30,rule>llmlingua2" --core-states
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/20261019-231040 --compressors drop_evidence --core-states
```

- **A:** 근거 인용문 자리(none 문맥과 단어 정렬해 찾은 구간) 안에 정답 핵심어가 남음. 긴 답은 근거 자리 안의 위치만으로 절반 규칙을 채워야 한다.
- **B:** 근거 자리에는 없지만 다른 위치에 남음. 남은 위치에 따라 code / prose / both 로 나누고, 근거 자리와 다른 위치를 합쳐야 절반 규칙을 채우면 mixed 다.
- **C:** 정답 핵심어가 문맥 전체에서 사라짐 (`core_matches` 가 거짓).
- 매칭은 normalized-v2 그대로다.

### 상태별 (LLMLingua-2 는 3회 반복 105 trial, drop_evidence 는 1회 35 trial)

| 압축기 | 상태 | trial | 비율 | 정확도 | NOT FOUND |
|---|---|---|---|---|---|
| llmlingua2_r50 | A | 96 | 91.4% | 0.948 | 0.031 |
| | B (both 3) | 3 | 2.9% | 1.000 | 0.000 |
| | C | 6 | 5.7% | 1.000 | 0.000 |
| llmlingua2_r30 | A | 78 | 74.3% | 0.970 | 0.013 |
| | B (code 12, both 3, mixed 3) | 18 | 17.1% | 1.000 | 0.000 |
| | C | 9 | 8.6% | 0.556 | 0.333 |
| rule>llmlingua2 | A | 99 | 94.3% | 0.949 | 0.030 |
| | B | 0 | 0.0% | - | - |
| | C | 6 | 5.7% | 1.000 | 0.000 |
| drop_evidence | A | 0 | 0.0% | - | - |
| | B-code | 5 | 14.3% | 1.000 | 0.000 |
| | B-prose | 4 | 11.4% | 0.500 | 0.250 |
| | B-both | 10 | 28.6% | 0.900 | 0.100 |
| | C | 16 | 45.7% | 0.354 | 0.562 |

- **LLMLingua-2 는 trial 의 74~94% 에서 정답 단어를 근거 자리에 남긴다.** 다른 위치가 쓰인 B 는 r30 에서만 의미 있는 수(18 trial, 6문항)이고, 모두 맞혔다.
  - B 문항: c0003, c0025, c0026, c0038 (code), c0040 (both), c0148 (mixed). r50 의 B 는 c0040 3 trial 뿐이다.
- **drop_evidence 는 근거 줄을 지우므로 A 가 0 이다.** 절반 이상(19/35)이 B 로 다른 위치에 기대고, 그중 16 trial 이 맞았다.
  - 틀린 3 trial 중 c0018·c0020 은 정답이 설명 문장에만 남은 경우이고, c0027 은 both 다.
- **2절 a 와의 차이:**
  - drop_evidence 에서 2절 a 로 잡혔던 8 trial 은 여기서 B 나 C 로 간다. 근거 보존율이 0.5 이상이었던 c0002·c0017·c0023 은 C 다 (모두 NOT FOUND).
  - LLMLingua-2 에서는 2절 b-evidence(근거 자리에만 남음)로 잡혔던 trial 이 A 로 들어간다.

### 상태 C 전체

LLMLingua-2 (21 trial)

| qid | 유형 | 압축기 | run | 정답 | 모델 답변 앞부분 | 정확도 |
|---|---|---|---|---|---|---|
| c0004 | fact | llmlingua2_r30 | 20261031-143214 | The last one added | The first middleware added. | 0.00 |
| c0004 | fact | llmlingua2_r30 | 20261031-162640 | The last one added | The last middleware added wraps all the others. | 1.00 |
| c0004 | fact | llmlingua2_r30 | 20261031-172011 | The last one added | The last middleware added wraps all the others. | 1.00 |
| c0020 | fact | llmlingua2_r30 | 20261031-143214 | "request" | NOT FOUND | 0.00 |
| c0020 | fact | llmlingua2_r30 | 20261031-162640 | "request" | NOT FOUND | 0.00 |
| c0020 | fact | llmlingua2_r30 | 20261031-172011 | "request" | NOT FOUND | 0.00 |
| c0030 | fact | llmlingua2_r30 | 20261031-143214 | The override's own signature | The parameters declared by the override dependency. | 1.00 |
| c0030 | fact | llmlingua2_r30 | 20261031-162640 | The override's own signature | The parameters declared by the override dependency. | 1.00 |
| c0030 | fact | llmlingua2_r30 | 20261031-172011 | The override's own signature | The parameters declared by the override dependency. | 1.00 |
| c0004 | fact | llmlingua2_r50 | 20261031-143214 | The last one added | The last middleware added. | 1.00 |
| c0004 | fact | llmlingua2_r50 | 20261031-162640 | The last one added | The last middleware added. | 1.00 |
| c0004 | fact | llmlingua2_r50 | 20261031-172011 | The last one added | The last middleware added (outermost). | 1.00 |
| c0030 | fact | llmlingua2_r50 | 20261031-143214 | The override's own signature | The override callable's signature. | 1.00 |
| c0030 | fact | llmlingua2_r50 | 20261031-162640 | The override's own signature | The override callable's signature. | 1.00 |
| c0030 | fact | llmlingua2_r50 | 20261031-172011 | The override's own signature | The override callable's signature. | 1.00 |
| c0004 | fact | rule>llmlingua2 | 20261031-143214 | The last one added | The last middleware added wraps all the others. | 1.00 |
| c0004 | fact | rule>llmlingua2 | 20261031-162640 | The last one added | The last middleware added. | 1.00 |
| c0004 | fact | rule>llmlingua2 | 20261031-172011 | The last one added | The last middleware registered. | 1.00 |
| c0030 | fact | rule>llmlingua2 | 20261031-143214 | The override's own signature | The override callable's signature. | 1.00 |
| c0030 | fact | rule>llmlingua2 | 20261031-162640 | The override's own signature | The override callable's signature. | 1.00 |
| c0030 | fact | rule>llmlingua2 | 20261031-172011 | The override's own signature | The override callable's signature. | 1.00 |

압축은 결정적이라 세 run 의 문맥이 같다. 문맥을 직접 보면 C 의 성격이 압축기마다 다르다.

| 압축기 | 문항 | 근거 자리의 압축 후 문맥 | 판단 |
|---|---|---|---|
| r50 | c0004 | `middleware wraps app built last added outermost` | 표기상 C. "one" 만 빠지고 정답 단어가 제자리에 있다 |
| r50 | c0030 | `override signature defines request parameters` | 표기상 C. "'s own" 만 빠졌다 |
| rule>llmlingua2 | c0004 | `middleware wraps app outermost` | 일부 삭제. "last added" 는 지워졌고 "outermost" 가 같은 뜻을 남긴다 |
| rule>llmlingua2 | c0030 | `signature defines request parameters` | 일부 삭제. "override" 가 지워졌다 |
| r30 | c0004 | (last·added·outermost 모두 없음) | 실제 삭제. 2/3 맞힘 (남은 `add_middleware` 코드 순서로 추론하거나 기억으로 답한 것으로 보임) |
| r30 | c0030 | (signature 없음, `override_dependency(q)` 코드만 남음) | 실제 삭제. 코드로 추론해 3/3 맞힘 |
| r30 | c0020 | (`request` 가 문맥 전체에서 없음) | 실제 삭제. 3/3 NOT FOUND |

drop_evidence (16 trial)

| qid | 유형 | 정답 | 모델 답변 앞부분 | 정확도 |
|---|---|---|---|---|
| c0002 | code | 15 | NOT FOUND | 0.00 |
| c0004 | fact | The last one added | The last middleware registered wraps all the others. | 1.00 |
| c0005 | code | 5 | NOT FOUND | 0.00 |
| c0017 | code | 30 | NOT FOUND | 0.00 |
| c0021 | fact | DependencyScopeError | NOT FOUND | 0.00 |
| c0022 | code | 400 | 404 | 0.00 |
| c0023 | code | Rick | NOT FOUND | 0.00 |
| c0030 | fact | The override's own signature | The replacement dependency's parameters. | 1.00 |
| c0031 | fact | WebSocketDisconnect | NOT FOUND | 0.00 |
| c0034 | fact | OAuth2PasswordRequestFormStrict | NOT FOUND | 0.00 |
| c0036 | code | fakehashed | NOT FOUND | 0.00 |
| c0037 | code | {"token": token} | NOT FOUND | 0.00 |
| c0039 | multi | The simple version returns 400 Incorrect username or passwor… | In the simple password-flow tutorial, wrong credentials at `/token` re… | 1.00 |
| c0145 | procedure | 1) Create the client in a with block: with TestClient(app) a… | 1. Define the app's lifespan logic, including startup work before `yie… | 1.00 |
| c0147 | procedure | 1) Declare the yield dependency with Depends(get_username, s… | 1. Set the dependency's `scope` to `"function"` in `Depends()`. 2. Its… | 1.00 |
| c0148 | multi | A module-level client = TestClient(app) used without a with … | Using `TestClient(app)` without a `with` context manager does not run … | 0.67 |

(모두 run `20261019-231040`)

### 상태 A 인데 틀림 (accuracy < 0.5, LLMLingua-2 7 trial, drop_evidence 0)

압축 후 문맥은 none 과 단어 정렬해서, 인용문 자리에 대응하는 압축 문맥 구간을 그대로 옮겼다.

| qid | 압축기 | run | 정답 | 답변 | 인용문 원문 | 압축 후 같은 부분 |
|---|---|---|---|---|---|---|
| c0020 | r50 | 143214, 162640, 172011 (3/3) | `"request"` | NOT FOUND | - `"request"` (default for `yield` dependencies): setup before the path operation, teardown **after the response is sent**. This means a `StreamingResponse` can keep using the resource while streaming. | request default setup before path operation teardown after response sent StreamingResponse resource while streaming |
| c0020 | rule>llmlingua2 | 172011 (1/3) | `"request"` | NOT FOUND | (같음) | request default setup before path operation teardown after response StreamingResponse resource streaming |
| c0021 | rule>llmlingua2 | 143214, 172011 (2/3) | DependencyScopeError | NOT FOUND | Sub-dependency rule: a `"request"`-scoped dependency may only depend on `"request"`-scoped dependencies; a `"function"`-scoped dependency may depend on both. Violating it raises `DependencyScopeError` when the route is created. … | only DependencyScopeError route createdHistory edge cases Advanced Dependencies |
| c0031 | r30 | 143214 (1/3) | WebSocketDisconnect | NOT FOUND | … If the server closes or rejects the connection (e.g. `WebSocketException` with code 1008), the test client raises `WebSocketDisconnect`, which you can assert with `pytest.raises` … | send_text send_bytes send_json receive_text receive_bytes receive_json URL WebSocketException 1008 WebSocketDisconnect WebSockets |

**7 trial 모두 정답 단어는 남았지만, 그 단어와 질문을 잇는 말이 지워졌다.**

- **c0020:** `for yield dependencies` 의 `yield` 와 괄호 구조가 빠졌다. 그래서 `request` 가 무엇의 기본값인지 이어지지 않는다.
- **c0021:** `Violating it raises … when` 이 빠졌다. `DependencyScopeError` 가 규칙 위반의 결과라는 관계가 사라졌다.
- **c0031:** `If the server closes … the test client raises` 가 빠지고 식별자 나열만 남았다.

같은 압축 문맥에서도 run 에 따라 맞히기도 한다 (c0021 1/3, c0031 2/3, rule>llmlingua2 c0020 2/3 맞힘). 연결어가 지워지면 답변이 경계에 놓여 흔들리는 것으로 보인다.

### 요약

- **정답 단어가 실제로 지워진 비율 (C):** 매칭 기준으로 r50 5.7%, r30 8.6%, rule>llmlingua2 5.7%, drop_evidence 45.7% 다. 문맥을 읽어 보면 r50 의 C 6건은 단어가 제자리에 있는 표기상 C 라 실제 삭제는 0% 다. rule>llmlingua2 는 일부 삭제 6건(5.7%), r30 은 실제 삭제 9건(8.6%)이다.
- **B 에서 중복성이 정답을 지켜 준 건수:** LLMLingua-2 21/21 trial (r30 18, r50 3, rule>llmlingua2 0) 이다. 전체 315 trial 의 6.7% 다. drop_evidence 는 16/19 trial (35 trial 중 46%) 이다.
- **A 인데 틀린 건수:** LLMLingua-2 7 trial (c0020 4, c0021 2, c0031 1). 7건 모두 정답 단어는 남고 연결어가 지워진 경우로 보인다. drop_evidence 는 A 가 없다.

"정답 단어가 대부분 제자리에 남아서 중복성이 쓰일 일이 적었다"는 설명은 숫자로 맞다. LLMLingua-2 의 틀린 답은 정답 단어 삭제(r30 c0020 3건)보다 **연결어 삭제**(7건)에서 더 많이 나온다.

## 한계

1. **근거 보존율(v2)은 짧은 코드 인용문에서 과대평가된다.**
   - drop_evidence 의 a 8 trial 중 4건(c0002 0.625, c0017 0.5, c0023 0.5, c0027 0.857)은 인용문 줄이 지워졌다. 그런데도 비슷한 코드 줄(같은 import, 같은 함수 시그니처)의 단어로 부분 점수를 받았다. 4건 모두 NOT FOUND 다.
   - 그래서 drop_evidence 의 a 정확도 0.458 은 "근거가 남았는데 틀림"이 아니다. 근거가 지워졌는데 a 로 잘못 분류된 것이다.
   - 이 4건을 c 로 옮겨도 결론은 그대로다 (c0002·c0017 은 중복도 1, c0023·c0027 은 2+).
2. **중복도는 정답 표기가 그대로 나오는 위치만 센다.**
   - c0004 처럼 코드의 등록 순서로 같은 사실을 보여 주는 경우는 세지 않는다. 그래서 의미상 중복은 과소평가된다.
3. **표본이 작다.**
   - dev 35문항(1: 13, 2+: 22)이다. LLMLingua-2 에서 틀린 trial 은 압축기마다 2~3건이라, 차이가 없다는 결론도 검정력이 낮다.
   - 3회 반복을 합친 p 는 같은 문항의 반복이라 독립 가정이 맞지 않는다.
4. **NOT FOUND 와 정확도는 trial 단위이고, 모델 답변은 run 마다 다르다** (temp 0 에서도 86/210 쌍이 다름).

## 파일

- `src/redundancy.py`: 분석 스크립트. `--json` 으로 문항·trial 값을 쓴다. `--core-states` 는 4절 표와 목록을, `--compressors` 는 압축기 필터를 낸다.
- `src/experiment.py`: `iter_normalized` 를 추가했다 (모든 위치). `find_normalized` 는 그 첫 위치를 쓰며, 판정은 그대로다.
- `tests/test_redundancy.py`: 위치 세기, 코드/설명 구분, 근거 자리, 상태 분류, Fisher 검정.
