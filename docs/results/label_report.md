# 사람 라벨 집계

`python src/label_report.py` 로 만든다 (2026-11-04 17:49). 라벨 기준은 [labeling_guide.md](labeling_guide.md). 1~6절은 스크립트가 만들고, 아래 수기 구간은 사람이 쓴다.

<!-- 수기 시작: label_report.py 를 다시 돌려도 이 사이는 그대로 둔다 -->

## 요약 (2026-11-04, 사람 분류 50/50)

대상은 test_v1 의 압축 오답 50 trial 이다 (r50·r30·rule>llmlingua2, accuracy < 0.5). 사람 분류 기준은 [labeling_guide.md](labeling_guide.md) 2절이다.

- **절반 넘게 정보 손실이다.** 정답 구절 삭제(1)가 28 (56%), 해석 손실(2 연결어·조건 10, 3 표기 분해 2, 4 정답 남음 8)이 20, 기타(5)가 2 다.
  - 정보 손실은 r30 에 몰린다 (31 중 21). r50 은 8 중 4 가 "정답 남음·추론 가능한데 틀림"(4)이다.
- **자동 분류(A/B/C)와 77% 일치한다 (37/48).** 사람 1 ↔ 자동 C, 사람 2·3·4 ↔ 자동 A·B 로 맞대어 셌다.
  - 사람 1 인데 자동 A·B 인 7: 정답 핵심어는 남았지만 답에 필요한 다른 값이 지워졌거나, 같은 문자열이 다른 위치에만 남은 경우다.
  - 사람 2·4 인데 자동 C 인 4: 자동 분류는 짧은 정답을 문자열 전체로 찾아서, 표기가 조금만 달라도 C 가 된다 (c0012 r50 은 원문에서도 매칭되지 않는 행).
- **생각 켬에서 해석 손실은 75% 회복되고, 정보 손실은 21~25% 회복된다.**

  | 설정 | 정보 손실 (1) | 해석 손실 (2+3+4) | Fisher p |
  |---|---|---|---|
  | (1) 생각 끔·T0 재실행 | 2/28 (7%) | 3/20 (15%) | 0.636 |
  | (2) 서버 기본값 [생각 켬] | 7/28 (25%) | 15/20 (75%) | 0.001 |
  | (3) temperature 만 기본, 3회 평균 | 2.7/28 (10%) | 4/20 (20%) | - |
  | luna (기본) [생각 켬] | 6/28 (21%) | 15/20 (75%) | < 0.001 |

  - 생각을 끈 (1)·(3) 에서는 두 쪽 모두 7~20% 로 낮다. 생각 기능이 주로 해석 손실을 되돌린다.
  - 4 "정답 남음·추론 가능한데 틀림" 은 생각 켬에서 8 중 7~8 이 회복된다. 압축 손실이 아니라 생각 끔 설정의 오답이었다.
- **[사후] 기억 가능성으로 나누면, 차이는 기억 가능 문항에서만 보인다.** 기억 가능성은 luna 가 closed-book 에서 맞힌 문항이다 ([closed_book_luna.md](closed_book_luna.md) 판정 A, test_v1_default.md 8절과 같은 기준).

  | 층 | 설정 | 정보 손실 (1) | 해석 손실 (2+3+4) | Fisher p |
  |---|---|---|---|---|
  | 기억 가능 (문항 23) | (2) 서버 기본값 | 3/20 | 11/12 | < 0.001 |
  | 기억 가능 | luna (기본) | 2/20 | 10/12 | < 0.001 |
  | 기억 불가능 (문항 12) | (2) 서버 기본값 | 4/8 | 4/8 | 1.000 |
  | 기억 불가능 | luna (기본) | 4/8 | 5/8 | 1.000 |

  - 기억 불가능 층은 16 trial 뿐이라 차이가 없다고도, 있다고도 말할 수 없다.
  - 기억 가능 문항이어도 정답 구절이 지워지면 회복이 드물다 (3/20). 모델이 기억으로 빈칸을 메우기보다 NOT FOUND 를 낸다.
  - 정보 손실인데 회복된 7 중 2 (c0150 r30, c0174 rule>llmlingua2) 는 multi 문항의 부분 점수(0.5)다.

## 요약: judge 검증과 민감도 분석 (2026-11-04, 사람 라벨 80/80)

judge(deepseek-flash, fact_judge_v2 per_fact)의 key_fact 판정을 사람 라벨과 비교했다. 표는 5절, 보정은 6절이다.

