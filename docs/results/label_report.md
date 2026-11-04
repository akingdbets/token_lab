# 사람 라벨 집계

`python src/label_report.py` 로 만든다 (2026-11-04 16:40). 라벨 기준은 [labeling_guide.md](labeling_guide.md). 1~5절은 스크립트가 만들고, 아래 수기 구간은 사람이 쓴다.

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

human 이 채워진 행: **0 / 80** (빈 행 80 은 뺐다)

아직 사람 라벨이 없다.

