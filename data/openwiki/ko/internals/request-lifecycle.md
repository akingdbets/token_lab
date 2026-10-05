---
type: architecture
title: 요청 처리 흐름(사용자 관점의 내부 구조)
description: FastAPI 앱이 ASGI 요청을 받아 응답을 보내기까지의 내부 흐름—미들웨어 스택 구성(ServerErrorMiddleware, 사용자 미들웨어, ExceptionMiddleware, AsyncExitStackMiddleware), 라우터 매칭, request_response의 두 AsyncExitStack, get_request_handler의 본문 파싱·의존성 해석·엔드포인트 실행·응답 검증/직렬화, OpenAPI 스키마 캐시—를 사용자가 디버깅에 필요한 수준으로 설명한다.
tags: [internals, request-lifecycle, routing, middleware, dependencies, serialization]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-338938fe8c8c2e10895f46fa
    resource: repo://fastapi/middleware/asyncexitstack.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 요청 처리 흐름(사용자 관점의 내부 구조)

이 페이지는 FastAPI 내부 구현 중 **사용자가 동작을 이해하고 디버깅하는 데 필요한 부분**만 정리한다. 사용법 자체는 각 주제 페이지를 참고한다.

## 큰 그림

```
ASGI 서버(Uvicorn)
  └─ FastAPI.__call__            root_path 설정, lifespan은 텔레메트리 lifespan 경유
      └─ 미들웨어 스택(build_middleware_stack)
          ServerErrorMiddleware        ← 500 / Exception 핸들러, debug 트레이스백
          ExceptionTelemetryMiddleware ← 처리되지 않은 예외 기록
          사용자 미들웨어(add_middleware / @app.middleware)
          ExceptionMiddleware          ← HTTPException, RequestValidationError 등 핸들러
          AsyncExitStackMiddleware     ← 업로드 파일 등 정리(fastapi_middleware_astack)
          └─ APIRouter                 경로 매칭(일반 라우트 → 낮은 우선순위 프론트엔드 라우트)
              └─ APIRoute.app = request_response(get_request_handler(...))
```

`FastAPI`는 `Starlette`를 상속하며, 위 미들웨어 목록은 `FastAPI.build_middleware_stack()`이 구성한다. `exception_handlers` 중 키가 `500` 또는 `Exception`인 핸들러는 가장 바깥 `ServerErrorMiddleware`로 가고, 나머지는 `ExceptionMiddleware`로 간다. 그래서 `Exception` 핸들러는 사용자 미들웨어 **바깥**에서, `HTTPException` 핸들러는 사용자 미들웨어 **안쪽**에서 동작한다([미들웨어](../middleware/middleware-and-cors.md), [오류 처리](../errors/handling-errors.md)).

## 라우팅

- `app.get()` 등은 내부 `APIRouter`에 `APIRoute`를 추가한다. `include_router()`는 경로를 복사하지 않고 원본 라우터를 포함 컨텍스트와 함께 연결하는 **라이브 포함**이다([큰 애플리케이션](../app-structure/bigger-applications.md)).
- 라우터는 등록 순서대로 라우트를 확인해 **처음으로 완전히 일치(FULL match)**하는 라우트를 실행한다. 그래서 `/users/me`처럼 고정 경로는 `/users/{user_id}`보다 **먼저** 선언해야 한다([경로 파라미터](../request/path-parameters.md)).
- 경로는 맞지만 메서드가 다르면(PARTIAL match) 405가 반환된다.
- `app.frontend()`로 등록한 프론트엔드 라우트는 일반 라우트가 모두 실패한 뒤에만 확인된다([프론트엔드](../integrations/static-files-templates-frontend.md)).

## request_response: 요청 단위 정리 스택

각 `APIRoute`의 ASGI 앱은 `request_response()`가 만든다. 이 함수는 요청마다 두 개의 `AsyncExitStack`을 연다.

```python
async with AsyncExitStack() as request_stack:          # scope["fastapi_inner_astack"]
    async with AsyncExitStack() as function_stack:     # scope["fastapi_function_astack"]
        response = await f(request)                    # 의존성 해석 + 엔드포인트 실행
    await response(scope, receive, send)               # 응답 전송
```

- `scope="function"` yield 의존성은 `function_stack`에 등록되어 **응답 전송 전**에 정리된다.
- 기본(`scope="request"`) yield 의존성은 `request_stack`에 등록되어 **응답 전송 후**(스트리밍 응답이면 스트림 종료 후) 정리된다([yield 의존성](../dependencies/dependencies-with-yield.md)).
- 응답이 전송되지 못한 채 스택이 끝나면 `FastAPIError("Response not awaited ...")`가 발생한다. yield 의존성의 `except`가 예외를 삼키고 다시 발생시키지 않은 경우가 대표적인 원인이다.
- 이 전체가 Starlette의 `wrap_app_handling_exceptions`로 감싸져, 라우트 안에서 발생한 예외가 등록된 예외 핸들러로 전달된다.

## get_request_handler: 한 요청의 처리 순서

`get_request_handler()`가 만드는 `app(request)`는 다음 순서로 동작한다.