- **일치율 0.863 (69/80), Cohen's κ 0.725.** 어긋난 11 행은 모두 FN(judge X·사람 O)이다. FP(judge O·사람 X)는 0 이다.
  - judge O 행 40: 사람도 40 모두 O 다. judge 가 맞다고 하면 믿어도 된다.
  - judge X 행 40: 사람 O 가 **11 (27.5%)** 이다. judge 는 엄격한 쪽으로 틀린다.
- **FN 은 multi·procedure 에 몰린다.** fact 22 행은 모두 일치하고, multi 6·procedure 4·code 1 이 FN 이다. 부분 점수 문항(사실이 여럿)의 κ 는 0.483 으로 낮다. 긴 답에서 사실 하나를 찾는 판정이 약하다.
- 담당자별 일치율은 0.80~0.95 다 (A 0.90, B 0.95, C 0.80, D 0.80).
- **판정 비율은 11/40 이다.** 요청에 적힌 13/40 과 다르다. 이번에 받은 80 행 기준으로는 judge X 40 행 중 사람 O 가 11 이다. 6절은 11/40, 13/40, 상한 1/1(judge X 가 전부 틀렸다고 가정) 세 가지를 모두 계산했다.
- **보정해도 "rule 만 유지" 결론은 바뀌지 않는다.**

  | 조건 (luna 기본) | 유지율 보정 전 | p = 11/40 | p = 13/40 | p = 1 (상한) | 판단 |
  |---|---|---|---|---|---|
  | rule | 101.2% [99.9, 102.7] | 100.8% [100.0, 101.9] | 100.8% [100.0, 101.8] | 100.0% | 유지 |
  | llmlingua2_r50 | 93.0% [88.1, 97.5] | 93.3% [88.7, 97.4] | 93.4% [88.8, 97.4] | 94.2% [89.9, 97.8] | 손실 |
  | llmlingua2_r30 | 81.8% [75.2, 87.8] | 82.8% [76.5, 88.6] | 83.0% [76.7, 88.8] | 85.5% [79.0, 91.3] | 손실 |
  | rule>llmlingua2 | 93.9% [89.3, 97.9] | 94.6% [90.5, 98.0] | 94.7% [90.7, 98.1] | 96.4% [92.7, 99.3] | 손실 |

  - 보정은 none 정확도도 같이 올린다 (0.981 → 0.986). 그래서 유지율은 1%p 남짓만 오른다.
  - LLMLingua-2 의 손실은 대부분 judge 를 거치지 않은 NOT FOUND·빈 답이다. judge X 를 모두 O 로 바꾼 상한에서도 r50 5.8%p, r30 14.5%p, rule>llmlingua2 3.6%p 가 남고, 유지율 CI 하한이 95% 에 못 미친다.
  - 시뮬레이션 500 표본에서도 판단이 한 번도 바뀌지 않았다 (rule 유지 100%, 나머지 유지 0%).
- **정확도 수치는 잠정치를 벗어난다.** p = 11/40 기준으로 judge 는 정확도를 조건에 따라 0.2~1.4%p 낮게 잰다 (none +0.5, rule +0.2, r50 +0.9, r30 +1.4, rule>llmlingua2 +1.1). 조건 간 비교와 사전 기준 판단에는 영향이 없다.
- **메모 2건과의 관계**
  - c0092 (T073): 사람 라벨도 X 다. "send headers" 는 "set custom headers" 와 다르다고 봤다. 오답 검수 메모의 "채점 오류 의심" 과 엇갈리므로, 이 문항은 judge 오류가 아닌 경계 사례로 둔다.
  - c0085 (T068): 사람은 O(FN)로 봤다 ("NOT FOUND 확인 필요" 메모). 아래 c0085 절의 "지금 규칙으로는 오답" 해석과 다르다. 답 뒤에 붙은 NOT FOUND 를 모순으로 볼지는 팀이 정할 일이다.

## 메모 확인 2건

### c0092 rule>llmlingua2: 채점 오류 의심 → judge 판정이 흔들리는 경계 사례

