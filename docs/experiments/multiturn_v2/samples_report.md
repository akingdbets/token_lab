# multiturn-v2 샘플 점검

자동 생성: `python src/multiturn/scenario_report.py` (API 호출 없음).

## 턴 유형 분포와 기록

| 시나리오 | 턴 | new | followup | recall | synthesis | update | same_doc | recall 거리 | 3턴 이상 synthesis | 마지막 턴 기록 | 스키마 오류 | 근거 확인 실패 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 16, 14 | 턴 13, 18 | 18,674 | 0 | 1 |
| v2_02_response_design | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 13, 15 | 턴 13, 18 | 20,935 | 0 | 0 |

근거 확인 실패 내용:

- v2_01_auth_switch 턴 6: key_entity '/' 가 근거 페이지에 없음

## closed-book (문서·대화 없이 standalone_question)

| 시나리오 | 유형 | 턴 | 맞힘 |
|---|---|---|---|
| v2_01_auth_switch | new | 8 | 3 |
| v2_01_auth_switch | followup | 2 | 2 |
| v2_01_auth_switch | update | 2 | 0 |
| v2_01_auth_switch | same_doc_new_topic | 2 | 2 |
| v2_01_auth_switch | recall | 3 | 1 |
| v2_01_auth_switch | synthesis | 2 | 2 |
| v2_01_auth_switch | **전체** | 19 | **10** |
| v2_02_response_design | new | 8 | 7 |
| v2_02_response_design | followup | 2 | 2 |
| v2_02_response_design | update | 2 | 1 |
| v2_02_response_design | same_doc_new_topic | 2 | 1 |
| v2_02_response_design | recall | 3 | 3 |
| v2_02_response_design | synthesis | 2 | 2 |
| v2_02_response_design | **전체** | 19 | **16** |

standalone_question 이 원래 질문에 없는 key_entity 를 새로 담은 턴 (답 누설 의심):

| 시나리오 | 턴 | 유형 | 새로 담은 key_entity | closed-book 맞힘 |
|---|---|---|---|---|
| v2_01_auth_switch | 2 | followup | WWW-Authenticate, 0.122.0 | 예 |
| v2_01_auth_switch | 3 | new | HS256 | 아니오 |
| v2_01_auth_switch | 4 | update | OAuth2PasswordBearer | 아니오 |
| v2_01_auth_switch | 5 | new | Response, httponly=True, secure=True | 예 |
| v2_01_auth_switch | 6 | followup | Response | 예 |
| v2_01_auth_switch | 7 | same_doc_new_topic | secrets.compare_digest | 예 |
| v2_01_auth_switch | 8 | new | CORSMiddleware | 아니오 |
| v2_01_auth_switch | 9 | recall | X-API-Key | 예 |
| v2_01_auth_switch | 12 | new | WWW-Authenticate | 아니오 |
| v2_01_auth_switch | 13 | synthesis | response_model, http://localhost:8080 | 예 |
| v2_01_auth_switch | 17 | recall | sub | 아니오 |
| v2_01_auth_switch | 18 | synthesis | get_identity, X-API-Key, CORS | 예 |
| v2_02_response_design | 3 | new | Response, response_model | 예 |
| v2_02_response_design | 4 | update | Response | 예 |
| v2_02_response_design | 9 | recall | 200, 201 | 예 |
| v2_02_response_design | 12 | new | response_description | 예 |
| v2_02_response_design | 13 | synthesis | 200, 201, X-Cat-Dog, alone in the world, 404, responses | 예 |
| v2_02_response_design | 14 | same_doc_new_topic | PlainTextResponse | 예 |
| v2_02_response_design | 16 | recall | X-Cat-Dog, alone in the world | 예 |
| v2_02_response_design | 18 | synthesis | 200, 201, Response, 404, message, Item not found | 예 |

## 비율 압축 강도의 overflow (기록 4k 이상 턴)

예산 = ⌈r × 과거 기록⌉. 최근 1턴(keep_recent)만으로 예산을 넘으면 overflow. 과거 답변 자리에 참고 정답을 넣어 셌다.

| 시나리오 | 센 턴 | r25 | r50 | r75 |
|---|---|---|---|---|
| v2_01_auth_switch | 17 | 12% | 6% | 0% |
| v2_02_response_design | 16 | 12% | 0% | 0% |

## confusable 태그 key_fact

