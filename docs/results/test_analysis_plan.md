# test 본실험 분석 계획

> **실험 전에 커밋한다.** 아래 지표·검정·판단 기준은 test 결과를 보기 전에 정한 것이다. 결과를 본 뒤 바꾸는 항목은 결과 문서에 "사후 변경"으로 따로 적는다.
>
> **정확도는 잠정치로 표시한다.** deepseek-flash 채점은 사람 라벨 검증 전이다 (`judge_check_v3.csv`). 결과 문서의 모든 정확도·유지율·McNemar 표에 "(잠정)"을 붙이고, 사람 라벨 일치율이 나오면 갱신한다. 토큰·절감률·의미 손실·정답 핵심어 위치는 채점과 무관하므로 확정값이다.

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

**실행 기준:** 평가셋과 코드는 `test-v1-freeze` 태그와 같아야 한다. 실행 직전에 `git diff test-v1-freeze -- data src` 가 비어 있는지 확인한다 (이 계획 문서처럼 `docs/` 만 바뀐 커밋에서는 실행해도 된다). 평가셋은 이 태그 이후 바꾸지 않는다.

## 비용·시간 추정 (API 호출 없이)

- **답변 입력 토큰:** 동결 평가셋(`test-v1-freeze`) test 139문항을 실제로 로컬 압축해 셌다. 원문 대체 0건, drop_evidence 인용문 미일치 0건이다.
- **나머지 값:** dev 3회 반복 run(같은 코드·설정)의 trial 값으로 환산했다.
  - 답변 출력·응답 시간은 압축기별 trial 당 평균으로, judge 는 key_fact 당 평균으로 잡았다 (test key_facts 235개).
  - empty·drop_evidence 의 dev 값은 `20261019-231040` 에서 가져왔다.

| 조건 | 답변 입력 (실측) | 입력 절감 | 답변 출력 | judge 호출 | judge 입력 | judge 출력 | 로컬 압축 | 답변 응답 시간 합 |
|---|---|---|---|---|---|---|---|---|
| none | 336,052 | - | ~5,300 | ~235 | ~62,300 | ~20,500 | 0 | ~5분 |
| rule | 266,263 | 20.8% | ~5,500 | ~235 | ~63,200 | ~17,700 | 0 | ~4분 |
| llmlingua2_r50 | 219,775 | 34.6% | ~5,300 | ~231 | ~61,500 | ~20,800 | 5.6분 | ~5분 |
| llmlingua2_r30 | 165,847 | 50.6% | ~5,400 | ~230 | ~61,900 | ~20,800 | 5.2분 | ~4분 |
| rule>llmlingua2 | 177,315 | 47.2% | ~5,600 | ~231 | ~62,800 | ~22,400 | 3.6분 | ~4분 |
| empty | 16,825 | 95.0% | ~700 | ~0 | ~0 | ~0 | 0 | ~9분 |
| drop_evidence | 329,529 | 1.9% | ~5,200 | ~190 | ~54,800 | ~26,900 | 0 | ~8분 |
| **합계 (973 trial)** | **1,511,606** | | **약 33K** | **약 1,350** | **약 366K** | **약 129K** | 약 14분 | 약 40분 |

- **답변 모델:** `gpt-6-luna` 호출은 973번이다.
- **empty 의 judge:** dev 에서는 empty 가 모두 NOT FOUND 라 judge 를 부르지 않았다. test 에서 empty 가 답을 내면 judge 호출이 최대 235번(입력 약 6만 토큰) 늘어난다.
- **시간:** 전체 약 3.4~4.1시간으로 본다. dev run 의 trial 당 실제 소요 시간 12.6~15.3초에 973 trial 을 곱한 값이다.
  - 답변 응답 시간 합(약 40분) 외에 judge 호출(fact 마다 생각 토큰을 쓴다), bge-m3 임베딩, 로컬 압축이 들어간다.
  - dev 1회차(32.7초/trial)는 네트워크 장애가 있어 뺐다.
- **비용:** 단가가 저장소에 기록되어 있지 않아 토큰으로만 적는다. 결과 run 에서 `src/stats.py --price-in/--price-out` 으로 환산한다.

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

## 3. empty 바닥값·drop_evidence

- **empty (문서 없이, 실험 지시문 answer_v1):** 문서가 없을 때의 정확도 바닥값이다. `answer_accuracy` 와 NOT FOUND 비율을 낸다.
  - dev 바닥값은 0.000 이다 (35문항 모두 NOT FOUND, `20261019-231040`). test 도 0 에 가까울 것으로 본다.
  - 보정 유지율 = (압축 − empty) / (none − empty) × 100 (`experiment.calibrated_retention`) 을 표 1 옆 열로 낸다.
  - empty 에서 맞힌 문항(accuracy ≥ 0.5)은 목록으로 낸다. 지시문을 어기고 자기 지식으로 답한 경우다.