- key_fact 는 "Browsers cannot set custom headers on WebSocket connections." 다. 답은 "Browsers can't send headers in WebSocket connections." 다. per_fact judge 는 **False** 로 판정했다.
- 예전 YES/NO judge(`grade`)는 같은 답에 YES 를 줬다. 사람도 사실상 정답으로 봤다. 엄밀히는 "custom" 이 빠졌다. 브라우저는 표준 헤더는 보내므로 "헤더를 못 보낸다" 는 덜 정확하다.
- **같은 답 문자열이 5 번 채점됐고, 1 번만 True 다.** test_v1, (1), (3) 2회차, terra (기본) 는 False 다. (2) 서버 기본값만 True 다. judge 입력(질문·정답·사실·답)이 같고 temperature 0 인데도 판정이 바뀌었다.
  - 따라서 **reasoning_probe (2) 의 c0092 "회복" 은 답이 바뀐 것이 아니라 채점이 바뀐 것이다.** (2) 회복 24 중 1 은 채점 변동이다.
  - luna (기본) 의 회복은 답 문장이 다르다 ("…, so tokens are passed as a query parameter or a cookie."). 다만 같은 "send headers" 표현이라 이것도 경계 사례다.
- per_fact judge 는 판정 이유를 저장하지 않는다 (`fact_results` 는 fact 와 true/false 만 남긴다). 그래서 judge 가 왜 False 를 줬는지는 보여 줄 수 없다.
- 채점 프롬프트(fact_judge_v2)는 고치지 않았다. 이 문항은 judge 검증 세트(`judge_check_test.csv`)의 사람 라벨로 FN 비율을 보는 근거로 쓸 수 있다.

### c0085 rule>llmlingua2: 답 뒤에 NOT FOUND → 주 지표에서는 오답, NOT FOUND 집계에서는 빠짐

답은 `found query: {q} NOT FOUND` 다. 코드에서 이 답이 거친 경로는 이렇다.

| 단계 | 함수 | 규칙 | 결과 |
|---|---|---|---|
| NOT FOUND 집계 | `experiment.is_not_found` | 답이 `NOT FOUND` 로 **시작**하나 | False → `not_found` False |
| judge 생략 여부 | `grader.is_not_found_answer` | 답 전체가 `NOT FOUND` **뿐**인가 (fullmatch) | False → judge 를 부름 |
| 주 지표 | fact_judge_v2, per_fact | 사실 "get_query logs the message "found query: {q}"." | **False** → answer_accuracy 0.0 |
| 예전 채점 | `grader.grade` | 짧은 정답이라 문자열 일치 | correct True (보조 기록) |

- 즉 **NOT FOUND 비율에는 들어가지 않고, 정확도에서는 오답이다.** judge 는 같은 답을 test_v1·(1)·(3) 1회차에서 세 번 모두 False 로 봤다. 판정은 일관된다.
- 답에 정답이 들어 있으니 judge 가 너무 엄격하다고 볼 수도 있다. 반대로 "찾았다" 와 "못 찾았다" 를 함께 말한 답이니 오답이 맞다고 볼 수도 있다. 지금 규칙("사실과 모순되면 X")으로는 후자다.
- **이 형식은 드물다.** test_v1 973 trial 중 답 중간이나 끝에 `NOT FOUND` 가 있는 답은 7 개다. 나머지 6 개(c0063·c0091·c0170 ×3·c0174)는 여러 부분을 묻는 문항에서 못 찾은 부분을 NOT FOUND 로 표시한 것이다. 한 줄 정답 바로 뒤에 붙은 것은 c0085 하나다. 생각 켬((2)·luna 기본)에서는 사라졌고, (3) 에서는 3회 중 1회 다시 나왔다.
- 채점 규칙은 고치지 않았다. 바꾼다면 `is_not_found` 를 "NOT FOUND 를 포함하나" 로 넓혀 집계에서 따로 세는 정도가 후보다. 주 지표에는 영향이 없다.


<!-- 수기 끝 -->

## 1. 오답 분류 (`test_error_review.csv`)

사람 분류가 채워진 행: **50 / 50** (빈 행 0 은 뺐다)

### 사람 분류별 건수 (압축기별)

| 사람 분류 | llmlingua2_r50 | llmlingua2_r30 | rule>llmlingua2 | 합 |
|---|---|---|---|---|
| 1 정답 구절 삭제 | 3 | 21 | 4 | 28 |
| 2 연결어·조건 삭제 | 1 | 7 | 2 | 10 |
| 3 표기 분해 | 0 | 1 | 1 | 2 |
| 4 정답 남음·추론 가능한데 틀림 | 4 | 2 | 2 | 8 |
| 5 기타 | 0 | 0 | 2 | 2 |
| 합 | 8 | 31 | 11 | 50 |

### 사람 분류별 건수 (유형별)

