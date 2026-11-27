# multiturn-v2 샘플 점검

자동 생성: `python src/multiturn/scenario_report.py` (API 호출 없음).

생성 프롬프트: v2_01_auth_switch `['mt_scenario_gen_v2', '14ed07361f1b']`, v2_02_response_design `['mt_scenario_gen_v2', '14ed07361f1b']`

## 턴 유형 분포와 기록

| 시나리오 | 턴 | new | followup | recall | synthesis | update | same_doc | recall 거리 | 3턴 이상 synthesis | 마지막 턴 기록 | 스키마 오류 | 근거 확인 실패 | 경고 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 6, 15, 7 | 턴 13, 18 | 18,178 | 0 | 0 | 0 |
| v2_02_response_design | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 11, 15 | 턴 13, 18 | 20,727 | 0 | 0 | 0 |

스키마 오류·근거 확인 실패·경고 내용:

- 없음

## 출처와 질문 크기

| 시나리오 | key_fact doc / user | recall·synthesis 중 user | user 값을 바꾸는 update | doc 중 example 태그 | 턴당 asks 평균 (synthesis 외 최대) | 물음표 2개 이상 턴 | 턴당 key_fact 평균 (최대) |
|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 29 / 11 | 5/12 (42%) | 턴 4, 11 | 10/29 (34%) | 2.05 (2) | 3 | 2.11 (3) |
| v2_02_response_design | 30 / 9 | 5/12 (42%) | 턴 4, 11 | 11/30 (37%) | 1.89 (2) | 8 | 2.05 (3) |

asks 는 생성 모델이 적은 '묻는 사항' 목록, 물음표 수는 질문 문장에서 센 교차 확인용 값이다.

## closed-book 두 종류

- knowledge: 싱글턴 CLOSED_BOOK_PROMPT (모르면 UNKNOWN). 사전 지식으로 맞히는지.
- grounded: 실험 답변 지시문 mt_answer_v2 (NOT FOUND 규칙) 로 문서·기록 없이. **압축 결과를 오염시키는 쪽.**
- 채점 fact_judge_v3 (per_fact), 맞힘 = 정확도 1.0.

| 시나리오 | 유형 | 턴 | knowledge 맞힘 | grounded 맞힘 |
|---|---|---|---|---|
| v2_01_auth_switch | new | 8 | 5 | 1 |
| v2_01_auth_switch | followup | 2 | 1 | 0 |
| v2_01_auth_switch | update | 2 | 2 | 0 |
| v2_01_auth_switch | same_doc_new_topic | 2 | 1 | 0 |
| v2_01_auth_switch | recall | 3 | 0 | 0 |
| v2_01_auth_switch | synthesis | 2 | 0 | 0 |
| v2_01_auth_switch | **전체** | 19 | **9/19 (47%)** | **1/19 (5%)** |
| v2_02_response_design | new | 8 | 4 | 0 |
| v2_02_response_design | followup | 2 | 2 | 0 |
| v2_02_response_design | update | 2 | 0 | 0 |
| v2_02_response_design | same_doc_new_topic | 2 | 0 | 0 |
| v2_02_response_design | recall | 3 | 0 | 0 |
| v2_02_response_design | synthesis | 2 | 0 | 0 |
| v2_02_response_design | **전체** | 19 | **6/19 (32%)** | **0/19 (0%)** |

| 시나리오 | knowledge UNKNOWN | grounded NOT FOUND |
|---|---|---|
| v2_01_auth_switch | 5 | 18 |
| v2_02_response_design | 7 | 17 |

key_fact 단위 충족률 (출처별):

| 시나리오 | 검사 | source=doc | source=user |
|---|---|---|---|
| v2_01_auth_switch | knowledge | 17/29 (59%) | 6/11 (55%) |
| v2_01_auth_switch | grounded | 1/29 (3%) | 1/11 (9%) |
| v2_02_response_design | knowledge | 14/30 (47%) | 2/9 (22%) |
| v2_02_response_design | grounded | 2/30 (7%) | 0/9 (0%) |

## standalone_question 누설 (원래 질문에 없던 key_entity)