- **drop_evidence (근거 인용문 줄만 지움):** 문서 중복성이 정답을 얼마나 지키는지 본다.
  - 정확도, NOT FOUND, 2절의 A/B/C 분포 (drop_evidence 는 근거 줄이 없으므로 A 가 0 이어야 한다)
  - **중복도 1 vs 2+:** `redundancy.py` 3절 표. none 문맥에서 정답 핵심어가 한 곳(근거 자리)에만 있는 문항과 두 곳 이상 있는 문항의 정확도, 정답 문항 수의 Fisher 정확 검정(양측)
    - 근거가 사라진 trial(b + c)만 본 같은 비교도 낸다
    - dev: 0.282 vs 0.818, p = 0.004. test 에서 같은 방향이면 "중복성이 근거 삭제를 버티게 한다"를 재현한 것으로 본다
  - 근거 줄이 없는데 맞힌 문항은 5절의 memory_suspect 로 분류한다

## 4. 유형별

`python src/stats.py results/runs/<test_run> --by-type`

- code 42 / fact 38 / procedure 30 / multi 29 마다 표 1 의 정확도·유지율·CI 를 낸다
- 유형별 n 이 29~42 라 CI 가 넓다. 유형 간 차이는 서술만 하고 검정 결론을 내지 않는다
- dev 에서 가장 흔들린 fact(r30 0.85 ± 0.11) 가 test 에서도 가장 낮은지 본다

## 5. memory_suspect (normalized-v2)

`EVAL_DIR=data/evalsets/claude-v1 python src/memory_suspect.py results/runs/<test_run>`