| 사람 분류 | fact | code | procedure | multi | 합 |
|---|---|---|---|---|---|
| 1 정답 구절 삭제 | 18 | 0 | 1 | 9 | 28 |
| 2 연결어·조건 삭제 | 7 | 0 | 1 | 2 | 10 |
| 3 표기 분해 | 2 | 0 | 0 | 0 | 2 |
| 4 정답 남음·추론 가능한데 틀림 | 5 | 0 | 1 | 2 | 8 |
| 5 기타 | 1 | 1 | 0 | 0 | 2 |
| 합 | 33 | 1 | 3 | 13 | 50 |

### 사람 분류별 문항 수

trial 은 (문항, 압축기) 쌍이다. 문항은 35 개다. 한 문항이 압축기마다 다른 분류를 받으면 각 분류에 한 번씩 센다.

| 사람 분류 | trial | 문항 |
|---|---|---|
| 1 정답 구절 삭제 | 28 | 21 |
| 2 연결어·조건 삭제 | 10 | 9 |
| 3 표기 분해 | 2 | 1 |
| 4 정답 남음·추론 가능한데 틀림 | 8 | 8 |
| 5 기타 | 2 | 2 |

압축기마다 분류가 다른 문항 6 개: c0012 (llmlingua2_r50 2, llmlingua2_r30 1), c0070 (llmlingua2_r30 2, rule>llmlingua2 4), c0078 (llmlingua2_r30 1, rule>llmlingua2 4), c0086 (llmlingua2_r50 4, llmlingua2_r30 1, rule>llmlingua2 1), c0092 (llmlingua2_r30 1, rule>llmlingua2 5), c0150 (llmlingua2_r50 4, llmlingua2_r30 1)

## 2. 자동 분류(A/B/C)와의 교차표

자동 분류: A 근거 자리에 정답 핵심어 남음 / B 다른 위치에만 남음 / C 매칭 안 됨 (normalized-v2).

| 사람 분류 \ 자동 | A | B | C | 합 |
|---|---|---|---|---|
| 1 정답 구절 삭제 | 3 | 4 | 21 | 28 |
| 2 연결어·조건 삭제 | 7 | 0 | 3 | 10 |
| 3 표기 분해 | 2 | 0 | 0 | 2 |
| 4 정답 남음·추론 가능한데 틀림 | 7 | 0 | 1 | 8 |
| 5 기타 | 1 | 0 | 1 | 2 |

**일치율.** 자동 분류는 정답 문자열이 압축 문맥에 남았는지만 본다. 그래서 사람 1(정답 구절 삭제)은 자동 C 와, 사람 2·3·4(정답은 남음)는 자동 A·B 와 맞대어 센다. 사람 5(기타)는 뺀다.

- 일치: **37/48 (77%)**
- 사람 1 중 자동 C: 21/28 (75%)
- 사람 2·3·4 중 자동 A·B: 16/20 (80%)

어긋난 trial:

| qid | 압축기 | 사람 | 자동 |
|---|---|---|---|
| c0012 | llmlingua2_r50 | 2 | C |
| c0063 | llmlingua2_r30 | 1 | B |
| c0064 | llmlingua2_r30 | 2 | C |
| c0078 | llmlingua2_r30 | 1 | B |
| c0121 | llmlingua2_r30 | 1 | B |
| c0131 | llmlingua2_r30 | 2 | C |
| c0136 | llmlingua2_r30 | 4 | C |
| c0151 | llmlingua2_r30 | 1 | B |
| c0153 | llmlingua2_r30 | 1 | A |
| c0162 | llmlingua2_r30 | 1 | A |
| c0174 | llmlingua2_r50 | 1 | A |

## 3. 사람 분류별 회복률

같은 압축 문맥에서 답변 설정만 바꿨을 때 그 trial 이 accuracy >= 0.5 가 된 비율이다. [생각 켬] 이 붙은 열이 생각 토큰을 쓰는 설정이다.