| 시나리오 | 턴 | key_fact |
|---|---|---|
| v2_01_auth_switch | 0 | OAuth2PasswordBearer extracts the bearer token as a string. |
| v2_01_auth_switch | 0 | Login uses username/password form fields, and the token response contains access_token and token_type="bearer". |
| v2_01_auth_switch | 2 | The default missing-key response is 401 Not authenticated with WWW-Authenticate: APIKey. |
| v2_01_auth_switch | 2 | The built-in status changed from 403 to 401 in FastAPI 0.122.0. |
| v2_01_auth_switch | 3 | Expired tokens and unknown users receive the same 401 with WWW-Authenticate: Bearer as other invalid credentials. |
| v2_01_auth_switch | 4 | HTTPBearer returns HTTPAuthorizationCredentials, whereas OAuth2PasswordBearer returns a token string. |
| v2_01_auth_switch | 7 | A rejected Basic login should return 401 with WWW-Authenticate: Basic so browsers re-prompt. |
| v2_01_auth_switch | 8 | http://localhost:8080 and http://localhost are different origins because port is part of the origin. |
| v2_01_auth_switch | 9 | The gateway arrangement uses HTTPBearer, whose credentials member contains the token. |
| v2_01_auth_switch | 10 | Header() converts underscores to hyphens by default. |
| v2_01_auth_switch | 12 | The central checker explicitly compares required scopes with token scopes and raises 401 Not enough permissions with a scope-bearing Bearer challenge when one is missing. |
| v2_01_auth_switch | 14 | Directly returning JSONResponse bypasses response_model validation and filtering. |
| v2_01_auth_switch | 15 | A local HTTPBearer subclass can restore 403 by returning an HTTPException from make_not_authenticated_error(). |
| v2_01_auth_switch | 16 | Username/password were form fields, and the JSON response required access_token and token_type="bearer". |
| v2_01_auth_switch | 17 | Expired tokens and unknown users share the same 401 response and Bearer challenge. |
| v2_02_response_design | 1 | An explicit response_model takes priority over the return annotation. |
| v2_02_response_design | 2 | response_model_exclude_unset omits unset fields but retains explicitly set values equal to defaults. |
| v2_02_response_design | 2 | response_model_exclude_defaults omits fields whose values equal their defaults. |
| v2_02_response_design | 4 | Set the injected Response.status_code to status.HTTP_201_CREATED only for creation, leaving replacement at 200. |
| v2_02_response_design | 7 | The body-forbidden statuses are below 200, 204, 205, and 304. |
| v2_02_response_design | 8 | Invalid response-model output raises ResponseValidationError and defaults to 500 rather than the request-validation 422. |
| v2_02_response_design | 9 | The current split is 200 for replacement and 201 for creation, implemented with the injected Response status override. |
| v2_02_response_design | 10 | responses declarations only document responses and do not enforce their runtime output. |
| v2_02_response_design | 11 | Return a local JSONResponse with status 404 and content {'message': 'Item not found'} to avoid the default detail wrapper. |
| v2_02_response_design | 13 | Return the revised message-shaped 404 directly and document the additional 201 and 404 schemas with responses. |
| v2_02_response_design | 14 | An individual operation's response_class overrides the app default. |
| v2_02_response_design | 15 | jsonable_encoder returns Python structures rather than a JSON string, converting a datetime timestamp to an ISO-format string. |
| v2_02_response_design | 17 | With response_model_exclude_unset=True, omitted tax stays out but an explicitly supplied tax=10.5 remains. |
| v2_02_response_design | 18 | The final success contract is replacement=200 and creation=201 using the injected Response override. |
| v2_02_response_design | 18 | The final missing-catalog contract is 404 with {'message': 'Item not found'}, not a detail wrapper. |

## same_doc_new_topic 소제목

| 시나리오 | 턴 | source_turn | 페이지 | 첨부 때 물은 소제목 | 이번에 묻는 소제목 | 다른가 |
|---|---|---|---|---|---|---|
| v2_01_auth_switch | 7 | 1 | security/http-basic-and-api-keys.md | (머리말); API keys; Missing credentials: `auto_error` and 401 | Checking credentials safely | 예 |
| v2_01_auth_switch | 14 | 5 | responses/response-headers-and-cookies.md | 1. A `Response` parameter (recommended when returning data); `set_cookie` options | 2. Returning a `Response` directly | 예 |
| v2_02_response_design | 7 | 0 | responses/status-codes.md | Declaring the status code | Status code ranges | 예 |
| v2_02_response_design | 14 | 5 | responses/custom-responses.md | Returning a `Response` directly | Default response class | 예 |

## update 턴

| 시나리오 | 턴 | 변경 | 영향 턴 |
|---|---|---|---|
| v2_01_auth_switch | 4 | Bearer-token issuer and extraction scheme: First-party password login described by OAuth2PasswordBearer(tokenUrl="token") → Gateway-issued tokens extracted with HTTPBearer, without a documented token URL | [9] |
| v2_01_auth_switch | 11 | Authentication accepted by dashboard protected routes: Gateway-issued bearer tokens, with a possible X-API-Key alternative → session cookie first; X-API-Key only when the cookie is absent; no bearer authentication; Fallback after an invalid supplied session cookie: Not specified → Reject the request without trying the API key | [13, 18] |
| v2_02_response_design | 4 | Successful creation status: 200 for both creation and replacement → 201 for creation; 200 for replacement | [9, 13, 18] |
| v2_02_response_design | 11 | Missing-catalog error body and local implementation: Raise HTTPException for 404 with {'detail': 'Item not found'} → Return local JSONResponse for 404 with {'message': 'Item not found'} | [13, 18] |