1. **본문 읽기**
   - 폼 본문(`Form`/`File` 파라미터)이면 `await request.form()`. 폼의 업로드 파일은 `fastapi_middleware_astack`에 등록되어 요청이 끝나면 자동으로 닫힌다.
   - 그 외에는 `await request.body()`를 읽고, `Content-Type`이 `application/json` 또는 `application/*+json`이면 JSON으로 파싱한다. `Content-Type`이 없으면 `strict_content_type`이 `False`일 때만 JSON으로 파싱하고, 기본(`True`)이면 바이트로 남긴다([요청 본문](../request/request-body.md)).
   - JSON 디코딩 오류는 `json_invalid` 타입의 `RequestValidationError`(422)로, 그 밖의 파싱 오류는 `HTTPException(400, "There was an error parsing the body")`로 바뀐다.
2. **의존성 해석**(`solve_dependencies`)
   - 하위 의존성을 **먼저 재귀적으로** 해석한다. `app.dependency_overrides`에 등록된 대체 함수가 있으면 원래 의존성 대신 사용한다([테스트](../testing/testing-basics.md)).
   - 같은 요청에서 이미 계산된 의존성은 캐시에서 재사용한다(`use_cache=True` 기본).
   - yield 의존성은 컨텍스트 매니저로 감싸 해당 스코프의 exit stack에 등록하고, 일반 `def` 의존성은 스레드풀에서, `async def`는 직접 `await`한다.
   - 그다음 경로·쿼리·헤더·쿠키 파라미터, 본문 파라미터를 검증한다. `Request`, `WebSocket`, `BackgroundTasks`, `Response`, `SecurityScopes` 타입 파라미터에는 해당 객체를 주입한다.
   - 하위 의존성에서 오류가 나면 그 의존성은 호출되지 않으며, 오류가 모두 모인다.
3. **오류가 있으면** 엔드포인트를 호출하지 않고 모든 오류를 담은 `RequestValidationError`를 발생시킨다 → 기본 핸들러가 422 응답.
4. **엔드포인트 실행**: `async def`는 직접 `await`, `def`는 `run_in_threadpool`로 실행([async/await](../getting-started/python-types-and-async.md)).
5. **응답 만들기**
   - 반환값이 `Response` 인스턴스면 **그대로** 사용한다(응답 모델 검증·직렬화 생략). 응답의 `background`가 비어 있으면 주입된 `BackgroundTasks`를 붙인다.
   - 그렇지 않으면 `serialize_response()`로 응답 모델(반환 타입 또는 `response_model`)에 대해 **검증**한 뒤 `response_model_include/exclude/by_alias/exclude_unset/...` 옵션으로 직렬화한다. 검증 실패는 `ResponseValidationError`(서버 오류). 응답 모델이 없으면 `jsonable_encoder()`로 변환한다([응답 모델](../responses/response-model.md)).
   - 응답 모델이 있고 `response_class`를 지정하지 않았다면, Pydantic의 Rust 코어로 **바로 JSON 바이트를 생성하는 빠른 경로**를 사용한다(중간 dict + `json.dumps` 생략).
   - 상태 코드는 의존성/엔드포인트가 `Response` 파라미터에 설정한 값 → 데코레이터 `status_code` → 응답 클래스 기본값 순으로 결정된다. `Response` 파라미터에 설정한 헤더·쿠키는 최종 응답에 복사된다([상태 코드](../responses/status-codes.md), [응답 헤더와 쿠키](../responses/response-headers-and-cookies.md)).
   - 본문이 허용되지 않는 상태 코드(204, 304 등)면 본문을 비운다.
   - 스트리밍(`yield` 엔드포인트, JSON Lines, SSE)은 별도 경로로 처리된다([스트리밍과 SSE](../responses/streaming-and-sse.md)).
6. 응답이 반환되면 `function_stack` 정리 → 응답 전송 → `request_stack` 정리 → 백그라운드 작업 실행 → 미들웨어 정리 순으로 진행된다.

## OpenAPI 스키마 생성과 캐시

`app.openapi()`는 처음 호출될 때 `get_openapi()`로 스키마를 만들어 `app.openapi_schema`에 저장하고, 이후에는 저장된 값을 반환한다. 이 버전에서는 라우트가 추가·변경되어 라우터의 "routes version"이 바뀌면 다시 생성한다. `/openapi.json` 요청 시에는 `root_path`에 맞춰 `servers`를 보정한다([OpenAPI 확장](../openapi/customizing-openapi-and-docs-ui.md), [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md)).

## 디버깅 팁

- 422가 나오면 응답 `detail`의 `loc`(예: `["body", "price"]`, `["query", "q"]`)로 어느 파라미터가 실패했는지 확인한다. 엔드포인트 함수는 실행되지 않았다.
- 응답 모델 검증 실패는 클라이언트 422가 아니라 서버 500이며, 로그의 `ResponseValidationError`에 엔드포인트 정보가 포함된다.
- 블로킹 코드를 `async def`에 넣으면 이벤트 루프 전체가 멈춘다. 동기 라이브러리는 `def` 엔드포인트/의존성에서 호출한다.
- 미들웨어에서 처리되지 않은 예외는 `ServerErrorMiddleware`가 500으로 바꾼다. `FastAPI(debug=True)`면 트레이스백을 응답으로 보여 준다(운영 금지).

## 관련 페이지

- [Request 객체 직접 사용과 커스텀 APIRoute](../request/using-request-directly.md) — `get_route_handler()` 재정의로 이 흐름에 끼어들기
- [의존성 주입 기초](../dependencies/dependency-injection-basics.md)
- [미들웨어와 CORS](../middleware/middleware-and-cors.md)
