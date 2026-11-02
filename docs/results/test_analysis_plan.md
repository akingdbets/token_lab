# test 본실험 분석 계획

> **실험 전에 커밋한다.** 아래 지표·검정·판단 기준은 test 결과를 보기 전에 정한 것이다. 결과를 본 뒤 바꾸는 항목은 결과 문서에 "사후 변경"으로 따로 적는다.

dev 에서 정한 압축기 후보를 test 139문항에서 한 번 측정한다.
dev 결과는 [LLMLingua-2 dev v3 (3회 반복)](llmlingua2_dev_v3_repeat.md) 와 [중복도 분석](redundancy_analysis.md) 에 있다.

## 고정 사항

| 항목 | 값 |
|---|---|
| 평가셋 | `data/evalsets/claude-v1` test 139문항. 사람 검수 139/139 (#37 검수표, #41 반영, c0152 #43). 고정 태그 `test-v1-freeze` |
| 문항 구성 | code 42, fact 38, procedure 30, multi 29. key_facts 235개. 모든 문항에 근거 인용문 있음 |
| 압축기 | none, rule, llmlingua2_r50, llmlingua2_r30, rule>llmlingua2, empty, drop_evidence |
| LLMLingua-2 안전 정책 | `question-identifiers-v1+fenced-code-blocks-v1+document-headers-v1+unsplit-identifiers-v1`. dev 3회 반복 run 432개 기록과 같다. 그 run 의 코드(`96d862c`) 이후 `src/compressors`·`src/prompts` 변경 없음 |
| 답변 | `gpt-6-luna`, temperature 0.0, seed 42, reasoning_effort `none`, `max_completion_tokens` 512, answer 프롬프트 v1 `d12495bd1412` |
| 판정 | `deepseek-flash`, per_fact, fact_judge_v2 `7e441ad04bab`, temperature 0.0, seed 42 |
| 토크나이저·임베딩 | `tiktoken:o200k_base`, bge-m3 (로컬 Ollama, `--semantic`) |
| 반복 | 1회. dev 에서 같은 설정도 답변이 run 마다 다르므로(86/210 쌍) 결과 문서에 이 한계를 적는다 |

실행 명령 (확인 후 실행):

```
EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split test --compressors "none,rule,llmlingua2_r50,llmlingua2_r30,rule>llmlingua2,empty,drop_evidence" --semantic
```

끊기면 `--resume` 으로 같은 run 에 이어 붙인다. 원문 대체(fallback), 답변 잘림, judge 오류가 생기면 결과 문서에 건수와 문항을 적는다. 오류 trial 을 빼고 다시 계산하지 않는다 (재실행은 `--resume` 의 빠진 trial 만).

**실행 기준:** `test-v1-freeze` 태그가 가리키는 커밋에서 실행한다. 평가셋은 이 태그 이후 바꾸지 않는다.

## 비용·시간 추정 (API 호출 없이)

- **답변 입력 토큰:** test 139문항을 실제로 로컬 압축해 셌다 (원문 대체 0건, drop_evidence 인용문 미일치 0건).
  c0152 수정(#43) 전에 센 값이다. 수정으로 그 문항의 none 문맥이 1,830 토큰 줄어, 압축기마다 수백~1.8K 토큰 줄어든다 (합계 1% 미만).
- **나머지 값:** dev 3회 반복 run(같은 코드·설정)의 trial 값으로 환산했다. 답변 출력·시간은 압축기별 trial 당, judge 는 key_fact 당이다.
- empty·drop_evidence 의 dev 값은 `20261019-231040` 에서 가져왔다.

| 압축기 | 답변 입력 (실측) | 답변 출력 | judge 호출 | judge 입력 | judge 출력 | 로컬 압축 시간 |
|---|---|---|---|---|---|---|
| none | 337,883 | ~5,300 | ~235 | ~62,300 | ~20,500 | 0 |
| rule | 267,842 (−20.7%) | ~5,500 | ~235 | ~63,200 | ~17,700 | 0 |
| llmlingua2_r50 | 221,019 (−34.6%) | ~5,300 | ~231 | ~61,500 | ~20,800 | 4.3분 |
| llmlingua2_r30 | 166,811 (−50.6%) | ~5,400 | ~230 | ~61,900 | ~20,800 | 4.9분 |
| rule>llmlingua2 | 178,372 (−47.2%) | ~5,600 | ~231 | ~62,800 | ~22,400 | 3.6분 |
| empty | 16,827 | ~700 | ~0 | ~0 | ~0 | 0 |
| drop_evidence | 331,348 (−1.9%) | ~5,200 | ~190 | ~54,800 | ~26,900 | 0 |
| **합계 (973 trial)** | **약 1.52M** | **약 33K** | **약 1,350** | **약 366K** | **약 129K** | 약 13분 |

- **답변 모델:** `gpt-6-luna` 호출 973번이다. empty 는 dev 에서 모두 NOT FOUND 라 judge 를 부르지 않았다. test 에서 empty 가 답을 내면 judge 호출이 최대 235번(입력 약 6만 토큰) 늘어난다.
- **시간:** dev run 의 trial 당 실제 소요 시간으로 잡으면 약 3.4~4.1시간이다 (2·3회차 14.0~15.3초, drop run 12.6초). 1회차(32.7초)는 네트워크 장애가 있어 뺐다. 로컬 압축과 bge-m3 임베딩 시간이 포함된 값이다.
- **비용:** 단가가 저장소에 기록되어 있지 않아 토큰으로만 적는다. `src/stats.py --price-in/--price-out` 으로 결과 run 에서 환산한다.

## 1. 표 1: 압축기별 주 결과

`python src/stats.py results/runs/<test_run> --boot 10000 --seed 42` (none 과 같은 문항끼리 짝지음)

| 열 | 정의 |
|---|---|
| 입력 토큰 절감률 | 입력 토큰 합의 절감률 (`input_reduction_pct`). 과금 입력 토큰 절감률도 함께 |
| 정확도 ± 95% CI | `answer_accuracy` (key_facts 충족 비율의 평균). 문항 복원 추출 paired bootstrap 10,000회, percentile |
| 유지율 ± 95% CI | 짝지은 문항의 압축 정확도 / none 정확도 × 100 (`retention_pct`) |
| none 대비 차이 ± 95% CI | 압축 − none (`diff`) |
| McNemar p | 문항별 완전 정답(`answer_accuracy == 1`) 짝지음, 정확 이항 검정 양측. b/c (none 만 / 압축기만 맞힘)도 함께 |
| NOT FOUND | 답변이 `NOT FOUND` 로 시작하는 비율 |
| 의미 손실·핵심 개체 보존율 | `--semantic` 지표 (채점과 무관) |

- **검정 대상:** 압축기 4개(rule, r50, r30, rule>llmlingua2) vs none. 다중 비교는 Holm 보정 p 를 같이 적는다 (stats.py 에는 없어 4개 p 로 직접 계산). empty·drop_evidence 는 진단용이라 검정 묶음에 넣지 않는다.
- **판단 기준 (사전):**
  - **유지:** 유지율 95% CI 하한이 95% 이상이고 Holm 보정 McNemar p ≥ 0.05 → "정확도 손실 없이 줄임"
  - **손실:** CI 하한 < 95% 이거나 보정 p < 0.05 → "손실 있음"으로 보고, 아래 2절로 원인을 본다
  - 둘 다 아니면 "판단 보류 (test 1회, n=139)"로 적는다
- **dev 와 비교:** dev 3회 평균(r50 0.952, r30 0.940, rule>llmlingua2 0.952, none 0.986)과 나란히 적는다. dev 에서 정한 압축기 순서가 test 에서도 같은지 본다.

## 2. 정답 핵심어 위치 a/b/c

[중복도 분석 4절](redundancy_analysis.md#4-근거-자리-안의-정답-핵심어로-다시-본-상태) 과 같은 방식이다 (normalized-v2, 근거 자리 안 핵심어 기준).

```
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/<test_run> --compressors "llmlingua2_r50,llmlingua2_r30,rule>llmlingua2,drop_evidence" --core-states
EVAL_DIR=data/evalsets/claude-v1 python src/redundancy.py results/runs/<test_run>
```

- **상태별 표:** A(근거 자리에 남음) / B(다른 위치에만, code·prose·both·mixed) / C(문맥 전체에서 사라짐). 압축기별 건수·비율·정확도·NOT FOUND.
- **C 전체 목록:** 문맥을 읽고 셋으로 나눈다.
  - 표기상 C: 정답 단어가 제자리에 있고 사이 단어만 빠짐
  - 일부 삭제: 정답 표현 일부만 남음
  - 실제 삭제: 정답 단어가 없음
- **A 인데 틀린 목록:** 인용문 원문과 압축 후 같은 부분을 나란히 놓고, "연결어 삭제"인지 판정한다.
  - 연결어 삭제: 정답 단어는 남고, 그 단어와 질문을 잇는 말(주어·동사·조건절·괄호 구조)이 지워짐
  - 그 밖: 채점 문제, 질문 해석 차이, 근거와 무관한 오답
- **중복도:** 중복도 1 vs 2+ 정확도(압축기별·유형별)와 Fisher p (3절 방식).
- **dev 에서 확인할 예측:**
  - LLMLingua-2 의 A 비율이 dev 처럼 높다 (dev: r50 91%, r30 74%, rule>llmlingua2 94%)
  - B 는 거의 다 맞는다 (dev 21/21)
  - LLMLingua-2 의 오답은 정답 단어 삭제(C)보다 연결어 삭제(A 오답)에서 더 많다 (dev 3 vs 7)
  - drop_evidence 는 중복도 1 의 정확도가 2+ 보다 낮다 (dev 0.28 vs 0.82, p = 0.004)

## 3. empty·drop_evidence

- **empty (문서 없이):** test 의 문서 없이 풀리는 정도다. `answer_accuracy` 와 NOT FOUND 비율을 낸다.
  - 보정 유지율 = (압축 − empty) / (none − empty) × 100 (`experiment.calibrated_retention`, 표 1 옆 열)
  - empty 에서 맞힌 문항은 목록으로 낸다 (평가셋 closed-book 필터를 통과했는데 맞힌 문항)
- **drop_evidence (근거 인용문 줄만 지움):** 문서 중복성이 정답을 얼마나 지키는지 본다.
  - 정확도, NOT FOUND, 2절의 B/C 분포, 중복도 1 vs 2+ 비교
  - 근거 줄이 없는데 맞힌 문항은 [memory_suspect v2](../../src/memory_suspect.py) 로 분류한다 (`python src/memory_suspect.py results/runs/<test_run>`)

## 4. 유형별

`python src/stats.py results/runs/<test_run> --by-type`

- code 42 / fact 38 / procedure 30 / multi 29 마다 표 1 의 정확도·유지율·CI 를 낸다
- 유형별 n 이 30~42 라 CI 가 넓다. 유형 간 차이는 서술만 하고 검정 결론을 내지 않는다
- dev 에서 가장 흔들린 fact(r30 0.85 ± 0.11) 가 test 에서도 가장 낮은지 본다

## 5. test 코드 비중 (절감률 상한)

LLMLingua-2 는 fenced code block 을 지우지 않는다 (`fenced-code-blocks-v1`). 그래서 문맥의 코드 비중이 줄일 수 있는 양의 상한을 정한다.

| split | 문항 | 문맥 토큰 | 코드 블록 토큰 | 코드 비중 | code / fact / multi / procedure |
|---|---|---|---|---|---|
| dev | 35 | 73,051 | 23,049 | 31.6% | 30.8 / 29.5 / 35.6 / 31.5% |
| test | 139 | 319,186 | 85,870 | **26.9%** | 27.0 / 26.7 / 26.7 / 27.4% |

- 계산: `compressors.llmlingua2._split_fenced_blocks` 로 none 문맥을 나누고 `tiktoken:o200k_base` 로 센다
- **상한:** 코드 블록 밖 설명만 지울 수 있으므로, 문맥 토큰 절감률의 상한은 1 − 코드 비중 이다. test 는 73.1%, dev 는 68.4% 다
  - 문서 제목 줄과 질문 속 식별자도 지우지 않으므로 실제 상한은 이보다 조금 낮다
- **결과 문서에 낼 값:** 압축기별 문맥 토큰 절감률 / 상한 (상한 대비 달성률)
  - 입력 토큰 절감률은 시스템 프롬프트·질문을 포함하므로 문맥 절감률보다 낮다
- test 의 코드 비중이 dev 보다 4.7%p 낮다. 같은 비율 설정에서 test 절감률이 dev 보다 조금 높게 나올 수 있다

## 실행 전 확인

- **c0152:** 검수 메모(장우진)대로 수정했다 (#43). 근거를 `app-structure/lifespan-events.md` 131행 하나로 줄였고 (전제 문서 `integrations/sql-databases.md` 제거), 유형은 multi → fact 로 바꿨다. 정답은 key_facts 와 맞췄다. none 문맥에서 `answer_core_in_context` 가 True 다.
- **실행 직전:** `git describe --tags` 가 `test-v1-freeze` (이 계획과 #43 을 포함한 main) 인지, `python -m unittest discover -s tests` 가 통과하는지 확인한다.

## 결과 문서

`docs/results/test_v1.md` 에 위 1~5 절 순서로 쓴다. `results/` 는 커밋하지 않는다.
