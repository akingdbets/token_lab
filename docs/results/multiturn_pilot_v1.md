# 멀티턴 파일럿 v1 결과

자동 생성: `python src/multiturn/pilot_report.py` (run `mt_20261123-233727`, 캐시 검증 `mt_20261124-002939`). 표의 수치는 결과 파일에서 뽑았다.

## 설정

| 항목 | 값 |
|---|---|
| 답변 모델 | gpt-6-luna (reasoning_effort=server_default, temperature=server_default, 출력 한도 4096) |
| 채점 | deepseek-flash (per_fact) |
| 답변 지시문 | v2 (79e1fbab96c5) |
| 시나리오 | mt01_security (9턴, draft), mt02_dependencies (9턴, draft), mt03_responses (9턴, draft) |
| sample | 5 (기준 궤적 sample 0) |
| 기록 예산 | 2000, 4000, 8000 (keep_recent 1) |
| 요약 | gpt-6-luna (조건 server_default, none, 출력 한도 4096) |
| 비열등 마진 | 0.1 (부트스트랩 10000회) |
| 토크나이저 | tiktoken:o200k_base |
| 실행 구간 | concurrency 5 · trial 1350 + 체인 0 (사후 기록); concurrency 1 · trial 4 + 체인 0 (사후 기록); concurrency 5 · trial 270 + 체인 0; concurrency 5 · trial 0 + 체인 210 |
| 기준 궤적 run | `mt_20261123-232847` |

## 기준 궤적과 답변 상태

- 기준 궤적 경고 0건 (빈 답변·finish_reason=length 없음이면 0).
- 답변 잘림(finish=length) 합계 0, 빈 답변 합계 0.

## 전체 표 (none 대비)

sim = 직전 턴 접두부를 캐시 읽기로 본 비용 (주 지표), sim_write = 미스 부분을 캐시 쓰기 단가로 (luna 실측과 일치, 캐시 검증 절), nocache = 캐시 0%. 양수가 절감.