- 없음 (검사기 오류로 잡는다)

## source=user key_fact

| 시나리오 | 턴 | 유형 | key_fact |
|---|---|---|---|
| v2_01_auth_switch | 0 | new | Configure OAuth2PasswordBearer with the project's relative token URL auth/issue. |
| v2_01_auth_switch | 1 | new | Use APIKeyHeader with the project's X-Orbit-Key header name. |
| v2_01_auth_switch | 2 | followup | The browser-cookie extractor must use the project's orbit_session cookie name. |
| v2_01_auth_switch | 3 | new | Pass timedelta(minutes=23) for the project's access-token lifetime. |
| v2_01_auth_switch | 4 | update | The project's access-token lifetime is now 41 minutes, replacing 23 minutes. |
| v2_01_auth_switch | 9 | recall | The current project lifetime is 41 minutes. |
| v2_01_auth_switch | 11 | update | The browser authentication cookie is now named orbit_session_v2 rather than orbit_session. |
| v2_01_auth_switch | 13 | synthesis | The current project settings are cookie orbit_session_v2 and a 41-minute token lifetime. |
| v2_01_auth_switch | 16 | recall | The project's machine-client header is X-Orbit-Key. |
| v2_01_auth_switch | 17 | recall | The current browser authentication cookie is orbit_session_v2. |
| v2_01_auth_switch | 18 | synthesis | The project's settings are auth/issue for token issuance, X-Orbit-Key for machine keys, and orbit_session_v2 for browser authentication. |
| v2_02_response_design | 0 | new | The project's upsert route is /artifacts/{artifact_id}. |
| v2_02_response_design | 1 | new | The project uses X-Forge-Stamp and forge_ticket with a lifetime of 1380 seconds. |
| v2_02_response_design | 4 | update | The cookie remains forge_ticket, but its lifetime is now 2460 seconds. |
| v2_02_response_design | 9 | recall | The current settings are X-Forge-Stamp, forge_ticket, and 2460 seconds. |
| v2_02_response_design | 11 | update | The project header is now X-Forge-Receipt, replacing X-Forge-Stamp. |
| v2_02_response_design | 13 | synthesis | Use /artifacts/{artifact_id}, X-Forge-Receipt, and forge_ticket with max_age=2460. |
| v2_02_response_design | 16 | recall | The current custom response header is X-Forge-Receipt. |
| v2_02_response_design | 17 | recall | The current cookie is forge_ticket with a lifetime of 2460 seconds. |
| v2_02_response_design | 18 | synthesis | The active project settings are /artifacts/{artifact_id}, X-Forge-Receipt, and forge_ticket with a lifetime of 2460 seconds. |

## 비율 압축 강도의 overflow (기록 4k 이상 턴)

예산 = ⌈r × 과거 기록⌉. 최근 1턴(keep_recent)만으로 예산을 넘으면 overflow. 과거 답변 자리에 참고 정답을 넣어 셌다.

| 시나리오 | 센 턴 | r25 | r50 | r75 |
|---|---|---|---|---|
| v2_01_auth_switch | 17 | 18% | 6% | 0% |
| v2_02_response_design | 15 | 13% | 0% | 0% |

## confusable 태그 key_fact

