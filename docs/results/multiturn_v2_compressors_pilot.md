# 멀티턴 v2 압축기 파일럿 (v1 시나리오, presummary · fact_notes)

2026-11-27. 캐시가 없는 LLM 가정 (멘토 회의 결정): 토큰·정확도 기준으로만 비교한다.

## 설정

| 항목 | 값 |
|---|---|
| 시나리오 | data/evalsets/multiturn-v1 (3개 × 9턴, 문서가 붙은 턴 9개, 페이지 9개) |
| 답변 | gpt-6-luna, reasoning_effort=server_default, 출력 한도 4096, 지시문 mt_answer_v2 (기존과 같음) |
| 채점 | per_fact (기존과 같음) |
| sample | 3 (기준 궤적 sample 0, 기존 기준 궤적 재사용) |
| presummary | gpt-6-luna, server_default, 출력 한도 4096, 목표 비율 0.25, 지시문 presummary_v1 |
| fact_notes | gpt-6-luna, server_default, 출력 한도 4096, 목표 비율 0.25, 지시문 fact_notes_v1, keep_recent 1 |
| 새 run | `results/runs/mt_20261127-222444` (none, presummary, fact_notes) |
| 기존 run | `results/runs/mt_20261123-233727` 을 sample 0–2 로 잘라 같은 표에 합침 (none 은 기존 run 의 행) |

## 전체 표 (none 대비, sample 0–2)

총 토큰 = 답변 입력 + 답변 출력(추론 포함) + 압축 LLM 토큰(요약·메모, 추론 포함). 압축 LLM 비중 = 압축 LLM 토큰 / 압축 쪽 총 토큰.
비열등: 마진 0.10, 턴 단위 쌍체 부트스트랩 / 시나리오 군집 부트스트랩 (시나리오 3개라 군집 쪽은 불안정).