| 압축기 | 입력 절감 | 총 토큰 절감 | sim | sim_write | nocache | 접두부 공유 | 유지율 | 비열등 (턴 / 시나리오) | 추론 토큰 | 요약 호출 | 요약 비용 | 재압축 | 요약 실패율 | overflow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| none | – | – | – | – | – | 79.2% | – | – | 27.2 | – | – | – | – | – |
| window(2) | 53.8% | 52.7% | -48.6% | -58.0% | +48.6% | 18.3% | 59.3% | ✗ / ✗ | 51.6 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| window_budget(2000) | 59.5% | 57.3% | -33.2% | -36.8% | +49.0% | 30.5% | 65.2% | ✗ / ✗ | 94.0 | 0 | $0.0000 | 0 | 0.0% | 14.8% |
| window_budget(4000) | 27.3% | 25.9% | -35.9% | -38.9% | +20.8% | 63.6% | 78.2% | ✗ / ✗ | 73.4 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| window_budget(8000) | 0.0% | -0.0% | -0.0% | -0.0% | -0.0% | 79.2% | 100.0% | ✓ / ✓ | 27.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| query_select(2000) | 48.2% | 47.0% | -85.8% | -99.0% | +42.4% | 10.8% | 94.1% | ✗ / ✗ | 49.4 | 0 | $0.0000 | 0 | 0.0% | 14.8% |
| query_select(4000) | 35.1% | 34.2% | -126.1% | -144.4% | +30.9% | 10.8% | 100.0% | ✓ / ✓ | 41.6 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| query_select(8000) | 33.9% | 33.0% | -130.6% | -149.2% | +29.6% | 10.8% | 100.0% | ✓ / ✓ | 42.4 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| per_message(rule) | 16.4% | 16.1% | -27.1% | -32.2% | +15.3% | 59.0% | 100.0% | ✓ / ✓ | 26.9 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| per_message(llmlingua2) | 26.6% | 26.0% | -23.0% | -27.2% | +23.6% | 58.1% | 92.2% | ✗ / ✗ | 38.4 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| on_arrival(rule) | 19.1% | 18.9% | +14.9% | +15.3% | +18.0% | 78.8% | 100.0% | ✓ / ✓ | 26.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| on_arrival(llmlingua2) | 31.2% | 30.1% | +12.7% | +14.6% | +26.0% | 78.6% | 84.8% | ✗ / ✗ | 56.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| rolling_summary(2000)[sre=server_default] | 48.9% | 14.6% | -306.9% | -287.6% | -29.5% | 31.1% | 94.1% | ✗ / ✗ | 45.5 | 63 | $0.0449 | 0 | 0.0% | 22.2% |
| rolling_summary(2000)[sre=none] | 57.5% | 37.5% | -121.6% | -118.1% | +25.2% | 25.7% | 73.6% | ✗ / ✗ | 50.1 | 52 | $0.0155 | 0 | 0.0% | 19.3% |
| rolling_summary(4000)[sre=server_default] | 25.9% | 10.7% | -126.3% | -119.8% | -5.7% | 63.9% | 100.0% | ✓ / ✓ | 32.7 | 20 | $0.0152 | 0 | 0.0% | 0.0% |
| rolling_summary(4000)[sre=none] | 34.4% | 22.6% | -63.1% | -61.6% | +17.3% | 63.5% | 81.4% | ✗ / ✗ | 45.7 | 20 | $0.0051 | 0 | 0.0% | 0.0% |
| rolling_summary(8000)[sre=server_default] | 0.0% | -0.0% | -0.0% | -0.0% | -0.0% | 79.2% | 100.0% | ✓ / ✓ | 27.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| rolling_summary(8000)[sre=none] | 0.0% | -0.0% | -0.0% | -0.0% | -0.0% | 79.2% | 100.0% | ✓ / ✓ | 27.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| frozen_summary(2000)[sre=server_default] | 48.1% | 17.0% | -266.7% | -251.8% | -18.8% | 32.6% | 93.1% | ✗ / ✗ | 48.6 | 88 | $0.0367 | 24 | 0.0% | 22.2% |
| frozen_summary(2000)[sre=none] | 57.2% | 38.3% | -107.1% | -105.0% | +28.9% | 27.1% | 73.1% | ✗ / ✗ | 51.2 | 66 | $0.0119 | 15 | 0.0% | 18.5% |
| frozen_summary(4000)[sre=server_default] | 25.9% | 11.9% | -112.8% | -107.7% | -2.0% | 64.2% | 98.5% | ✓ / ✓ | 31.5 | 20 | $0.0129 | 0 | 0.0% | 0.0% |
| frozen_summary(4000)[sre=none] | 34.3% | 22.6% | -63.7% | -62.2% | +17.1% | 63.5% | 81.4% | ✗ / ✗ | 49.5 | 20 | $0.0049 | 0 | 0.0% | 0.0% |
| frozen_summary(8000)[sre=server_default] | 0.0% | -0.0% | -0.0% | -0.0% | -0.0% | 79.2% | 100.0% | ✓ / ✓ | 27.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| frozen_summary(8000)[sre=none] | 0.0% | -0.0% | -0.0% | -0.0% | -0.0% | 79.2% | 100.0% | ✓ / ✓ | 27.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| on_arrival(rule)>frozen_summary(8000)[sre=server_default] | 19.1% | 18.9% | +14.9% | +15.3% | +18.0% | 78.8% | 100.0% | ✓ / ✓ | 26.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |
| on_arrival(rule)>frozen_summary(8000)[sre=none] | 19.1% | 18.9% | +14.9% | +15.3% | +18.0% | 78.8% | 100.0% | ✓ / ✓ | 26.2 | 0 | $0.0000 | 0 | 0.0% | 0.0% |

요약 호출이 0회인 요약형 조건 (기록이 예산을 넘은 적이 없어 요약 단계가 한 번도 돌지 않음. 결과는 요약 없는 앞 단계와 같다): `rolling_summary(8000)[sre=server_default]`, `rolling_summary(8000)[sre=none]`, `frozen_summary(8000)[sre=server_default]`, `frozen_summary(8000)[sre=none]`, `on_arrival(rule)>frozen_summary(8000)[sre=server_default]`, `on_arrival(rule)>frozen_summary(8000)[sre=none]`.

none 대 none 변동폭 (sample 0 대 나머지, 108쌍): 정확도 차이 +0.000, 95% CI [+0.000, +0.000].