| 사람 분류 | 오답 | (1) 생각 끔·T0 재실행 | (2) 서버 기본값 [생각 켬] | (3) 생각 끔·temperature 기본, 3회 평균 | luna (기본) [생각 켬] |
|---|---|---|---|---|---|
| 1 정답 구절 삭제 | 28 | 2/28 (7%) | 7/28 (25%) | 2.7/28 (10%) | 6/28 (21%) |
| 2 연결어·조건 삭제 | 10 | 1/10 (10%) | 6/10 (60%) | 1.7/10 (17%) | 5/10 (50%) |
| 3 표기 분해 | 2 | 1/2 (50%) | 2/2 (100%) | 1/2 (50%) | 2/2 (100%) |
| 4 정답 남음·추론 가능한데 틀림 | 8 | 1/8 (12%) | 7/8 (88%) | 1.3/8 (17%) | 8/8 (100%) |
| 5 기타 | 2 | 0/2 (0%) | 2/2 (100%) | 0.7/2 (33%) | 2/2 (100%) |
| **정보 손실 (1)** | 28 | 2/28 (7%) | 7/28 (25%) | 2.7/28 (10%) | 6/28 (21%) |
| **해석 손실 (2+3+4)** | 20 | 3/20 (15%) | 15/20 (75%) | 4/20 (20%) | 15/20 (75%) |
| 전체 | 50 | 5/50 (10%) | 24/50 (48%) | 7.3/50 (15%) | 23/50 (46%) |

### 정보 손실 대 해석 손실 (Fisher 정확 검정, 양측)

| 설정 | 정보 손실 (1) | 해석 손실 (2+3+4) | 차이 | Fisher p |
|---|---|---|---|---|
| (1) 생각 끔·T0 재실행 | 2/28 (7%) | 3/20 (15%) | +8%p | 0.636 |
| (2) 서버 기본값 [생각 켬] | 7/28 (25%) | 15/20 (75%) | +50%p | 0.001 |
| (3) 생각 끔·temperature 기본, 3회 평균 | 2.7/28 (10%) | 4/20 (20%) | +10%p | - (반복 평균) |
| luna (기본) [생각 켬] | 6/28 (21%) | 15/20 (75%) | +54%p | < 0.001 |

반복 평균인 열은 같은 trial 을 여러 번 센 것이라 독립 표본이 아니다. 그래서 Fisher 검정을 하지 않았다.

### 분류별 회복 trial 목록

- **(1) 생각 끔·T0 재실행**
  - 1 정답 구절 삭제: 2 / 28: c0046 llmlingua2_r50, c0151 llmlingua2_r30
  - 2 연결어·조건 삭제: 1 / 10: c0064 llmlingua2_r30
  - 3 표기 분해: 1 / 2: c0076 rule>llmlingua2
  - 4 정답 남음·추론 가능한데 틀림: 1 / 8: c0149 llmlingua2_r50
  - 5 기타: 0 / 2
- **(2) 서버 기본값 [생각 켬]**
  - 1 정답 구절 삭제: 7 / 28: c0012 llmlingua2_r30, c0049 rule>llmlingua2, c0063 llmlingua2_r30, c0111 llmlingua2_r30, c0111 rule>llmlingua2, c0150 llmlingua2_r30, c0174 rule>llmlingua2
  - 2 연결어·조건 삭제: 6 / 10: c0007 llmlingua2_r30, c0012 llmlingua2_r50, c0064 llmlingua2_r30, c0072 llmlingua2_r30, c0131 llmlingua2_r30, c0168 llmlingua2_r30
  - 3 표기 분해: 2 / 2: c0076 llmlingua2_r30, c0076 rule>llmlingua2
  - 4 정답 남음·추론 가능한데 틀림: 7 / 8: c0067 llmlingua2_r30, c0078 rule>llmlingua2, c0086 llmlingua2_r50, c0106 llmlingua2_r50, c0136 llmlingua2_r30, c0149 llmlingua2_r50, c0150 llmlingua2_r50
  - 5 기타: 2 / 2: c0085 rule>llmlingua2, c0092 rule>llmlingua2
- **(3) 생각 끔·temperature 기본, 3회 평균**
  - 1 정답 구절 삭제: 6 / 28: c0046 llmlingua2_r50 ×2, c0111 llmlingua2_r30 ×1, c0150 llmlingua2_r30 ×1, c0151 llmlingua2_r30 ×1, c0153 llmlingua2_r30 ×1, c0174 llmlingua2_r50 ×2
  - 2 연결어·조건 삭제: 3 / 10: c0012 llmlingua2_r50 ×3, c0072 llmlingua2_r30 ×1, c0131 llmlingua2_r30 ×1
  - 3 표기 분해: 1 / 2: c0076 rule>llmlingua2 ×3
  - 4 정답 남음·추론 가능한데 틀림: 2 / 8: c0149 llmlingua2_r50 ×3, c0150 llmlingua2_r50 ×1
  - 5 기타: 1 / 2: c0085 rule>llmlingua2 ×2