| 압축기 | 입력 절감 | 총 토큰 절감 | 압축 LLM 비중 | 추론 평균 (none → 압축) | 추론 변화 | 유지율 | 비열등 턴 / 군집 |
|---|---|---|---|---|---|---|---|
| window(2) | 53.8% | 52.7% | 0.0% | 27.4 → 51.2 | 86.5% | 59.3% | ✗ / ✗ |
| window_budget(2000) | 59.5% | 57.4% | 0.0% | 27.4 → 92.6 | 237.5% | 67.3% | ✗ / ✗ |
| window_budget(4000) | 27.3% | 25.8% | 0.0% | 27.4 → 81.1 | 195.6% | 77.8% | ✗ / ✗ |
| window_budget(8000) | 0.0% | -0.0% | 0.0% | 27.4 → 27.5 | 0.0% | 100.0% | ✓ / ✓ |
| query_select(2000) | 48.2% | 47.1% | 0.0% | 27.4 → 43.5 | 58.7% | 94.2% | ✗ / ✗ |
| query_select(4000) | 35.1% | 34.2% | 0.0% | 27.4 → 40.8 | 48.6% | 100.0% | ✓ / ✓ |
| query_select(8000) | 33.9% | 33.0% | 0.0% | 27.4 → 42.0 | 53.0% | 100.0% | ✓ / ✓ |
| per_message(rule) | 16.4% | 16.1% | 0.0% | 27.4 → 26.4 | -3.8% | 100.0% | ✓ / ✓ |
| per_message(llmlingua2) | 26.6% | 26.0% | 0.0% | 27.4 → 37.1 | 35.2% | 92.0% | ✗ / ✗ |
| on_arrival(rule) | 19.1% | 18.9% | 0.0% | 27.4 → 25.9 | -5.8% | 100.0% | ✓ / ✓ |
| on_arrival(llmlingua2) | 31.2% | 30.2% | 0.0% | 27.4 → 51.4 | 87.4% | 84.6% | ✗ / ✗ |
| rolling_summary(2000)[sre=server_default] | 48.9% | 14.5% | 38.8% | 27.4 → 49.1 | 79.0% | 93.8% | ✗ / ✗ |
| rolling_summary(2000)[sre=none] | 57.7% | 38.1% | 29.7% | 27.4 → 48.3 | 76.1% | 72.8% | ✗ / ✗ |
| rolling_summary(4000)[sre=server_default] | 25.8% | 10.6% | 16.5% | 27.4 → 31.3 | 14.2% | 100.0% | ✓ / ✓ |
| rolling_summary(4000)[sre=none] | 34.6% | 22.9% | 14.0% | 27.4 → 44.5 | 62.2% | 81.5% | ✗ / ✗ |
| rolling_summary(8000)[sre=server_default] | 0.0% | -0.0% | 0.0% | 27.4 → 27.5 | 0.0% | 100.0% | ✓ / ✓ |
| rolling_summary(8000)[sre=none] | 0.0% | -0.0% | 0.0% | 27.4 → 27.5 | 0.0% | 100.0% | ✓ / ✓ |
| frozen_summary(2000)[sre=server_default] | 48.2% | 16.9% | 36.1% | 27.4 → 53.5 | 95.1% | 91.0% | ✗ / ✗ |
| frozen_summary(2000)[sre=none] | 57.0% | 38.4% | 28.2% | 27.4 → 49.6 | 80.9% | 72.0% | ✗ / ✗ |
| frozen_summary(4000)[sre=server_default] | 26.0% | 12.1% | 15.3% | 27.4 → 29.2 | 6.4% | 98.8% | ✓ / ✓ |
| frozen_summary(4000)[sre=none] | 34.5% | 22.8% | 13.9% | 27.4 → 48.1 | 75.3% | 80.9% | ✗ / ✗ |
| frozen_summary(8000)[sre=server_default] | 0.0% | -0.0% | 0.0% | 27.4 → 27.5 | 0.0% | 100.0% | ✓ / ✓ |
| frozen_summary(8000)[sre=none] | 0.0% | -0.0% | 0.0% | 27.4 → 27.5 | 0.0% | 100.0% | ✓ / ✓ |
| on_arrival(rule)>frozen_summary(8000)[sre=server_default] | 19.1% | 18.9% | 0.0% | 27.4 → 25.9 | -5.8% | 100.0% | ✓ / ✓ |
| on_arrival(rule)>frozen_summary(8000)[sre=none] | 19.1% | 18.9% | 0.0% | 27.4 → 25.9 | -5.8% | 100.0% | ✓ / ✓ |
| presummary | 37.0% | 36.2% | 0.0% | 27.4 → 41.1 | 49.8% | 96.3% | ✗ / ✗ |
| fact_notes | 42.2% | 21.2% | 25.6% | 27.4 → 36.6 | 33.4% | 98.6% | ✓ / ✓ |


presummary 의 요약 생성 토큰(구축 비용, 아래)은 run 토큰에 넣지 않았다. 이번 파일럿 규모에서 구축 토큰 24,226 을 run 에 넣으면
presummary 의 총 토큰 절감률은 36.2% → 29.3% 가 된다. 이제 summary 가 두 값을 기본으로 낸다 (`total_token_reduction_pct_without_build` / `_with_build`). 실서비스에서는 페이지 요약을 여러 대화가 공유하므로 29.3% 는 구축 부담을 대화 하나에 전부 넣은 하한이고, 36.2% 는 대화가 충분히 많을 때의 극한이다.

## 토큰 항목 (합계, 81 trial)

| | 답변 입력 | 답변 출력 | 그중 추론 | 압축 LLM 입력 | 압축 LLM 출력 | 총 |
|---|---|---|---|---|---|---|
| none | 343,902 | 4,734 | 2,224 | 0 | 0 | 348,636 |
| presummary | 216,591 | 5,729 | 3,331 | 0 | 0 | 222,320 |
| fact_notes | 198,861 | 5,445 | 2,965 | 53,658 | 16,770 | 274,734 |

fact_notes 는 입력을 가장 많이 줄였지만(42.2%), 메모 추출 호출 27번(문서 턴 9 × sample 3)의 입력이 그 턴 문서 전체라서 총 토큰 절감은 21.2% 에 그친다.

## turn_type 별 정확도

