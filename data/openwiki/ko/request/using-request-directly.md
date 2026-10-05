---
type: guide
title: Request 객체 직접 사용과 커스텀 Request/APIRoute
description: 경로 작업 파라미터를 Request 타입으로 선언해 Starlette Request(클라이언트 IP, 원시 본문 등)에 직접 접근하는 방법과 검증·문서화가 생략된다는 점, Request 서브클래스(GzipRequest)와 APIRoute.get_route_handler() 재정의로 요청 본문 변환·예외 처리·응답 시간 측정을 하는 방법, app.router.route_class와 APIRouter(route_class=...)로 적용 범위를 정하는 방법을 설명한다.
tags: [request, starlette, apiroute, route-class, custom-request, gzip]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-4124748546524f167641c798
    resource: repo://docs_src/custom_request_and_route/tutorial001_an_py310.py
  - id: openwiki-source-727b2ae2e333761582e655ad
    resource: repo://docs_src/custom_request_and_route/tutorial002_an_py310.py
  - id: openwiki-source-e79f261952e8647156880574
    resource: repo://docs_src/custom_request_and_route/tutorial003_py310.py
  - id: openwiki-source-8782b090f58527cb09067138
    resource: repo://docs_src/using_request_directly/tutorial001_py310.py
  - id: openwiki-source-1c4300918a70439b89cefc67
    resource: repo://docs/en/docs/advanced/using-request-directly.md
  - id: openwiki-source-4f39b87de176905c9a9e93d3
    resource: repo://fastapi/requests.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# Request 객체 직접 사용과 커스텀 Request/APIRoute

## Request 객체 직접 사용

지금까지는 필요한 요청 부분(경로 파라미터, 본문, 헤더, 쿠키 등)을 타입과 함께 선언해 FastAPI가 검증·변환·문서화하게 했다. 하지만 `Request` 객체에 직접 접근해야 할 때도 있다.