- **luna (기본) [생각 켬]**
  - 1 정답 구절 삭제: 6 / 28: c0012 llmlingua2_r30, c0063 llmlingua2_r30, c0111 llmlingua2_r30, c0111 rule>llmlingua2, c0150 llmlingua2_r30, c0151 llmlingua2_r30
  - 2 연결어·조건 삭제: 5 / 10: c0012 llmlingua2_r50, c0064 llmlingua2_r30, c0072 llmlingua2_r30, c0131 llmlingua2_r30, c0168 llmlingua2_r30
  - 3 표기 분해: 2 / 2: c0076 llmlingua2_r30, c0076 rule>llmlingua2
  - 4 정답 남음·추론 가능한데 틀림: 8 / 8: c0067 llmlingua2_r30, c0070 rule>llmlingua2, c0078 rule>llmlingua2, c0086 llmlingua2_r50, c0106 llmlingua2_r50, c0136 llmlingua2_r30, c0149 llmlingua2_r50, c0150 llmlingua2_r50
  - 5 기타: 2 / 2: c0085 rule>llmlingua2, c0092 rule>llmlingua2

## 4. 메모가 있는 행의 원자료

### c0085 rule>llmlingua2 (사람 분류 5)

- 메모: 출력 형식: 정답 뒤에 NOT FOUND가 붙음
- 질문: In FastAPI's background-task example that also uses a dependency, what text does get_query log when a q value is sent?
- 정답: `found query: {q}`
- test_v1 답변: `found query: {q} NOT FOUND`
- key_fact 판정 (fact_judge_v2, per_fact): "get_query logs the message "found query: {q}"." → False
- answer_accuracy 0.0 · not_found False · 예전 채점(grade): correct True, 방법 match, 문자열 일치 True, YES/NO judge None

| run | 답변 | accuracy |
|---|---|---|
| (1) 생각 끔·T0 재실행 | `found query: {q} NOT FOUND` | 0.0 |
| (2) 서버 기본값 [생각 켬] | `found query: {q}` | 1.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #1 | `found query: {q} NOT FOUND` | 0.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #2 | `found query: {q}` | 1.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #3 | `found query: {q}` | 1.0 |
| luna (기본) [생각 켬] | `found query: {q}` | 1.0 |

### c0092 rule>llmlingua2 (사람 분류 5)

- 메모: 채점 오류 의심: 모델 답이 사실상 정답
- 질문: Why are authentication tokens for FastAPI WebSocket endpoints usually sent as a query parameter or a cookie?
- 정답: `Browsers can't set custom headers on WebSocket connections`
- test_v1 답변: `Browsers can't send headers in WebSocket connections.`
- key_fact 판정 (fact_judge_v2, per_fact): "Browsers cannot set custom headers on WebSocket connections." → False
- answer_accuracy 0.0 · not_found False · 예전 채점(grade): correct True, 방법 judge, 문자열 일치 False, YES/NO judge True

| run | 답변 | accuracy |
|---|---|---|
| (1) 생각 끔·T0 재실행 | `Browsers can't send headers in WebSocket connections.` | 0.0 |
| (2) 서버 기본값 [생각 켬] | `Browsers can't send headers in WebSocket connections.` | 1.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #1 | `Browsers can’t send headers in WebSocket connections.` | 0.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #2 | `Browsers can't send headers in WebSocket connections.` | 0.0 |
| (3) 생각 끔·temperature 기본, 3회 평균 #3 | `Browsers can’t send headers in WebSocket connections.` | 0.0 |
| luna (기본) [생각 켬] | `Browsers can't send headers for WebSocket connections, so tokens are passed as a query parameter or a cookie.` | 1.0 |

## 5. judge 검증 (`judge_check_test.csv`)

human 이 채워진 행: **80 / 80** (빈 행 0 은 뺐다)

### 전체

| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |
|---|---|---|---|---|---|
| 전체 | 80 | 0.863 (69/80) | 0 | 11 | 0.725 |
| judge YES 행 | 40 | 1.000 (40/40) | 0 | 0 | - |
| judge NO 행 | 40 | 0.725 (29/40) | 0 | 11 | - |
| 부분 점수 문항 | 36 | 0.722 (26/36) | 0 | 10 | 0.483 |

- judge YES 행의 정확도 = judge 가 O 라고 한 것 중 사람도 O 인 비율 (정밀도). NO 행도 같다.
- 시트는 judge YES 40 / NO 40 으로 층화 추출했다. 실제 판정 분포(YES 95%)와 다르므로 전체 정확도는 이 표본에서의 값이다.

### 압축 조건별

| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |
|---|---|---|---|---|---|
| none | 15 | 0.800 (12/15) | 0 | 3 | 0.587 |
| rule | 13 | 0.769 (10/13) | 0 | 3 | 0.451 |
| LL2-r50 | 17 | 0.824 (14/17) | 0 | 3 | 0.653 |
| LL2-r30 | 17 | 1.000 (17/17) | 0 | 0 | 1.000 |
| rule>LL2 | 18 | 0.889 (16/18) | 0 | 2 | 0.780 |

### 유형별

| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |
|---|---|---|---|---|---|
| fact | 22 | 1.000 (22/22) | 0 | 0 | 1.000 |
| code | 12 | 0.917 (11/12) | 0 | 1 | 0.625 |
| procedure | 23 | 0.826 (19/23) | 0 | 4 | 0.662 |
| multi | 23 | 0.739 (17/23) | 0 | 6 | 0.504 |

### 설정별

| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |
|---|---|---|---|---|---|
| 기본 | 40 | 0.875 (35/40) | 0 | 5 | 0.750 |
| 생각 끔 | 40 | 0.850 (34/40) | 0 | 6 | 0.700 |

### 담당자별

| 구분 | n | 정확도 (일치율) | FP (사람 X·judge O) | FN (사람 O·judge X) | Cohen's κ |
|---|---|---|---|---|---|
| A | 20 | 0.900 (18/20) | 0 | 2 | 0.800 |
| B | 20 | 0.950 (19/20) | 0 | 1 | 0.900 |
| C | 20 | 0.800 (16/20) | 0 | 4 | 0.600 |
| D | 20 | 0.800 (16/20) | 0 | 4 | 0.600 |

### FP (사람 X, judge O): 0

### FN (사람 O, judge X): 11

| row_id | qid | 유형 | 설정 | 압축 조건 | 핵심 사실 | 모델 답변 | 메모 |
|---|---|---|---|---|---|---|---|
| T002 | c0171 | multi | 생각 끔 | rule>LL2 | FastAPI/Starlette add Content-Length to a Response. | `FileResponse` adds the `Content-Length` header. Set `httponly=True` to keep the cookie inaccessible to browser scripts. | 모델 답변에 핵심 사실이 명확하게 드러남 ⏎ 답변: `FileResponse` adds the `Content-Length` header. |
| T009 | c0172 | multi | 기본 | none | HTTPBasic sends WWW-Authenticate: Basic (with a realm if set). | HTTPBasic sends `WWW-Authenticate: Basic` with the 401 so browsers re-prompt. When `me` and `items` are both required, t |  |
| T012 | c0060 | procedure | 기본 | rule | FastAPI inspects __call__ for request parameters and calls it per request. | 1. Define a class whose `__init__` accepts the configuration parameter and stores it. ⏎ 2. Implement `__call__` with the |  |
| T014 | c0161 | multi | 기본 | LL2-r50 | The custom route class is ValidationErrorLoggingRoute. | The custom `APIRoute` approach reads the raw body with `await request.body()` and decodes it for the 422 error detail. A |  |
| T023 | c0161 | multi | 생각 끔 | rule | The custom route class is ValidationErrorLoggingRoute. | The custom `APIRoute` approach reads the raw body with `await request.body()` when `RequestValidationError` is caught. T |  |
| T025 | c0155 | multi | 기본 | LL2-r50 | fastapi run leaves FASTAPI_ENV unchanged, so a missing directory raises an error when the app is created. | With the default `check_dir="auto"`, `fastapi dev` sets `FASTAPI_ENV` to development, so a missing `dist` directory emit |  |
| T042 | c0166 | multi | 생각 끔 | LL2-r50 | A set field's schema has uniqueItems. | `jsonable_encoder` converts sets to lists. The documentation says request lists are de-duplicated and their schema uses  |  |
| T046 | c0088 | procedure | 기본 | none | The collector URL is set with OTEL_EXPORTER_OTLP_ENDPOINT. | 1. Set `OTEL_SERVICE_NAME` to your service name. ⏎ 2. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to the monitoring service’s OTLP |  |
| T050 | c0060 | procedure | 생각 끔 | none | FastAPI inspects __call__ for request parameters and calls it per request. | 1. Define a class whose `__call__` method implements the dependency. FastAPI inspects `__call__` for request parameters  |  |
| T068 | c0085 | code | 생각 끔 | rule>LL2 | get_query logs the message "found query: {q}". | found query: {q} NOT FOUND | 모델 답변 뒤에 NOT FOUND 확인 필요 |
| T078 | c0104 | procedure | 생각 끔 | rule | The result is encoded with jsonable_encoder and saved. | 1. Load the stored item data. ⏎ 2. Build a Pydantic model from it: `stored_item_model = Item(**stored_item_data)`. ⏎ 3.  |  |