| 시나리오 | 턴 | key_fact |
|---|---|---|
| v2_01_auth_switch | 2 | HTTPBearer returns HTTPAuthorizationCredentials with scheme and credentials fields, unlike the password-flow extractor's string. |
| v2_01_auth_switch | 3 | The helper's fallback lifetime is 15 minutes when expires_delta is not provided. |
| v2_01_auth_switch | 4 | The project's access-token lifetime is now 41 minutes, replacing 23 minutes. |
| v2_01_auth_switch | 7 | The timing-safe Basic-auth example checks stanleyjobson and swordfish. |
| v2_01_auth_switch | 8 | The example lists both HTTP and HTTPS localhost.tiangolo.com, plus http://localhost and http://localhost:8080. |
| v2_01_auth_switch | 9 | The current project lifetime is 41 minutes. |
| v2_01_auth_switch | 9 | Omitting expires_delta uses the helper's 15-minute fallback. |
| v2_01_auth_switch | 11 | The browser authentication cookie is now named orbit_session_v2 rather than orbit_session. |
| v2_01_auth_switch | 12 | The scoped example returns 401 Not enough permissions when items is missing for /users/me/items/. |
| v2_01_auth_switch | 12 | FastAPI 0.122.0 changed built-in authentication errors from 403 to 401 with a suitable WWW-Authenticate header. |
| v2_01_auth_switch | 13 | The current project settings are cookie orbit_session_v2 and a 41-minute token lifetime. |
| v2_01_auth_switch | 13 | The middleware handles preflight requests itself with 200 or 400, without passing them to endpoints. |
| v2_01_auth_switch | 16 | APIKeyHeader returns str, while HTTPBearer returns HTTPAuthorizationCredentials with a credentials field. |
| v2_01_auth_switch | 17 | The current browser authentication cookie is orbit_session_v2. |
| v2_01_auth_switch | 18 | The project's settings are auth/issue for token issuance, X-Orbit-Key for machine keys, and orbit_session_v2 for browser authentication. |
| v2_02_response_design | 1 | The injected-response example sets fakesession to fake-cookie-session-value. |
| v2_02_response_design | 4 | The cookie remains forge_ticket, but its lifetime is now 2460 seconds. |
| v2_02_response_design | 5 | exclude_unset retains explicitly set values even when they equal the default, including baz's tax of 10.5. |
| v2_02_response_design | 7 | FastAPI recognizes codes below 200 and codes 204, 205, and 304 as forbidding a response body. |
| v2_02_response_design | 8 | Output that violates the response model raises ResponseValidationError and defaults to a 500 response. |
| v2_02_response_design | 10 | The create-item example sets response_description to 'The created item', rather than the default 'Successful Response'. |
| v2_02_response_design | 11 | The project header is now X-Forge-Receipt, replacing X-Forge-Stamp. |
| v2_02_response_design | 12 | The example documents 404 with Message and explicitly returns {"message": "Item not found"}. |
| v2_02_response_design | 14 | RedirectResponse defaults to status 307. |
| v2_02_response_design | 14 | The pydantic redirect example overrides the status to 302 and returns https://docs.pydantic.dev/. |
| v2_02_response_design | 15 | The replacement example resets an omitted stored tax of 20.2 to 10.5. |
| v2_02_response_design | 16 | The current custom response header is X-Forge-Receipt. |
| v2_02_response_design | 17 | The current cookie is forge_ticket with a lifetime of 2460 seconds. |
| v2_02_response_design | 18 | Default request validation failures produce 422, while response-model validation failures produce 500. |

## same_doc_new_topic 소제목

| 시나리오 | 턴 | source_turn | 페이지 | 첨부 때 물은 소제목 | 이번에 묻는 소제목 | 다른가 |
|---|---|---|---|---|---|---|
| v2_01_auth_switch | 7 | 1 | security/http-basic-and-api-keys.md | (머리말) | Checking credentials safely | 예 |
| v2_01_auth_switch | 14 | 5 | responses/response-headers-and-cookies.md | 1. A `Response` parameter (recommended when returning data); `set_cookie` options | 2. Returning a `Response` directly | 예 |
| v2_02_response_design | 7 | 0 | responses/status-codes.md | Changing the status code per request | Status code ranges | 예 |
| v2_02_response_design | 14 | 3 | responses/custom-responses.md | Returning a `Response` directly | `RedirectResponse` | 예 |

## update 턴

| 시나리오 | 턴 | 변경 | 영향 턴 | user 값 |
|---|---|---|---|---|
| v2_01_auth_switch | 4 | Project access-token lifetime in minutes: 23 → 41 | [9, 13] | 예 |
| v2_01_auth_switch | 11 | Browser authentication cookie name: orbit_session → orbit_session_v2 | [13, 17, 18] | 예 |
| v2_02_response_design | 4 | Project cookie lifetime in seconds: 1380 → 2460 | [9, 13, 17, 18] | 예 |
| v2_02_response_design | 11 | Project custom response header name: X-Forge-Stamp → X-Forge-Receipt | [13, 16, 18] | 예 |