| 압축기 | new | followup | recall | synthesis |
|---|---|---|---|---|
| none | 1.00 | 1.00 | 1.00 | 1.00 |
| presummary | 1.00 | 1.00 | 1.00 | 0.83 |
| fact_notes | 1.00 | 1.00 | 1.00 | 0.94 |
| per_message(rule) | 1.00 | 1.00 | 1.00 | 1.00 |
| on_arrival(rule) | 1.00 | 1.00 | 1.00 | 1.00 |
| per_message(llmlingua2) | 1.00 | 0.81 | 0.83 | 1.00 |

recall 거리(4·5·6턴)별로는 presummary·fact_notes 모두 1.00 이다. 떨어진 턴은 전부 synthesis 다.

- presummary: mt01_security 턴 6 (sample 3개 모두 NOT FOUND). JWT 페이지 요약에 "/token 이 잘못된 자격 증명에 401 Incorrect username or password" 문장이 빠졌다
  (요약에는 get_current_user 의 401 "Could not validate credentials" 만 남음). 요약 누락 1건이 시나리오 하나의 턴 하나를 통째로 깎았다.
- fact_notes: mt01_security 턴 6 (sample 2개 0.67), 턴 7 (sample 1개 0.5). 부분 점수.

## 실제 압축률 (목표 0.25)

presummary (페이지 9개): 평균 0.413, 전체 0.408. 목표 2배(0.5) 초과 1개 (middleware/cors.md 0.549).

| 페이지 | 원문 | 목표 | 요약 | 비율 |
|---|---|---|---|---|
| dependencies/dependencies-with-yield.md | 1995 | 499 | 684 | 0.343 |
| errors/handling-errors.md | 2244 | 561 | 831 | 0.370 |
| integrations/background-tasks.md | 1166 | 292 | 469 | 0.402 |
| middleware/cors.md | 1212 | 303 | 665 | 0.549 |
| responses/response-headers-and-cookies.md | 1223 | 306 | 508 | 0.415 |
| responses/status-codes.md | 1472 | 368 | 566 | 0.385 |
| security/oauth2-jwt.md | 1975 | 494 | 711 | 0.360 |
| security/oauth2-password-flow.md | 2019 | 505 | 999 | 0.495 |
| security/oauth2-scopes.md | 1752 | 438 | 703 | 0.401 |

fact_notes (메모 27개 = 문서 턴 9 × sample 3): 평균 0.328, 전체 0.326, 목표 2배 초과 0개, 실패 0개.
턴별 평균 비율 0.288–0.376.

두 압축기 모두 목표(0.25)보다 길게 쓴다. 목표 2배를 넘는 출력은 presummary 1개뿐이라 "많다" 고 보지는 않았다.

## 지출

| 항목 | USD |
|---|---|
| presummary 구축 (페이지 9개, 구축 비용) | 0.0056 |
| 답변 (presummary, fact_notes 새 호출. none 은 응답 캐시 적중) | 0.0226 |
| fact_notes 메모 추출 | 0.0112 |
| 채점 (새 답변, 상한) | 0.0405 |
| 합계 | 약 0.080 |

## 한계

- 시나리오 3개, sample 3. 정확도 차이는 한 턴(mt01 턴 6)에 몰려 있어 시나리오가 늘면 결과가 바뀔 수 있다.
- none 행: 새 run 의 none 은 전부 응답 캐시 적중이지만 81개 중 6개가 기존 run 행과 답변 글자가 다르다 (같은 요청 해시, 모두 1.0 점).
  표는 기존 run 의 none 을 기준으로 썼다.
  원인은 응답 캐시의 동시 실행 버그다 (같은 요청을 none 과 window(2) 가 동시에 보내 둘 다 호출하고 나중 응답이 캐시를 덮어씀, 지금은 수정됨).
- 기존 run(mt_20261123-233727)의 동시 중복 호출 72건 중 18건은 답이 달라, 같은 요청을 보낸 압축기와 none 의 짝지은 비교가 엄밀하지 않다.
- presummary·fact_notes 의 목표 길이 지시는 지켜지지 않는다 (실제 0.33–0.41). 비율을 더 낮게 주거나 지시문을 바꾸는 것은 다음 단계.