## 6. 민감도 분석: judge FN 비율로 key_fact 판정 보정

run `luna-default-20261103` (luna 기본, test_v1_default.md). none 과 짝지은 문항 rule 138, llmlingua2_r50 138, llmlingua2_r30 138, rule>llmlingua2 137. judge 가 X 로 본 key_fact 는 조건별로 none 7, rule 3, llmlingua2_r50 9, llmlingua2_r30 18, rule>llmlingua2 11 개다 (사실 전체 232, 235, 235, 235, 233).

- 각 judge X 사실이 확률 p 로 사실은 O 라고 보고 다시 계산했다. NOT FOUND·빈 답 trial 은 judge 를 거치지 않았으므로 보정하지 않는다. FP 가 0 이라 O 판정은 내리지 않는다.
- 정확도·유지율은 기대값이고, CI 는 문항 짝 bootstrap 10,000 회 (시드 42) 다.
- "유지" 판단은 사전 기준(유지율 CI 하한 ≥ 95% 이고 Holm McNemar p ≥ 0.05)이다. McNemar 는 완전 정답 이진값이라 기대값으로 계산할 수 없다. 그래서 judge X 사실을 확률 p 로 뒤집은 표본 500 개마다 판단하고, "유지" 로 나온 표본 비율을 적는다.

- 사람 라벨 기준 p = 11/40 (judge X 행 중 사람 O). 시트는 judge X 를 따로 40 행 뽑았으므로 judge X 판정 전체에 대한 추정치로 쓴다.

| p | 조건 | 정확도 (none) | 유지율 [95% CI] | Holm p (중앙값) | 유지 판단 (표본 비율) |
|---|---|---|---|---|---|
| 보정 전 | rule | 0.993 (0.981) | 101.2% [99.9, 102.7] | 0.219 | 유지 |
| 보정 전 | llmlingua2_r50 | 0.912 (0.981) | 93.0% [88.1, 97.5] | 0.147 | 손실 |
| 보정 전 | llmlingua2_r30 | 0.803 (0.981) | 81.8% [75.2, 87.8] | 1.85e-06 | 손실 |
| 보정 전 | rule>llmlingua2 | 0.922 (0.981) | 93.9% [89.3, 97.9] | 0.154 | 손실 |
| 11/40 (p = 0.275) | rule | 0.995 (0.986) | 100.8% [100.0, 101.9] | 0.453 | 유지 (100%) |
| 11/40 (p = 0.275) | llmlingua2_r50 | 0.921 (0.986) | 93.3% [88.7, 97.4] | 0.125 | 손실 (0%) |
| 11/40 (p = 0.275) | llmlingua2_r30 | 0.817 (0.986) | 82.8% [76.5, 88.6] | 6.5e-06 | 손실 (0%) |
| 11/40 (p = 0.275) | rule>llmlingua2 | 0.933 (0.986) | 94.6% [90.5, 98.0] | 0.186 | 손실 (0%) |
| 13/40 (p = 0.325) | rule | 0.995 (0.987) | 100.8% [100.0, 101.8] | 0.488 | 유지 (100%) |
| 13/40 (p = 0.325) | llmlingua2_r50 | 0.922 (0.987) | 93.4% [88.8, 97.4] | 0.115 | 손실 (0%) |
| 13/40 (p = 0.325) | llmlingua2_r30 | 0.820 (0.987) | 83.0% [76.7, 88.8] | 6.5e-06 | 손실 (0%) |
| 13/40 (p = 0.325) | rule>llmlingua2 | 0.935 (0.987) | 94.7% [90.7, 98.1] | 0.23 | 손실 (0%) |
| 1/1 (p = 1.000) | rule | 1.000 (1.000) | 100.0% [100.0, 100.0] | 1 | 유지 (100%) |
| 1/1 (p = 1.000) | llmlingua2_r50 | 0.942 (1.000) | 94.2% [89.9, 97.8] | 0.0234 | 손실 (0%) |
| 1/1 (p = 1.000) | llmlingua2_r30 | 0.855 (1.000) | 85.5% [79.0, 91.3] | 7.63e-06 | 손실 (0%) |
| 1/1 (p = 1.000) | rule>llmlingua2 | 0.964 (1.000) | 96.4% [92.7, 99.3] | 0.125 | 손실 (0%) |