- 정답 핵심어 × 근거 보존율 두 축 분류다 (`CORE_MATCH_VERSION = normalized-v2`, 근거 없음 < 0.25, 낮음 < 0.5).
- 압축기별로 unmeasurable / not_correct / core_present / evidence_kept / evidence_low / evidence_absent 건수를 낸다.
- **헤드라인:** memory_suspect = evidence_absent (근거 보존율 < 0.25 인데 맞힘). 민감도는 evidence_absent + evidence_low 다.
- 헤드라인 문항은 문맥을 읽고 "남은 문맥으로 추론 가능" / "기억으로 보임" 으로 사람이 나눈다. dev 에서는 drop_evidence 의 c0004·c0030 이 코드 예시로 추론 가능한 경우였다.
- 한계: 근거 보존율은 한 줄짜리 코드 인용문에서 과대평가된다 ([중복도 분석 한계 1](redundancy_analysis.md#한계)). 그래서 2절의 근거 자리 안 핵심어 판정(A/B/C)과 나란히 놓고 본다.

## 6. closed-book 부분집합: 문서 없이 못 맞히는 문항

gpt-6-luna 는 자기 지식으로 답하라고 하면 test 의 64% 를 문서 없이 맞힌다 ([closed-book 재검사](closed_book_luna.md)). 그래서 "문서가 있어야 맞히는 문항"만으로 표 1 을 다시 낸다.

- **자료:** `results/closed_book_luna/closed_book.jsonl` 에 저장된 gpt-6-luna closed-book 답변 (새 호출 없음)
- **부분집합 S_A (주):** 판정 A(`grader.closed_book_knows`)로 문서 없이 못 맞힌 문항이다.
  - 저장된 답변을 동결 평가셋의 answer·key_entities 로 다시 판정했다. 검수 전 판정과 바뀐 문항은 0건이다.
  - 빈 답변(c0096, c0155, c0168)은 "모름"으로 친다.
  - **n = 50** (code 15, fact 13, procedure 12, multi 10)
- **부분집합 S_AB (보조):** 판정 A 모름 이고 판정 B(closed-book 답변의 key_facts 채점) < 0.5 다.
  - **n = 28** (code 15, procedure 6, fact 4, multi 3)
  - 판정 B 는 검수(#41·#43) 전 key_facts 로 채점한 값이다. 검수에서 key_facts 가 바뀐 26문항은 B 가 낡았다 (UNKNOWN 으로 B 를 0 으로 둔 c0010·c0117 은 영향 없음).
  - S_AB 28문항 중 B 가 낡은 문항은 5개, S_A 50문항 중에서는 10개다.
  - B 를 새로 하려면 저장된 답변을 지금 key_facts 로 다시 채점해야 한다 (judge 호출 44 fact, 입력 약 1.1만 토큰). 본실험 승인 때 같이 정한다. 하지 않으면 S_AB 는 낡은 B 로 정의했다고 결과 문서에 적는다.
- **표:** S_A, S_AB 마다 표 1 과 같은 열(절감률, 정확도 ± bootstrap 95% CI, 유지율, McNemar p, NOT FOUND)을 낸다.
  - `closed_book_check.py --subset-run results/runs/<test_run>/trials.jsonl` 은 평균과 유지율만 낸다. CI 와 McNemar 는 `stats.py` 에 `--exclude` 로 부분집합 밖 문항을 넘겨 계산한다.
- **해석:** n 이 50·28 이라 CI 가 넓다. 전체 표와 같은 방향인지만 본다. 부분집합에서 유지율이 크게 낮으면 "전체 유지율이 모델 지식으로 부풀었다"로 적는다.

## 7. test 코드 비중 (절감률 상한)

LLMLingua-2 는 fenced code block 을 지우지 않는다 (`fenced-code-blocks-v1`). 그래서 문맥의 코드 비중이 줄일 수 있는 양의 상한을 정한다.

| split | 문항 | 문맥 토큰 | 코드 블록 토큰 | 코드 비중 | code / fact / multi / procedure |
|---|---|---|---|---|---|
| dev | 35 | 73,051 | 23,049 | 31.6% | 30.8 / 29.5 / 35.6 / 31.5% |
| test | 139 | 319,186 | 85,870 | **26.9%** | 27.0 / 26.7 / 26.7 / 27.4% |

- 계산: `compressors.llmlingua2._split_fenced_blocks` 로 none 문맥을 나누고 `tiktoken:o200k_base` 로 센다
- **상한:** 코드 블록 밖 설명만 지울 수 있다. 그래서 문맥 토큰 절감률의 상한은 (1 − 코드 비중) × (1 − 남기는 비율) 이다.
  - LLMLingua-2 r30 (설명의 30% 를 남기고 70% 를 지움): (1 − 0.269) × 0.7 = **51.2%** (dev 47.9%)
  - LLMLingua-2 r50: (1 − 0.269) × 0.5 = **36.5%** (dev 34.2%)
  - 압축기가 지울 수 없는 코드 블록 전체를 빼고 계산하면 1 − 코드 비중 = 73.1% 가 어떤 비율로도 못 넘는 한계다
  - 문서 제목 줄과 질문 속 식별자도 지우지 않으므로 실제 상한은 이보다 조금 낮다
- **로컬 압축으로 본 실측 (API 호출 없음):** test none 문맥은 319,227 토큰이다 (답변 입력 − empty 입력. empty 입력 16,825 는 시스템 프롬프트와 질문뿐이다). 문맥 토큰 절감률은 r50 36.4%, r30 53.3%, rule>llmlingua2 49.7% 다.
  - **r50 은 상한 36.5% 와 거의 같다.**
  - **r30 은 상한 51.2% 를 2.1%p 넘는다.** LLMLingua-2 의 비율은 자기 토크나이저(xlm-roberta) 기준이다. 그래서 `o200k_base` 로 센 절감률이 비율보다 커질 수 있다 (지운 단어가 o200k 에서 토큰이 더 많은 경우). 따라서 이 식은 엄밀한 상한이 아니라 **근사 기준선**으로 쓴다.
  - 결과 문서에는 실측 절감률 / 근사 기준선 비를 낸다.
- **결과 문서에 낼 값:** 압축기별 문맥 토큰 절감률 / 상한 (상한 대비 달성률)
  - 입력 토큰 절감률은 시스템 프롬프트·질문을 포함하므로 문맥 절감률보다 낮다
- test 의 코드 비중이 dev 보다 4.7%p 낮다. 같은 비율 설정에서 test 절감률이 dev 보다 조금 높게 나올 수 있다

## 실행 전 확인

- **c0152:** 검수 메모(장우진)대로 수정했다 (#43). 근거를 `app-structure/lifespan-events.md` 131행 하나로 줄였고 (전제 문서 `integrations/sql-databases.md` 제거), 유형은 multi → fact 로 바꿨다. 정답은 key_facts 와 맞췄다. none 문맥에서 `answer_core_in_context` 가 True 다.
- **실행 직전:** `git describe --tags` 가 `test-v1-freeze` (이 계획과 #43 을 포함한 main) 인지, `python -m unittest discover -s tests` 가 통과하는지 확인한다.

## 결과 문서

`docs/results/test_v1.md` 에 위 1~7 절 순서로 쓴다. `results/` 는 커밋하지 않는다.