## frozen 대 rolling 접두부 공유율

| 예산 | 요약 추론 | rolling | frozen | frozen 이 높은가 |
|---|---|---|---|---|
| 2000 | none | 25.7% | 27.1% | ✓ |
| 2000 | server_default | 31.1% | 32.6% | ✓ |
| 4000 | none | 63.5% | 63.5% | ✗ |
| 4000 | server_default | 63.9% | 64.2% | ✓ |
| 8000 | none | 79.2% | 79.2% | ✗ |
| 8000 | server_default | 79.2% | 79.2% | ✗ |

## turn_type 별 정확도 (not_found 비율)

| 압축기 | new | followup | recall | synthesis |
|---|---|---|---|---|
| none | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| window(2) | 1.00 (0%) | 1.00 (0%) | 0.00 (100%) | 0.17 (83%) |
| window_budget(2000) | 1.00 (0%) | 0.97 (3%) | 0.07 (93%) | 0.40 (57%) |
| window_budget(4000) | 1.00 (0%) | 1.00 (0%) | 0.33 (67%) | 0.68 (27%) |
| window_budget(8000) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| query_select(2000) | 1.00 (0%) | 1.00 (0%) | 0.83 (17%) | 0.90 (7%) |
| query_select(4000) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| query_select(8000) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| per_message(rule) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| per_message(llmlingua2) | 1.00 (0%) | 0.82 (0%) | 0.83 (17%) | 1.00 (0%) |
| on_arrival(rule) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| on_arrival(llmlingua2) | 0.78 (11%) | 0.82 (0%) | 0.83 (17%) | 1.00 (0%) |
| rolling_summary(2000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 0.77 (23%) | 0.97 (3%) |
| rolling_summary(2000)[sre=none] | 1.00 (0%) | 0.90 (10%) | 0.30 (70%) | 0.61 (33%) |
| rolling_summary(4000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| rolling_summary(4000)[sre=none] | 1.00 (0%) | 1.00 (0%) | 0.27 (73%) | 0.89 (0%) |
| rolling_summary(8000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| rolling_summary(8000)[sre=none] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| frozen_summary(2000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 0.80 (20%) | 0.89 (10%) |
| frozen_summary(2000)[sre=none] | 1.00 (0%) | 0.90 (10%) | 0.30 (70%) | 0.59 (37%) |
| frozen_summary(4000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 0.93 (7%) |
| frozen_summary(4000)[sre=none] | 1.00 (0%) | 1.00 (0%) | 0.27 (73%) | 0.89 (0%) |
| frozen_summary(8000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| frozen_summary(8000)[sre=none] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| on_arrival(rule)>frozen_summary(8000)[sre=server_default] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |
| on_arrival(rule)>frozen_summary(8000)[sre=none] | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) | 1.00 (0%) |

## 정확도가 1.0 아래로 떨어진 턴

평균 정확도는 sample 5개 평균 (맞은 sample 포함). NOT FOUND 는 그중 NOT FOUND 답변 수.

| 시나리오 | 턴 | turn_type | 압축기 | 평균 정확도 | 틀린 sample | NOT FOUND | 요약 실패 |
|---|---|---|---|---|---|---|---|
| mt01_security | 4 | recall | frozen_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt01_security | 4 | recall | frozen_summary(4000)[sre=none] | 0.20 | 4 | 4 | 0 |
| mt01_security | 4 | recall | on_arrival(llmlingua2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 4 | recall | per_message(llmlingua2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 4 | recall | rolling_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt01_security | 4 | recall | rolling_summary(4000)[sre=none] | 0.20 | 4 | 4 | 0 |
| mt01_security | 4 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 4 | recall | window_budget(2000) | 0.20 | 4 | 4 | 0 |
| mt01_security | 4 | recall | window_budget(4000) | 0.00 | 5 | 5 | 0 |
| mt01_security | 6 | synthesis | frozen_summary(2000)[sre=none] | 0.53 | 5 | 1 | 0 |
| mt01_security | 6 | synthesis | frozen_summary(2000)[sre=server_default] | 0.73 | 2 | 1 | 0 |
| mt01_security | 6 | synthesis | frozen_summary(4000)[sre=none] | 0.67 | 5 | 0 | 0 |
| mt01_security | 6 | synthesis | query_select(2000) | 0.40 | 5 | 2 | 0 |
| mt01_security | 6 | synthesis | rolling_summary(2000)[sre=none] | 0.67 | 5 | 0 | 0 |
| mt01_security | 6 | synthesis | rolling_summary(4000)[sre=none] | 0.67 | 5 | 0 | 0 |
| mt01_security | 6 | synthesis | window(2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 6 | synthesis | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt01_security | 6 | synthesis | window_budget(4000) | 0.00 | 5 | 5 | 0 |
| mt01_security | 7 | synthesis | frozen_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 7 | synthesis | frozen_summary(2000)[sre=server_default] | 0.60 | 2 | 2 | 0 |
| mt01_security | 7 | synthesis | frozen_summary(4000)[sre=none] | 0.70 | 3 | 0 | 0 |
| mt01_security | 7 | synthesis | frozen_summary(4000)[sre=server_default] | 0.60 | 2 | 2 | 0 |
| mt01_security | 7 | synthesis | rolling_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 7 | synthesis | rolling_summary(2000)[sre=server_default] | 0.80 | 1 | 1 | 0 |
| mt01_security | 7 | synthesis | rolling_summary(4000)[sre=none] | 0.70 | 3 | 0 | 0 |
| mt01_security | 7 | synthesis | window(2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 7 | synthesis | window_budget(2000) | 0.60 | 3 | 1 | 0 |
| mt01_security | 7 | synthesis | window_budget(4000) | 0.90 | 1 | 0 | 0 |
| mt01_security | 8 | recall | frozen_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | frozen_summary(2000)[sre=server_default] | 0.40 | 3 | 3 | 0 |
| mt01_security | 8 | recall | frozen_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | rolling_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | rolling_summary(2000)[sre=server_default] | 0.80 | 1 | 1 | 0 |
| mt01_security | 8 | recall | rolling_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt01_security | 8 | recall | window_budget(4000) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 1 | followup | on_arrival(llmlingua2) | 0.50 | 5 | 0 | 0 |
| mt02_dependencies | 1 | followup | per_message(llmlingua2) | 0.50 | 5 | 0 | 0 |
| mt02_dependencies | 2 | followup | frozen_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 2 | followup | on_arrival(llmlingua2) | 0.90 | 1 | 0 | 0 |
| mt02_dependencies | 2 | followup | per_message(llmlingua2) | 0.90 | 1 | 0 | 0 |
| mt02_dependencies | 2 | followup | rolling_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 2 | followup | window_budget(2000) | 0.80 | 1 | 1 | 0 |
| mt02_dependencies | 6 | recall | frozen_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 6 | recall | frozen_summary(4000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 6 | recall | rolling_summary(2000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 6 | recall | rolling_summary(4000)[sre=none] | 0.40 | 3 | 3 | 0 |
| mt02_dependencies | 6 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 6 | recall | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 6 | recall | window_budget(4000) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 7 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 7 | recall | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 8 | synthesis | window(2) | 0.00 | 5 | 5 | 0 |
| mt02_dependencies | 8 | synthesis | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 0 | new | on_arrival(llmlingua2) | 0.00 | 5 | 0 | 0 |
| mt03_responses | 1 | followup | on_arrival(llmlingua2) | 0.50 | 4 | 0 | 0 |
| mt03_responses | 1 | followup | per_message(llmlingua2) | 0.50 | 4 | 0 | 0 |
| mt03_responses | 2 | new | on_arrival(llmlingua2) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | frozen_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | frozen_summary(2000)[sre=server_default] | 0.60 | 2 | 2 | 0 |
| mt03_responses | 5 | recall | frozen_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | query_select(2000) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | rolling_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | rolling_summary(2000)[sre=server_default] | 0.60 | 2 | 2 | 0 |
| mt03_responses | 5 | recall | rolling_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | window_budget(2000) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 5 | recall | window_budget(4000) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 6 | synthesis | window(2) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 6 | synthesis | window_budget(2000) | 0.40 | 3 | 3 | 0 |
| mt03_responses | 7 | recall | frozen_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 7 | recall | frozen_summary(2000)[sre=server_default] | 0.80 | 1 | 1 | 0 |
| mt03_responses | 7 | recall | frozen_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 7 | recall | rolling_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 7 | recall | rolling_summary(2000)[sre=server_default] | 0.20 | 4 | 4 | 0 |
| mt03_responses | 7 | recall | rolling_summary(4000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 7 | recall | window(2) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 7 | recall | window_budget(2000) | 0.20 | 4 | 4 | 0 |
| mt03_responses | 8 | synthesis | frozen_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 8 | synthesis | rolling_summary(2000)[sre=none] | 0.00 | 5 | 5 | 0 |
| mt03_responses | 8 | synthesis | window(2) | 0.00 | 5 | 5 | 0 |
| mt03_responses | 8 | synthesis | window_budget(2000) | 0.40 | 3 | 3 | 0 |
| mt03_responses | 8 | synthesis | window_budget(4000) | 0.20 | 5 | 3 | 0 |

## 압축 전후 추론 토큰

| 압축기 | none 평균 | 압축 후 평균 | 변화 | 출력 전체 평균 (none → 압축) |
|---|---|---|---|---|
| window(2) | 27.2 | 51.6 | +89.5% | 58.3 → 74.3 |
| window_budget(2000) | 27.2 | 94.0 | +245.6% | 58.3 → 119.1 |
| window_budget(4000) | 27.2 | 73.4 | +169.7% | 58.3 → 101.3 |
| window_budget(8000) | 27.2 | 27.2 | +0.0% | 58.3 → 58.3 |
| query_select(2000) | 27.2 | 49.4 | +81.6% | 58.3 → 82.9 |
| query_select(4000) | 27.2 | 41.6 | +52.8% | 58.3 → 76.0 |
| query_select(8000) | 27.2 | 42.4 | +55.9% | 58.3 → 77.6 |
| per_message(rule) | 27.2 | 26.9 | -1.1% | 58.3 → 57.9 |
| per_message(llmlingua2) | 27.2 | 38.4 | +41.2% | 58.3 → 69.6 |
| on_arrival(rule) | 27.2 | 26.2 | -3.8% | 58.3 → 57.2 |
| on_arrival(llmlingua2) | 27.2 | 56.2 | +106.5% | 58.3 → 86.7 |
| rolling_summary(2000)[sre=server_default] | 27.2 | 45.5 | +67.3% | 58.3 → 77.9 |
| rolling_summary(2000)[sre=none] | 27.2 | 50.1 | +84.3% | 58.3 → 78.6 |
| rolling_summary(4000)[sre=server_default] | 27.2 | 32.7 | +20.0% | 58.3 → 64.8 |
| rolling_summary(4000)[sre=none] | 27.2 | 45.7 | +67.8% | 58.3 → 76.2 |
| rolling_summary(8000)[sre=server_default] | 27.2 | 27.2 | +0.0% | 58.3 → 58.3 |
| rolling_summary(8000)[sre=none] | 27.2 | 27.2 | +0.0% | 58.3 → 58.3 |
| frozen_summary(2000)[sre=server_default] | 27.2 | 48.6 | +78.5% | 58.3 → 80.3 |
| frozen_summary(2000)[sre=none] | 27.2 | 51.2 | +88.2% | 58.3 → 79.5 |
| frozen_summary(4000)[sre=server_default] | 27.2 | 31.5 | +15.6% | 58.3 → 62.8 |
| frozen_summary(4000)[sre=none] | 27.2 | 49.5 | +81.8% | 58.3 → 79.9 |
| frozen_summary(8000)[sre=server_default] | 27.2 | 27.2 | +0.0% | 58.3 → 58.3 |
| frozen_summary(8000)[sre=none] | 27.2 | 27.2 | +0.0% | 58.3 → 58.3 |
| on_arrival(rule)>frozen_summary(8000)[sre=server_default] | 27.2 | 26.2 | -3.8% | 58.3 → 57.2 |
| on_arrival(rule)>frozen_summary(8000)[sre=none] | 27.2 | 26.2 | -3.8% | 58.3 → 57.2 |

기록이 잘리거나 문서가 깎이면 모델이 근거를 찾느라 추론이 늘어, 출력 비용이 입력 절감의 일부를 상쇄한다.

## llmlingua2 followup 하락 원인

`per_message(llmlingua2)` 가 실제로 압축한 범위를 trajectory 의 `messages_sent` 로 확인했다. 과거 user 메시지의 `<documentation>`
블록만 압축됐고, assistant 답변과 질문·형식 줄은 원문과 같다 (설계대로, 답변 압축 버그 아님).

| 턴 | 빠진 key_fact | 원문 | 압축본 |
|---|---|---|---|
| mt02 턴 1 | The server logs nothing about the real error | "The client still gets a `500 Internal Server Error`, but the server logs **nothing** about the real error." | "client gets 500 Server real error" (문장이 통째로 빠짐. force_tokens 에 no·not·never 는 있지만 nothing 은 없다) |
| mt03 턴 1 | Return a Response such as JSONResponse directly / not validated or filtered by the response model | "To keep using your response model *and* change the status dynamically, declare a `Response` parameter…" | "response model change status declare Response parameter" (조건이 깎임. 모델이 다른 정당한 해법인 Response 주입을 고름) |

on_arrival(llmlingua2) 는 현재 턴 문서도 압축하므로 new 턴에서도 틀린다. 예: mt03 턴 0 의 "below 200" 이 "200" 으로 깎여
"200, 204, 205, 304" 로 답했다.

## 캐시 실측 검증 (`--sequential-chains`)

응답 캐시를 끄고 턴 순서대로 한 번에 하나씩 보냈다 (시나리오 3개, sample 0, 채점 없음).

| 압축기 | 시뮬레이션 적중률 | 실측 적중률 | 실측/시뮬레이션 (턴 평균) | 실측 캐시 쓰기 토큰 | 실측 비용 | sim | sim_write | 실측 절감 | sim 절감 | sim_write 절감 |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 84.7% | 84.7% | 1.000 | 17,439 | $0.00399 | $0.00355 | $0.00399 | +0.0% | +0.0% | +0.0% |
| on_arrival(rule) | 84.6% | 98.9% | 1.167 | 913 | $0.00180 | $0.00298 | $0.00334 | +54.8% | +16.2% | +16.5% |
| per_message(rule) | 68.5% | 89.4% | 1.195 | 10,068 | $0.00295 | $0.00451 | $0.00526 | +26.1% | -26.7% | -31.8% |

### 턴별 (시뮬레이션 캐시 토큰 / 실측 cached_tokens / 실측 cache_write_tokens)

| 시나리오 | 턴 | none | on_arrival(rule) | per_message(rule) |
|---|---|---|---|---|
| mt01_security | 0 | 0 / 0 / 2184 | 0 / 1806 / 0 | 0 / 2184 / 0 |
| mt01_security | 1 | 2186 / 2184 / 58 | 1808 / 1864 / 0 | 0 / 1864 / 0 |
| mt01_security | 2 | 2243 / 2242 / 2041 | 1865 / 3690 / 0 | 1864 / 1864 / 2041 |
| mt01_security | 3 | 4285 / 4283 / 68 | 3692 / 3690 / 68 | 1870 / 3758 / 0 |
| mt01_security | 4 | 4353 / 4351 / 119 | 3760 / 3877 / 0 | 3760 / 3877 / 0 |
| mt01_security | 5 | 4469 / 4470 / 1822 | 3876 / 5396 / 0 | 3876 / 3877 / 1822 |
| mt01_security | 6 | 6294 / 6292 / 82 | 5398 / 5396 / 82 | 3885 / 5478 / 0 |
| mt01_security | 7 | 6376 / 6374 / 109 | 5480 / 5478 / 109 | 5480 / 5587 / 0 |
| mt01_security | 8 | 6485 / 6483 / 90 | 5589 / 5587 / 90 | 5589 / 5677 / 0 |
| mt02_dependencies | 0 | 0 / 0 / 2154 | 0 / 1663 / 0 | 0 / 2154 / 0 |
| mt02_dependencies | 1 | 2156 / 2154 / 51 | 1665 / 1663 / 51 | 0 / 1714 / 0 |
| mt02_dependencies | 2 | 2207 / 2205 / 91 | 1716 / 1805 / 0 | 1716 / 1805 / 0 |
| mt02_dependencies | 3 | 2296 / 2296 / 1235 | 1805 / 2738 / 0 | 1805 / 1805 / 1235 |
| mt02_dependencies | 4 | 3533 / 3531 / 85 | 2740 / 2823 / 0 | 1821 / 2823 / 0 |
| mt02_dependencies | 5 | 3616 / 3616 / 1311 | 2823 / 3886 / 0 | 2822 / 2823 / 1311 |
| mt02_dependencies | 6 | 4929 / 4927 / 66 | 3888 / 3886 / 66 | 2868 / 3952 / 0 |
| mt02_dependencies | 7 | 4995 / 4993 / 59 | 3954 / 3952 / 59 | 3954 / 4011 / 0 |
| mt02_dependencies | 8 | 5054 / 5052 / 72 | 4013 / 4011 / 72 | 4013 / 4083 / 0 |
| mt03_responses | 0 | 0 / 0 / 1624 | 0 / 1224 / 0 | 0 / 1624 / 0 |
| mt03_responses | 1 | 1626 / 1624 / 74 | 1226 / 1298 / 0 | 0 / 1298 / 0 |
| mt03_responses | 2 | 1699 / 1698 / 1343 | 1299 / 2292 / 0 | 1298 / 1298 / 1343 |
| mt03_responses | 3 | 3043 / 3041 / 69 | 2294 / 2361 / 0 | 1353 / 2361 / 0 |
| mt03_responses | 4 | 3109 / 3110 / 2316 | 2360 / 4165 / 0 | 2360 / 2361 / 2316 |
| mt03_responses | 5 | 5428 / 5426 / 90 | 4167 / 4165 / 90 | 2376 / 4255 / 0 |
| mt03_responses | 6 | 5518 / 5516 / 64 | 4257 / 4255 / 64 | 4257 / 4319 / 0 |
| mt03_responses | 7 | 5582 / 5580 / 86 | 4321 / 4319 / 86 | 4321 / 4405 / 0 |
| mt03_responses | 8 | 5668 / 5666 / 76 | 4407 / 4405 / 76 | 4407 / 4481 / 0 |

실측이 시뮬레이션보다 10토큰 넘게 적은 턴: 0개.

## 파일럿 한계

- 시나리오 3개 × 9턴 (27턴). 시나리오 군집 부트스트랩은 단위가 3개라 참고용이다.
- 기준 궤적 정확도가 27턴 모두 1.0 이고 none 대 none 변동이 0 이다 (천장 효과). 비열등 판정은 사실상 "한 번이라도 틀렸는가" 다.
- 시나리오는 초안(`status: draft`)이고 사람 검수 전이다.
- 9턴 대화의 기록은 최대 약 6.5k 토큰이라 예산 8000 의 요약형(그리고 `on_arrival(rule)>frozen_summary(8000)`)은 요약이 한 번도
  일어나지 않았다. 장기 대화용 조합을 검증하려면 더 긴 시나리오가 필요하다.
- mt03 턴 1 의 key_fact 는 "JSONResponse 를 직접 반환" 하나만 정답으로 본다. 문서에는 응답 모델을 유지하며 상태를 바꾸는
  `Response` 파라미터 주입도 정당한 해법으로 나온다. per_message(llmlingua2)·on_arrival(llmlingua2) 의 이 턴 감점 일부는
  정보 손실이 아니라 key_fact 가 다른 정당한 해법을 오답 처리한 결과다. 검수 때 key_fact 를 고친다.
- 캐시 실측 검증은 시나리오 3개 × sample 1 이고, 같은 요청이 다른 체인·이전 실행에 있으면 서버 캐시가 체인 밖에서 적중한다
  (on_arrival 은 25분 전 replay 실행분, per_message(rule) 는 직전 on_arrival 체인과 같은 요청). 그래서 실측 적중률이 시뮬레이션보다
  높게 나온 압축기가 있다. none 은 체인 밖 요청이 없어 시뮬레이션과 턴마다 2토큰 안쪽으로 맞았고, 실측 비용이 sim_write 와 같았다.