FastAPI는 내부적으로 Starlette이므로 Starlette의 [`Request`](https://starlette.dev/requests/) 객체를 그대로 쓸 수 있다. `fastapi.Request`는 `starlette.requests.Request`를 재노출한 것이다(`HTTPConnection`도 마찬가지).

```Python
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/items/{item_id}")
def read_root(item_id: str, request: Request):
    client_host = request.client.host
    return {"client_host": client_host, "item_id": item_id}
```

- 파라미터 타입을 `Request`로 선언하면 FastAPI가 그 파라미터에 `Request`를 넣어 준다.
- 함께 선언한 다른 파라미터(여기서는 경로 파라미터 `item_id`)는 평소처럼 추출·검증·변환·문서화된다.
- `Request`에서 직접 얻은 데이터(예: `await request.body()`로 읽은 본문)는 FastAPI가 **검증·변환·문서화하지 않는다**.
- 의존성 함수에서도 `Request`를 받을 수 있다. WebSocket에서는 `WebSocket`, 둘 다 공통이면 `HTTPConnection`을 쓴다.

자주 쓰는 속성: `request.client.host`, `request.method`, `request.url`, `request.headers`, `request.query_params`, `request.path_params`, `request.cookies`, `request.state`, `request.scope`, 그리고 `await request.body()`, `await request.json()`, `await request.form()`. 자세한 내용은 [Starlette Requests 문서](https://starlette.dev/requests/)를 참고한다.

원시 본문을 직접 파싱하면서 OpenAPI에는 스키마를 표시하려면 `openapi_extra`를 쓴다([경로 작업 설정](../app-structure/path-operation-configuration.md)).

## 커스텀 Request와 APIRoute 클래스

> 고급 기능이다. FastAPI를 막 시작했다면 건너뛰어도 된다.

`Request`와 `APIRoute`의 로직을 재정의하면, 앱이 처리하기 전에 요청 본문을 읽거나 조작하는 등 **미들웨어의 대안**이 될 수 있다. 미들웨어와 달리 특정 라우터/라우트에만 적용할 수 있고, FastAPI가 본문을 읽는 지점에 직접 개입한다.

사용 사례:

- JSON이 아닌 요청 본문(예: [`msgpack`](https://msgpack.org/index.html))을 JSON으로 변환
- gzip으로 압축된 요청 본문 해제
- 모든 요청 본문 자동 로깅

### gzip 요청 해제 예

```Python
import gzip
from collections.abc import Callable
from typing import Annotated

from fastapi import Body, FastAPI, Request, Response
from fastapi.routing import APIRoute


class GzipRequest(Request):
    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = await super().body()
            if "gzip" in self.headers.getlist("Content-Encoding"):
                body = gzip.decompress(body)
            self._body = body
        return self._body


class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = GzipRequest(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler


app = FastAPI()
app.router.route_class = GzipRoute


@app.post("/sum")
async def sum_numbers(numbers: Annotated[list[int], Body()]):
    return {"sum": sum(numbers)}
```

1. **`GzipRequest`**: `Request.body()`를 재정의해 `Content-Encoding` 헤더에 `gzip`이 있을 때만 본문을 해제한다. 그래서 같은 라우트가 압축/비압축 요청을 모두 처리한다.
2. **`GzipRoute`**: `fastapi.routing.APIRoute`를 상속하고 `get_route_handler()`를 재정의한다. 이 메서드는 "요청을 받아 응답을 반환하는 함수"를 반환한다. 원래 핸들러를 얻은 뒤, 원래 요청의 `scope`와 `receive`로 `GzipRequest`를 만들어 넘긴다.
   - `request.scope`는 요청 메타데이터를 담은 `dict`, `request.receive`는 본문을 "받는" 함수이며, 둘 다 ASGI 명세의 일부다. 이 두 가지만 있으면 새 `Request` 인스턴스를 만들 수 있다.
3. `app.router.route_class = GzipRoute`로 이후 `app`에 등록하는 경로 작업이 이 클래스를 사용하게 한다.

이후 처리 로직은 동일하며, FastAPI가 필요할 때 본문을 읽으면 `GzipRequest.body`가 자동으로 해제한다. 실제로 gzip 응답 압축이 필요하면 [`GZipMiddleware`](../middleware/middleware-and-cors.md)를 쓰는 것이 낫다(이 예제는 동작 원리 시연용).

### 예외 핸들러에서 요청 본문에 접근

```Python
from collections.abc import Callable
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute


class ValidationErrorLoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                body = await request.body()
                detail = {"errors": exc.errors(), "body": body.decode()}
                raise HTTPException(status_code=422, detail=detail)

        return custom_route_handler


app = FastAPI()
app.router.route_class = ValidationErrorLoggingRoute


@app.post("/")
async def sum_numbers(numbers: Annotated[list[int], Body()]):
    return sum(numbers)
```

`try`/`except`로 원래 핸들러를 감싸 `RequestValidationError`를 잡고, 같은 `Request` 인스턴스에서 본문을 다시 읽어 오류 응답에 포함한다. 같은 문제는 `RequestValidationError` 사용자 정의 핸들러에서 `exc.body`를 쓰는 편이 훨씬 쉽다([오류 처리](../errors/handling-errors.md)).

### 라우터에 커스텀 APIRoute 적용

`APIRouter(route_class=...)`로 특정 라우터의 경로 작업에만 적용할 수 있다.

```Python
import time
from collections.abc import Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.routing import APIRoute


class TimedRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            before = time.time()
            response: Response = await original_route_handler(request)
            duration = time.time() - before
            response.headers["X-Response-Time"] = str(duration)
            print(f"route duration: {duration}")
            print(f"route response: {response}")
            print(f"route response headers: {response.headers}")
            return response

        return custom_route_handler


app = FastAPI()
router = APIRouter(route_class=TimedRoute)


@app.get("/")
async def not_timed():
    return {"message": "Not timed"}


@router.get("/timed")
async def timed():
    return {"message": "It's the time of my life"}


app.include_router(router)
```

`/timed` 응답에만 `X-Response-Time` 헤더가 추가되고 `/`에는 추가되지 않는다.

### 내부 동작 참고

기본 `APIRoute.get_route_handler()`는 라우트의 의존성, 본문 필드, 상태 코드, 응답 클래스·모델 옵션, `strict_content_type` 등을 모아 `get_request_handler()`를 호출한다. 라우터에 포함된 라우트의 경우 이 버전은 포함 컨텍스트(prefix·의존성 등이 합쳐진 "effective" 라우트)를 내부 ContextVar로 전달한다. 재정의할 때는 `super().get_route_handler()`를 호출해 이 흐름을 유지하는 것이 안전하다([요청 처리 흐름](../internals/request-lifecycle.md)).

## 관련 페이지

- [미들웨어와 CORS](../middleware/middleware-and-cors.md)
- [요청 처리 흐름](../internals/request-lifecycle.md)
- [오류 처리](../errors/handling-errors.md)
- [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md) — `request.scope["root_path"]`
