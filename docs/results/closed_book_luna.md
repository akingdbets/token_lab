# 문서 없이 풀기(closed-book) 재검사 — gpt-6-luna

claude-v1 평가셋은 만들 때 qwen2.5:7b 로 문서 없이 풀기 검사를 통과한 문항만 남겼다 (174문항 모두 `closed_book_ok: true`).
답변 모델을 gpt-6-luna 로 바꿨으므로 같은 검사를 gpt-6-luna 로 다시 했다. 평가셋 파일은 고치지 않았다.

**결론: gpt-6-luna 는 문서 없이도 평가셋의 66%(판정 A)를 맞힌다. 판정 B 로는 79% 가 절반 이상 맞는다.** 오염 기준(30%)을 크게 넘는다.

- 실행: `EVAL_DIR=data/evalsets/claude-v1 python src/closed_book_check.py --split all`
- 결과: `results/closed_book_luna/closed_book.jsonl` (문항별), `summary.json`, `subset_report.json` (커밋 안 함)
- 프롬프트: `dataset_builder.CLOSED_BOOK_PROMPT` 그대로 ("Answer the question from your own knowledge. Be brief. If you do not know, reply exactly: UNKNOWN")
- 답변: gpt-6-luna, temperature 서버 기본값(0 거부), seed 42, `max_completion_tokens` 2048 (dataset_builder 의 출력 한도와 같음)
- 판정 A: `grader.closed_book_knows` (평가셋 필터와 같은 기준. 짧은 답은 정답 단어가 답변에 있는지, 긴 답은 핵심 개체 절반 이상)
- 판정 B: 같은 답변을 deepseek-flash per_fact(fact_judge_v2) 로 key_facts 채점한 closed-book 정확도. UNKNOWN 이면 0. **채점은 사람 검증 전 잠정**
- git commit `59ca0b6` (main, PR #23 머지 직후)

## split x type

| split | type | n | 판정 A 문서 없이 정답 | 판정 B 평균 | 판정 B ≥ 0.5 | UNKNOWN | 빈 답변 |
|---|---|---|---|---|---|---|---|
| dev | fact | 11 | 7 (63.6%) | 0.900 | 9 (81.8%) | 0.0% | 1 |
| dev | code | 12 | 11 (91.7%) | 0.917 | 11 (91.7%) | 0.0% | 0 |
| dev | procedure | 8 | 6 (75.0%) | 0.875 | 8 (100.0%) | 0.0% | 0 |
| dev | multi | 4 | 2 (50.0%) | 0.792 | 4 (100.0%) | 0.0% | 0 |
| dev | **전체** | 35 | 26 (74.3%) | 0.887 | 32 (91.4%) | 0.0% | 1 |
| test | fact | 37 | 25 (67.6%) | 0.892 | 34 (91.9%) | 0.0% | 0 |
| test | code | 42 | 27 (64.3%) | 0.619 | 26 (61.9%) | 4.8% | 0 |
| test | procedure | 30 | 18 (60.0%) | 0.672 | 22 (73.3%) | 0.0% | 1 |
| test | multi | 30 | 19 (63.3%) | 0.741 | 23 (76.7%) | 0.0% | 2 |
| test | **전체** | 139 | 89 (64.0%) | 0.730 | 105 (75.5%) | 1.4% | 3 |
| **전체** |  | 174 | 115 (66.1%) | 0.761 | 137 (78.7%) | 1.1% | 4 |

- UNKNOWN 은 2문항(c0010, c0117)뿐이다. gpt-6-luna 는 모르는 문항에도 거의 답을 지어낸다
- **빈 답변 4건** (c0001, c0096, c0155, c0168): 생각 토큰만으로 2048 한도를 다 써서 답변 본문이 비었다 (`finish_reason=length`).
  판정 A 는 모두 "모름" 이 되고, 판정 B 에서는 뺐다 (평균·≥0.5 집계에 들어가지 않음)
- **judge 오판 발견**: 빈 답변 4건에 deepseek-flash 가 c0001·c0168 은 1.0, c0096 0.5, c0155 0.67 을 줬다.
  채점 프롬프트에 정답(reference answer)이 같이 들어가 있어 빈 답변에도 YES 를 준 것으로 보인다. 스크립트는 이제 빈 답변을 채점하지 않는다.
  judge_check_v3 라벨링에서 FP 를 볼 때 참고할 사례
- judge 응답을 못 읽은 fact 1건 (c0172 fact 0, 생각 토큰이 4096 한도를 넘음) — 그 문항은 판정 B 에서 빠짐

### 판정 A 와 판정 B 비교

| | 판정 B ≥ 0.5 | 판정 B < 0.5 | 빈 답변 |
|---|---|---|---|
| 판정 A 정답 | 109 | 6 | 0 |
| 판정 A 모름 | 28 | 27 | 4 |

- A 만 정답(6): 정답의 짧은 단어나 핵심 개체 하나가 우연히 들어간 경우 (예: c0081 정답 `main:app`, 답변 `app.main:app`). A 가 후하다
- B 만 정답(28): 다른 표현으로 맞혀 핵심 개체 문자열이 안 맞은 경우. A 가 짜다
- **두 판정 모두 문서 없이 못 푼 문항은 27개뿐** (test 25: code 15, procedure 5, fact 3, multi 2 / dev 2: code 1, fact 1)

## dev 기준선 v2 를 부분집합으로 다시 집계

`results/runs/20261019-203350/trials.jsonl` (baseline_dev_v2 run) 을 새 호출 없이 다시 집계했다 (`--subset-run`). 정확도는 잠정.

| 부분집합 | n | none | rule | rule_fm_all | 유지율 rule | 유지율 rule_fm_all |
|---|---|---|---|---|---|---|
| 전체 | 35 | 1.000 | 1.000 | 0.986 | 100.0% | 98.6% |
| 판정 A 로 푼 문항 제외 | 9 | 1.000 | 1.000 | 0.944 | 100.0% | 94.4% |
| 판정 B ≥ 0.5 문항 제외 | 3 | 1.000 | 1.000 | 1.000 | 100.0% | 100.0% |

- 판정 A 제외 9문항: c0001, c0003, c0004, c0005, c0015, c0024, c0030, c0035, c0039 (c0001 은 빈 답변이라 "모름" 으로 남음)
- 판정 B 제외 3문항: c0001, c0005, c0035
- rule_fm_all 의 하락은 c0015 한 문항(baseline_dev_v2 에서 judge 흔들림으로 판단한 문항)이고, 문항 수가 줄어 비율만 커졌다.
  9문항·3문항으로는 압축 기법 간 차이를 말할 수 없다

## 판정 B ≥ 0.5 문항 (137개)

<details>
<summary>목록 펼치기 (qid, split, type, 판정 B, 판정 A, 질문, closed-book 답변 앞부분)</summary>

| qid | split | type | 판정 B | 판정 A | 질문 | closed-book 답변 (앞부분) |
|---|---|---|---|---|---|---|
| c0002 | dev | code | 1.00 | O | In FastAPI's JWT example, how many minutes of validity does create_access_token fall back to when the caller gives no... | 15 minutes. |
| c0003 | dev | procedure | 0.75 | - | In FastAPI's JWT tutorial, what does the dependency that resolves the logged-in user do with the bearer token, step b... | It gets the bearer token from the `Authorization` header, decodes and verifies it with the configured secre... |
| c0004 | dev | fact | 1.00 | - | When a FastAPI app registers several middlewares one after another, which of them ends up wrapping all the others? | The last middleware registered wraps all the earlier ones; it is the outermost middleware. |
| c0006 | dev | procedure | 1.00 | O | In FastAPI, how do I write my own middleware that times every request and reports the duration back to the client in ... | ```python import time from fastapi import FastAPI, Request app = FastAPI() @app.middleware("http") async de... |
| c0015 | dev | multi | 0.50 | - | In FastAPI's security tutorials, what does the simple password-flow login hand back as its access token, and what doe... | The simple password-flow example returns the username as the access token; the JWT version issues an encode... |
| c0017 | dev | code | 1.00 | O | In FastAPI's JWT example, how many minutes is ACCESS_TOKEN_EXPIRE_MINUTES set to? | 30 minutes |
| c0018 | dev | fact | 1.00 | O | Below what response size, in bytes, does FastAPI's GZip middleware skip compression by default? | 500 bytes. |
| c0019 | dev | code | 1.00 | O | In FastAPI's TrustedHostMiddleware example, which wildcard host pattern is allowed in addition to example.com? | `*.example.com` |
| c0020 | dev | fact | 1.00 | O | In FastAPI, what scope value do dependencies that use yield get when none is specified? | `request` |
| c0021 | dev | fact | 1.00 | O | Which error does FastAPI raise when a request-scoped yield dependency is made to depend on a function-scoped one? | FastAPI raises a `DependencyScopeError`. |
| c0022 | dev | code | 1.00 | O | In FastAPI's example where a yield dependency converts an ownership problem into an HTTP error, which status code is ... | 400 Bad Request. |
| c0023 | dev | code | 1.00 | O | In FastAPI's yield-dependency examples, what username value does get_username hand to the path operation? | "Rick" |
| c0024 | dev | procedure | 0.50 | - | In FastAPI, how should a yield dependency handle an exception it catches so that the real error still appears in the ... | After handling or logging it, re-raise the exception with a bare `raise` so FastAPI can log and handle the ... |
| c0025 | dev | fact | 1.00 | O | When writing async FastAPI tests, which pytest marker from the AnyIO plugin makes the test function run asynchronously? | `@pytest.mark.anyio` |
| c0026 | dev | fact | 1.00 | O | When testing FastAPI with httpx.AsyncClient and ASGITransport, which package provides the LifespanManager needed for ... | `asgi-lifespan` provides `LifespanManager`. |
| c0027 | dev | code | 1.00 | O | In FastAPI's async test example, what base_url is given to AsyncClient? | `http://test` |
| c0028 | dev | code | 1.00 | O | In FastAPI's database testing example, which pool class is passed to create_engine for the in-memory SQLite test data... | StaticPool |
| c0029 | dev | procedure | 0.75 | O | In FastAPI, how do I make my tests talk to a separate in-memory database instead of the real one, using pytest fixtures? | Override the same database dependency your routes use. For SQLite, `StaticPool` keeps the in-memory databas... |
| c0030 | dev | fact | 1.00 | - | When a FastAPI dependency is overridden in tests, what decides which request parameters get read and validated? | The override function’s signature determines which request parameters FastAPI reads and validates. |
| c0031 | dev | fact | 1.00 | O | When a FastAPI WebSocket endpoint rejects or closes the connection during a test, which exception does the test clien... | `WebSocketDisconnect` (from Starlette) is raised. |
| c0032 | dev | code | 1.00 | O | In FastAPI's dependency override test example, what limit value does the replacement dependency return? | 10 |
| c0033 | dev | code | 1.00 | O | In FastAPI's WebSocket testing example, which test client method opens the connection to /ws? | `client.websocket_connect("/ws")` |
| c0034 | dev | fact | 1.00 | O | Which stricter variant of FastAPI's OAuth2 password form class requires grant_type to be password? | `OAuth2PasswordRequestFormStrict` |
| c0036 | dev | code | 1.00 | O | In FastAPI's simple password-flow example, what string does fake_hash_password put in front of the password? | `fakehashed` |
| c0037 | dev | code | 1.00 | O | In FastAPI's first bearer-token example, what does the /items/ path operation return? | It returns `{"token": token}`, where `token` is the bearer token from the request. |
| c0038 | dev | procedure | 1.00 | O | With FastAPI's OAuth2PasswordBearer, what sequence of steps happens between the frontend and the API when a user logs... | 1. The frontend sends the user’s credentials to a token endpoint, typically as form data. 2. The API verifi... |
| c0039 | dev | multi | 1.00 | - | In FastAPI's security tutorials, how does the response to a failed login at /token differ between the simple password... | The simple password-flow version returns **400 Bad Request**. The JWT version returns **401 Unauthorized** ... |
| c0040 | dev | multi | 1.00 | O | If a FastAPI test must await an async database call itself and also replace one of the app's dependencies, which clie... | Use `httpx.AsyncClient` with `ASGITransport(app=app)`. Replace the dependency by assigning an override: `ap... |
| c0145 | dev | procedure | 1.00 | O | In FastAPI, how do I write a test that actually exercises the app's lifespan startup and cleanup with the synchronous... | Use `TestClient` as a context manager; entering runs startup, and leaving runs cleanup: ```python from fast... |
| c0146 | dev | procedure | 1.00 | O | In FastAPI, how do I swap out a dependency in only some of my tests while keeping the remaining tests unaffected? | Use `app.dependency_overrides` to replace the dependency for the tests that need it, then remove the overri... |
| c0147 | dev | procedure | 1.00 | O | In FastAPI, how do I make a yield dependency's cleanup run before the response goes out rather than after? | Use a function-scoped dependency: ```python @app.get("/") def endpoint(value=Depends(my_dependency, scope="... |
| c0148 | dev | multi | 0.67 | O | In FastAPI tests, which TestClient usage does not run lifespan, and how should the app be wrapped when using httpx.As... | Using `TestClient(app)` without a `with` context does not run lifespan events. With `httpx.AsyncClient`, wr... |
| c0007 | test | fact | 1.00 | O | Starting with which FastAPI release can query validation be written with Annotated? | FastAPI 0.95.0. |
| c0008 | test | code | 1.00 | O | In FastAPI's FilterParams query model example, which two values are allowed for the ordering field? | `created_at` and `updated_at` |
| c0009 | test | fact | 0.50 | - | Apart from codes under 200 and 204, which status codes does FastAPI treat as not allowing a response body? | 304 (Not Modified). |
| c0011 | test | procedure | 1.00 | O | In FastAPI, how can an endpoint keep using its response model but reply with 201 only on the requests where it create... | Inject `Response` and set its status code only when something is created. FastAPI will still apply the endp... |
| c0012 | test | fact | 1.00 | O | According to FastAPI's container guide, roughly how long does docker compose take to stop services when the Dockerfil... | About 10 seconds. |
| c0013 | test | code | 1.00 | O | In FastAPI's Docker guide, how many worker processes does the CMD for the single-server special case start? | 4 worker processes. |
| c0014 | test | procedure | 1.00 | - | In FastAPI's Docker guide, in what order should the Dockerfile bring in files and install packages so that editing co... | Copy the dependency file first, install its packages, then copy the application code. That way, code edits ... |
| c0016 | test | multi | 1.00 | O | In FastAPI, which validation error type appears when a required query parameter is left out, and which one when an in... | A missing required query parameter produces `missing`; text like `foo` for an `int` path parameter produces... |
| c0041 | test | fact | 1.00 | O | In FastAPI, what error is raised when include_router is called with an empty prefix for a route whose own path is als... | It raises a `FastAPIError`: “Prefix and path cannot be both empty.” |
| c0042 | test | code | 1.00 | O | In FastAPI's bigger-application example, which X-Token header value does the shared get_token_header dependency accept? | `fake-super-secret-token` |
| c0043 | test | fact | 1.00 | - | When a FastAPI app is created with a lifespan function, what happens to the on_startup and on_shutdown event handlers... | They are not called. A lifespan function replaces the app’s `on_startup` and `on_shutdown` handlers. |
| c0045 | test | procedure | 1.00 | O | In FastAPI, how do I load a shared resource once when the application starts and release it when the application stops? | Use a lifespan context manager to initialize the resource at startup and release it at shutdown: ```python ... |
| c0046 | test | fact | 1.00 | O | What text does FastAPI use for an operation's response_description when you do not set one? | Successful Response |
| c0047 | test | code | 1.00 | O | In FastAPI's OpenAPI extension example using openapi_extra, what value is assigned to the x-aperture-labs-portal key? | "blue" |
| c0048 | test | procedure | 1.00 | O | In FastAPI, how can I keep internal notes such as Sphinx :param: lines in an endpoint's docstring from showing up in ... | Add a form-feed character (`\f`) before the internal notes. FastAPI uses only the docstring text before it ... |
| c0049 | test | fact | 1.00 | O | When FastAPI settings read a .env file, which source wins if the same variable is also set in the real environment? | The real environment variable wins over the value in the `.env` file. |
| c0050 | test | code | 1.00 | O | In FastAPI's settings test example, which admin email does the overriding Settings object use? | `testing_admin@example.com` |
| c0051 | test | procedure | 1.00 | O | In FastAPI, how should application settings be provided so they are built only once and can be replaced in tests? | Define a cached settings dependency with `@lru_cache` and inject it using `Depends(get_settings)`. In tests... |
| c0053 | test | code | 1.00 | O | In FastAPI's Jinja2 example, which template file is rendered for the /items/{id} route? | `item.html` |
| c0054 | test | procedure | 1.00 | O | In FastAPI, what do I need to do to return an HTML page rendered from a Jinja2 template? | Install Jinja2 (`pip install jinja2`), configure a template directory, and return a `TemplateResponse`: ```... |
| c0056 | test | procedure | 0.67 | O | In FastAPI, how do I run an app behind a proxy that publishes it under /api/v1 but strips that prefix before forwardi... | Set the ASGI `root_path` to `/api/v1`—for example: ```bash uvicorn main:app --root-path /api/v1 ``` Keep yo... |
| c0057 | test | multi | 1.00 | - | In FastAPI, how does including an APIRouter differ from mounting a sub-application in terms of the OpenAPI schema and... | Including an `APIRouter` adds its routes to the main FastAPI app, so they appear in the main app’s OpenAPI ... |
| c0058 | test | fact | 1.00 | O | Starting from which FastAPI version do dependencies with yield accept a scope argument in Depends? | FastAPI 0.121.0. |
| c0059 | test | code | 1.00 | O | In FastAPI's parameterized dependency example, what fixed content string is the checker instance configured with? | "bar" |
| c0060 | test | procedure | 1.00 | - | In FastAPI, how do I build one dependency implementation that can be configured with different parameters for differe... | Use a callable class: configure an instance in `__init__`, and let FastAPI call its `__call__` method for e... |
| c0061 | test | fact | 1.00 | - | What happens to the values returned by dependencies listed in a FastAPI path operation decorator's dependencies param... | They’re executed, but their return values are discarded and aren’t passed to the path operation function. |
| c0062 | test | code | 1.00 | O | In FastAPI's decorator dependencies example, which X-Key header value does verify_key accept? | `fake-super-secret-key` |
| c0063 | test | procedure | 1.00 | - | For a single FastAPI request, in what order are the dependency lists from the app, routers, decorator and function pa... | They’re combined in this order: **app-level dependencies → router dependencies (outer to inner) → decorator... |
| c0064 | test | fact | 1.00 | - | When a FastAPI dependency is declared as Annotated[SomeClass, Depends()] with no argument, what does FastAPI use as t... | FastAPI uses `SomeClass` itself as the dependency, instantiating it as needed. |
| c0065 | test | code | 1.00 | O | In FastAPI's sub-dependency example, which cookie does query_or_cookie_extractor fall back to when q is empty? | It falls back to the `last_query` cookie. |
| c0066 | test | procedure | 1.00 | - | In FastAPI, how do I avoid repeating the same Annotated dependency declaration on many endpoints? | Define a reusable type alias for the `Annotated` dependency: ```python CommonDep = Annotated[CommonParams, ... |
| c0067 | test | fact | 1.00 | O | Starting with which FastAPI version do the built-in security classes answer missing or invalid credentials with 401 i... | FastAPI 0.122.0. |
| c0068 | test | code | 1.00 | O | In FastAPI's custom exception handler example, which status code does the UnicornException handler respond with? | 418 |
| c0073 | test | fact | 1.00 | - | According to FastAPI's HTTPS guide, roughly how long are Let's Encrypt certificates valid? | About 90 days (roughly three months). |
| c0074 | test | code | 1.00 | O | Which single command does FastAPI's cloud guide use to deploy an app to FastAPI Cloud? | `fastapi deploy` |
| c0075 | test | procedure | 0.50 | - | In a typical FastAPI HTTPS deployment, what does the TLS termination proxy do with each request, step by step? | 1. Accepts the client’s HTTPS connection and completes the TLS handshake using its certificate. 2. Decrypts... |
| c0076 | test | fact | 1.00 | O | Which FastAPI install extra provides the standard dependencies but leaves out the FastAPI Cloud CLI? | `fastapi[standard-no-fastapi-cloud-cli]` |
| c0078 | test | fact | 1.00 | O | What value does the fastapi dev command give FASTAPI_ENV when that variable is not already set? | `development` |
| c0079 | test | code | 1.00 | O | In FastAPI's environment variable example, what fallback value does os.getenv return when MY_NAME is not set? | World |
| c0080 | test | fact | 1.00 | O | Which OpenAPI version does FastAPI's generated schema use by default? | FastAPI uses OpenAPI 3.1.0 by default. |
| c0082 | test | procedure | 1.00 | O | In FastAPI, how can I make plain fastapi dev and fastapi run find my app without passing a file path each time? | Add an entrypoint to your project’s `pyproject.toml`: ```toml [tool.fastapi] entrypoint = "app.main:app" ``... |
| c0083 | test | fact | 1.00 | O | Which function does FastAPI use to run plain def path operations in an external threadpool? | `run_in_threadpool` from `starlette.concurrency`. |
| c0084 | test | code | 1.00 | O | In FastAPI's Pydantic type example, what default value does the name field of User have? | The default value is `"John Doe"`. |
| c0085 | test | code | 1.00 | O | In FastAPI's background-task example that also uses a dependency, what text does get_query log when a q value is sent? | It logs `found query: {q}\n`—with the sent value substituted for `{q}`. |
| c0086 | test | fact | 1.00 | O | Which package do FastAPI's docs suggest as the replacement for Starlette's deprecated GraphQLApp when using Graphene? | `starlette-graphene3` |
| c0087 | test | code | 1.00 | O | In FastAPI's Strawberry GraphQL example, what age does the user resolver return? | 100 |
| c0088 | test | procedure | 0.67 | O | In FastAPI, how do I send the built-in OpenTelemetry data to a monitoring service over OTLP? | FastAPI doesn’t emit OpenTelemetry data by default. Install the instrumentation and OTLP exporter, then run... |
| c0089 | test | fact | 1.00 | O | In FastAPI's SQLModel tutorial, what is the largest page size the hero list endpoint allows? | 100 heroes. |
| c0090 | test | code | 1.00 | O | In FastAPI's SQLModel example, what is the SQLite database file named? | `database.db` |
| c0091 | test | procedure | 0.75 | O | In FastAPI with SQLModel, how do I write a PATCH endpoint that changes only the fields the client actually sent? | Use a separate update model with optional fields, then dump only fields the client supplied: ```python from... |
| c0092 | test | fact | 1.00 | - | Why are authentication tokens for FastAPI WebSocket endpoints usually sent as a query parameter or a cookie? | Browsers’ WebSocket API doesn’t let clients set arbitrary headers such as `Authorization`. Tokens are there... |
| c0093 | test | code | 1.00 | O | In FastAPI's WebSocket dependency example, which close code constant is raised when neither a session cookie nor a to... | `status.WS_1008_POLICY_VIOLATION` |
| c0094 | test | fact | 1.00 | O | What validation error type does FastAPI report when a request body contains malformed JSON? | `json_invalid` |
| c0097 | test | fact | 1.00 | O | For how many seconds does FastAPI's CORSMiddleware let browsers cache preflight responses by default? | 600 seconds |
| c0098 | test | code | 1.00 | O | In FastAPI's CORS example, which localhost origin with an explicit port is in the allowed list? | http://localhost:8080 |
| c0102 | test | fact | 1.00 | - | When a FastAPI response model is a union of several models, which model should be listed first? | List the most specific model first, since union validation may match the first compatible model. |
| c0104 | test | procedure | 0.50 | - | In FastAPI, how do I partially update a stored Pydantic item so that fields the client did not send keep their stored... | For a PATCH endpoint, dump only fields the client supplied, then apply them to the stored model: ```python ... |
| c0105 | test | code | 1.00 | O | In FastAPI's response_model_exclude example for public item data, which field is left out? | The `tax` field. |
| c0107 | test | multi | 1.00 | O | For a partial update in FastAPI, which call applies only the sent fields to a stored Pydantic model, and which call d... | Use `stored_model.model_copy(update=update_data)` for a Pydantic model. For a SQLModel database row, use `d... |
| c0108 | test | fact | 1.00 | O | Starting with which FastAPI version can webhooks be documented in the OpenAPI schema? | FastAPI 0.99.0. |
| c0109 | test | code | 1.00 | O | In FastAPI's custom OpenAPI schema example, what version string is passed to get_openapi? | `2.5.0` |
| c0111 | test | fact | 1.00 | - | Which SDK generator do FastAPI's docs describe as purpose-built for TypeScript? | Hey API. |
| c0114 | test | fact | 1.00 | O | What is the default value of the version parameter for an API's metadata in FastAPI? | The default `version` is `"0.1.0"`. |
| c0116 | test | procedure | 0.75 | O | In FastAPI, how do I serve Swagger UI and ReDoc with JavaScript and CSS files hosted by my own server instead of a CDN? | Disable FastAPI’s default docs routes, serve the assets locally with `StaticFiles`, and pass their URLs to ... |
| c0118 | test | procedure | 0.67 | O | In FastAPI, how do I offer several named request examples for one endpoint that users can pick from a dropdown in Swa... | Use `Body(openapi_examples=...)` and provide a named mapping of examples: ```python from fastapi import Bod... |
| c0119 | test | fact | 1.00 | O | What validation error type does FastAPI return when a form model forbids extra fields and the client sends one anyway? | `extra_forbidden` (HTTP 422). |
| c0120 | test | code | 1.00 | O | In FastAPI's upload example that reads the file as bytes, under which key is the file's length returned? | `file_size` |
| c0121 | test | fact | 1.00 | O | Why can't the Try it out button in FastAPI's docs UI send values for cookie parameters? | Browsers prevent JavaScript from manually setting the `Cookie` header. Since FastAPI’s Try it out UI runs i... |
| c0122 | test | code | 1.00 | O | In FastAPI's duplicate header example, which header's repeated values are collected into a list? | `X-Token` (its repeated values are collected into a list). |
| c0123 | test | procedure | 0.67 | O | In FastAPI, how do I read a header whose name contains underscores exactly as the client sends it, without turning un... | Use `Header(convert_underscores=False)`: ```python from fastapi import FastAPI, Header app = FastAPI() @app... |
| c0124 | test | fact | 1.00 | - | When a FastAPI endpoint has more than one body parameter, what are the keys of the expected JSON object? | The JSON object’s keys are the body parameter names. |
| c0125 | test | code | 1.00 | O | In FastAPI's body Field example, what max_length is set on the item description? | 300 |
| c0126 | test | procedure | 1.00 | O | In FastAPI, how do I make clients wrap a single model body inside a key named after the parameter? | Use `Body(embed=True)` on the parameter: ```python from fastapi import Body @app.put("/items") async def up... |
| c0127 | test | code | 1.00 | O | In FastAPI's per-router timing example, which response header does TimedRoute add? | `X-Response-Time` |
| c0129 | test | fact | 1.00 | O | For a FastAPI {file_path:path} parameter, how is a value that itself starts with a slash written in the URL? | Use a double slash after the route prefix: `/files//home/johndoe/myfile.txt`. The captured value is `/home/... |
| c0130 | test | code | 1.00 | O | In FastAPI's Enum path parameter example, what message is returned for the lenet model? | “LeCNN all the images” |
| c0131 | test | fact | 1.00 | O | Which two FastAPI JSON response classes are deprecated because a response model already gives the same Rust-level ser... | `ORJSONResponse` and `UJSONResponse`. |
| c0133 | test | procedure | 1.00 | O | In FastAPI, how do I make every path operation return HTML by default while letting individual endpoints choose somet... | Set `default_response_class` on the app, then override it per endpoint: ```python from fastapi import FastA... |
| c0134 | test | fact | 1.00 | O | What is the default samesite setting used by Response.set_cookie in FastAPI? | `lax` |
| c0136 | test | fact | 1.00 | O | How often does FastAPI send a keep-alive ping comment on an idle Server-Sent Events stream? | Every 15 seconds by default. |
| c0138 | test | procedure | 0.67 | O | In FastAPI, how do I make authentication optional by accepting either an API key header or a bearer token? | Set `auto_error=False` on both security schemes, then handle whichever credential is present: ```python fro... |
| c0139 | test | fact | 0.50 | O | In FastAPI's OAuth2 scopes example, which scopes does get_current_user end up requiring for the /users/me/items/ path... | It requires both `items` and `me` scopes. |
| c0140 | test | code | 1.00 | O | In FastAPI's OAuth2 scopes example, what description is given to the items scope? | “Read items.” |
| c0141 | test | procedure | 0.50 | O | In FastAPI, how do I check a token's OAuth2 scopes for all endpoints in one central dependency? | Use one central dependency that accepts `SecurityScopes`, validates the token, then checks its scopes. Decl... |
| c0142 | test | fact | 1.00 | O | In FastAPI's extended testing example, which status code is expected when creating an item that already exists? | 409 Conflict |
| c0144 | test | multi | 0.67 | O | Using FastAPI's injected Response parameter, how do the docs set the X-Cat-Dog header in one example and switch the s... | Set `response.headers["X-Cat-Dog"] = "alone in the world"`; for the other example, set `response.status_cod... |
| c0149 | test | multi | 1.00 | O | Which earlier framework does FastAPI credit for its dependency injection idea, and how do you force such a dependency... | FastAPI credits **Angular**; pass `use_cache=False` to `Depends`, for example `Depends(get_dependency, use_... |
| c0150 | test | multi | 1.00 | - | Which proxy is bundled in the Full Stack FastAPI Template, and what can that proxy do about TLS certificates by itself? | It bundles Traefik, which can automatically obtain and renew TLS certificates through Let’s Encrypt. |
| c0153 | test | multi | 0.50 | O | What text documents an operation's main response when no response_description is given, and which status codes make F... | The default response description is **“Successful Response.”** FastAPI sends an empty body for **1xx status... |
| c0154 | test | multi | 0.50 | - | How does serving a built SPA with app.frontend() differ from mounting a Flask app under /v1 in whether FastAPI routes... | `app.frontend()` serves the SPA as a fallback, so FastAPI routes can match first. A Flask mount at `/v1` fo... |
| c0156 | test | multi | 1.00 | O | Behind a TLS proxy, which flag do the Docker docs add to the container command so forwarded headers are trusted, and ... | Use `--proxy-headers` to enable forwarded-header handling, and `--forwarded-allow-ips` to specify trusted p... |
| c0157 | test | multi | 1.00 | - | When a class is the dependency versus a configured instance of a class, which method's signature does FastAPI inspect... | For a class dependency, FastAPI inspects `__init__`; for a configured instance, it inspects `__call__`. |
| c0159 | test | multi | 1.00 | O | In a FastAPI WebSocket endpoint, which exception should a dependency raise to reject a missing token, and which defau... | Raise `WebSocketException` (typically with code `WS_1008_POLICY_VIOLATION`). FastAPI’s default `websocket_r... |
| c0160 | test | multi | 0.67 | O | Why do the docs say to register HTTP error handlers for Starlette's exception class, and where do exception handlers ... | Starlette’s `HTTPException` is the common base class: FastAPI’s `HTTPException` subclasses it, so a handler... |
| c0161 | test | multi | 0.67 | - | To include the raw request body in a 422 error, what does the custom APIRoute approach read, and what simpler handler... | The custom `APIRoute` reads the raw body with `await request.body()`. A simpler `RequestValidationError` ha... |
| c0162 | test | multi | 0.50 | O | Which FastAPI telemetry setting creates a child span for each background task, and in what order do those tasks execute? | Set `instrument_background_tasks=True`. Each background task gets a child span, and tasks run sequentially ... |
| c0163 | test | multi | 1.00 | O | How does a FastAPI WebSocket endpoint learn that the client went away, and how does a reconnecting Server-Sent Events... | A FastAPI WebSocket endpoint learns the client disconnected when a receive or send raises `WebSocketDisconn... |
| c0164 | test | multi | 0.67 | O | Which internal step validates an endpoint's return value against its response field, and how do you keep a Response \... | FastAPI’s `serialize_response()` validates the returned value against the response field. To keep `Response... |
| c0165 | test | multi | 0.50 | O | If a regenerated TypeScript client breaks because the schema now has Item-Input and Item-Output, which app setting re... | Set `FastAPI(separate_input_output_schemas=False)`. Generate the client with `npx openapi-typescript http:/... |
| c0166 | test | multi | 1.00 | O | When jsonable_encoder converts a set field, what does it become, and how does the OpenAPI schema mark a set-typed field? | A set becomes a list. Its OpenAPI schema is an array marked `uniqueItems: true`. |
| c0167 | test | multi | 0.67 | O | If an endpoint switches to 201 by setting status_code on an injected Response, is its return value still filtered by ... | Yes. The response model still filters the returned value; use `response_model_exclude_unset=True` to omit f... |
| c0170 | test | multi | 1.00 | - | How does FastAPI collect every value of a header that is sent several times, and which query values count as True for... | Declare the header as a list, e.g. `x_token: list[str] = Header()`, to collect repeated values. For a `bool... |
| c0171 | test | multi | 1.00 | O | If you build a Response object yourself, which length header is added for you, and which set_cookie flag keeps the co... | `Content-Length` is added automatically; use `set_cookie(..., httponly=True)` to keep the cookie inaccessib... |
| c0173 | test | multi | 1.00 | - | Where is Swagger UI served by default when running fastapi dev, and how would you move it to /documentation while dis... | Swagger UI is served at `/docs` by default (for example, `http://127.0.0.1:8000/docs`). Move it and disable... |
| c0174 | test | multi | 1.00 | O | When posting a Pydantic model through TestClient's json= argument, which model method can stand in for jsonable_encod... | Use `model.model_dump(mode="json")`; `jsonable_encoder` converts a `timedelta` to its total seconds as a fl... |

</details>

## API 사용 토큰 (서버 보고값)

| | 호출 | 입력 | 출력 |
|---|---|---|---|
| 답변 gpt-6-luna | 174 | 9,378 | 52,747 |
| 채점 deepseek-flash | 309 | 78,577 | 45,517 (생각 토큰 포함) |

- 답변 출력이 실행 전 예상(0.5~1.5만)의 약 3.5배였다. 짧게 답하라는 프롬프트인데도 생각 토큰을 쓰고 (출력 중앙값 171.5 토큰, 답변 본문 중앙값 47자),
  4건은 2048 한도를 다 썼다

## 권고

**오염 비율이 기준(30%)의 두 배 이상이라, 지금 평가셋으로는 "답변 정확도 유지율" 을 압축 품질 지표로 쓰기 어렵다.** 평가셋 v2 를 만드는 쪽을 권한다.

근거
1. **유지율이 압축과 상관없이 높게 나온다.** dev 에서 문서를 아예 안 줘도 판정 B 평균이 0.887 이다.
   압축이 문맥을 다 지워도 정확도가 0.89 근처에 머물 수 있으므로, 유지율 목표(90%)는 문서 내용을 지키지 않아도 거의 채워진다
2. **기준선이 천장에 붙어 있다.** none·rule 정확도가 모두 1.000 이라 기법 간 차이가 드러나지 않는다 (baseline_dev_v2)
3. **오염을 뺀 부분집합이 너무 작다.** dev 는 판정 A 기준 9문항, 판정 B 기준 3문항, 두 판정 모두 기준 2문항만 남는다
4. 토큰 지표(절감률, 과금 절감률)와 의미 손실은 답변 모델과 무관하므로 지금 평가셋으로도 유효하다

v2 를 만들 때 판단할 것
- **필터 모델**: 평가셋 생성의 문서 없이 풀기 검사를 실제 답변 모델(gpt-6-luna)로 한다. 이번 결과로 보면 통과율은 판정 A 기준 34%, 두 판정 모두 기준 16% 이므로
  목표 문항 수의 3~6배 후보가 필요하다. 생성 비용(후보 생성 + 검증 + closed-book 호출)을 먼저 추정할 것
- **남는 type 편향**: 두 판정 모두 통과한 27문항 중 15문항이 code 다. fact·multi 는 거의 다 걸러지므로 type 별 목표 수(`--cap`)를 다시 정해야 한다
- **판정 기준**: 판정 A 는 후한 경우(6)와 짠 경우(28)가 모두 있다. 필터는 A 와 B(judge) 를 함께 쓰거나, judge 가 사람 라벨로 검증된 뒤 B 를 쓰는 편이 낫다
- **대안 (평가셋을 바꾸지 않을 경우)**: 문항마다 closed-book 정확도를 빼고 문서의 기여분만 보는 유지율
  `(압축 정확도 − closed-book 정확도) / (none 정확도 − closed-book 정확도)` 을 함께 보고하고, 오염 문항은 표시만 한다.
  다만 dev 는 none − closed-book 차이가 대부분 0 이라 분모가 작아 값이 불안정하다
