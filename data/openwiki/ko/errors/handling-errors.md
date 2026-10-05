---
type: guide
title: 오류 처리와 예외 핸들러
description: HTTPException으로 4xx 오류 반환(detail에 JSON 값, headers 추가), @app.exception_handler로 사용자 정의 예외 처리, RequestValidationError·StarletteHTTPException 기본 핸들러 재정의, exc.body 활용, fastapi.exception_handlers의 기본 핸들러 재사용, 보안 클래스의 401/403 상태 코드 변경(make_not_authenticated_error)을 설명한다.
tags: [errors, httpexception, exception-handler, request-validation-error, status-codes]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-1f323bb4ecac55ff65656129
    resource: repo://docs_src/authentication_error_status_code/tutorial001_an_py310.py
  - id: openwiki-source-4f6197b295ea942c9f3bcda4
    resource: repo://docs_src/handling_errors/tutorial001_py310.py
  - id: openwiki-source-c6692ba17e0231ff71f6685a
    resource: repo://docs_src/handling_errors/tutorial002_py310.py
  - id: openwiki-source-dd0a6c93867083961dd90798
    resource: repo://docs_src/handling_errors/tutorial003_py310.py
  - id: openwiki-source-684aa2ef0e2825f8b1a76f43
    resource: repo://docs_src/handling_errors/tutorial004_py310.py
  - id: openwiki-source-862fdc39ac2e89444fe86396
    resource: repo://docs_src/handling_errors/tutorial005_py310.py
  - id: openwiki-source-19ed87b7838e67ed44f19919
    resource: repo://docs_src/handling_errors/tutorial006_py310.py
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-cd7d32cb20717b70ce7fd8ca
    resource: repo://fastapi/exception_handlers.py
  - id: openwiki-source-6960ae62409012c9993d0ec2
    resource: repo://fastapi/exceptions.py
  - id: openwiki-source-c3a2665619211e35f840a799
    resource: repo://fastapi/security/http.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 오류 처리와 예외 핸들러

API를 사용하는 클라이언트에게 오류를 알려야 하는 경우가 많다. 권한이 없거나, 리소스가 없거나, 접근할 수 없는 항목을 요청한 경우 등이다. 이때는 보통 **400~499** 범위의 상태 코드(클라이언트 오류)를 반환한다. 200~299는 성공을 의미한다.

## HTTPException 사용

```Python
from fastapi import FastAPI, HTTPException

app = FastAPI()

items = {"foo": "The Foo Wrestlers"}


@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```

- `HTTPException`은 일반 Python 예외이므로 `return`이 아니라 **`raise`**한다.
- 경로 작업 함수 안에서 호출한 유틸리티 함수에서 발생시켜도 나머지 코드가 중단되고 바로 오류 응답이 전송된다. 그래서 [의존성](../dependencies/dependency-injection-basics.md)이나 보안 코드에서 특히 유용하다.
- `/items/foo` → 200, `{"item": "The Foo Wrestlers"}`
- `/items/bar` → 404, `{"detail": "Item not found"}`
- `detail`에는 `str`뿐 아니라 `dict`, `list` 등 **JSON으로 변환 가능한 모든 값**을 넘길 수 있다. FastAPI가 자동으로 JSON으로 변환한다.

### 사용자 정의 헤더 추가

일부 보안 시나리오처럼 오류 응답에 헤더가 필요할 때 `headers`를 넘긴다.

```Python
@app.get("/items-header/{item_id}")
async def read_item_header(item_id: str):
    if item_id not in items:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
            headers={"X-Error": "There goes my error"},
        )
    return {"item": items[item_id]}
```

## 사용자 정의 예외 핸들러

Starlette의 예외 유틸리티와 같은 방식으로 `@app.exception_handler()`를 등록한다.

```Python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class UnicornException(Exception):
    def __init__(self, name: str):
        self.name = name


app = FastAPI()


@app.exception_handler(UnicornException)
async def unicorn_exception_handler(request: Request, exc: UnicornException):
    return JSONResponse(
        status_code=418,
        content={"message": f"Oops! {exc.name} did something. There goes a rainbow..."},
    )


@app.get("/unicorns/{name}")
async def read_unicorn(name: str):
    if name == "yolo":
        raise UnicornException(name=name)
    return {"unicorn_name": name}
```

`/unicorns/yolo` 요청 시 418과 `{"message": "Oops! yolo did something. There goes a rainbow..."}`가 반환된다. 핸들러는 `request`와 `exc`를 받아 `Response`를 반환한다. `fastapi.responses`, `fastapi.Request`는 편의를 위해 Starlette 것을 재노출한 것이다.

## 기본 예외 핸들러 재정의

`FastAPI` 앱은 생성 시 다음 기본 핸들러를 등록한다(`exception_handlers.setdefault`이므로 사용자가 `FastAPI(exception_handlers=...)`로 넘긴 것이 우선).

| 예외 | 기본 핸들러 | 동작 |
| --- | --- | --- |
| `HTTPException`(Starlette) | `http_exception_handler` | `{"detail": exc.detail}` JSON + `exc.headers`. 본문이 허용되지 않는 상태 코드(예: 204, 304)면 본문 없는 `Response` |
| `RequestValidationError` | `request_validation_exception_handler` | 422 + `{"detail": jsonable_encoder(exc.errors())}` |
| `WebSocketRequestValidationError` | `websocket_request_validation_exception_handler` | WebSocket을 1008(Policy Violation) 코드로 종료 |

### 요청 검증 오류 재정의

요청 데이터가 유효하지 않으면 FastAPI는 내부적으로 `RequestValidationError`를 발생시킨다. 기본 응답 예:

```JSON
{
    "detail": [
        {
            "loc": ["path", "item_id"],
            "msg": "Input should be a valid integer, unable to parse string as an integer",
            "type": "int_parsing",
            "input": "foo"
        }
    ]
}
```

텍스트로 바꾸는 예:

```Python
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    message = "Validation errors:"
    for error in exc.errors():
        message += f"\nField: {error['loc']}, Error: {error['msg']}"
    return PlainTextResponse(message, status_code=400)


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id == 3:
        raise HTTPException(status_code=418, detail="Nope! I don't like 3.")
    return {"item_id": item_id}
```

`RequestValidationError`에는 오류가 발생한 파일 이름과 줄 정보가 포함되어 있어 로그에 남길 수 있다. 하지만 그대로 클라이언트에 노출하면 보안상 위험할 수 있다.

### RequestValidationError의 body 사용

`exc.body`에는 받은 (유효하지 않은) 본문이 들어 있다. 개발 중 로그나 디버깅, 사용자 응답에 활용할 수 있다.

```Python
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


class Item(BaseModel):
    title: str
    size: int


@app.post("/items/")
async def create_item(item: Item):
    return item
```

`{"title": "towel", "size": "XL"}`를 보내면 `detail`과 함께 `"body": {"title": "towel", "size": "XL"}`가 반환된다.

### FastAPI의 HTTPException vs Starlette의 HTTPException

- FastAPI의 `HTTPException`은 Starlette의 `HTTPException`을 상속한다. 차이는 FastAPI 쪽은 `detail`에 JSON 가능한 모든 데이터를 허용하고(Starlette는 문자열만), `headers`를 받는다는 점이다.
- 코드에서 **발생시킬 때**는 FastAPI의 `HTTPException`을 쓴다.
- 핸들러를 **등록할 때**는 Starlette의 `HTTPException`에 등록한다. 그래야 Starlette 내부 코드나 확장이 발생시킨 예외(예: 404 Not Found, 405 Method Not Allowed)도 잡힌다. 두 클래스를 함께 쓰려면 `from starlette.exceptions import HTTPException as StarletteHTTPException`처럼 별칭을 쓴다.

### 기본 핸들러 재사용

예외를 기록한 뒤 기본 동작은 그대로 유지하려면 `fastapi.exception_handlers`에서 기본 핸들러를 가져와 호출한다.

```Python
from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    print(f"OMG! An HTTP error!: {repr(exc)}")
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"OMG! The client sent invalid data!: {exc}")
    return await request_validation_exception_handler(request, exc)
```

## 그 밖의 예외 클래스(`fastapi.exceptions`)

- `WebSocketException`: WebSocket 엔드포인트에서 연결을 종료할 때([WebSocket](../integrations/websockets.md))
- `ResponseValidationError`: 반환값이 [응답 모델](../responses/response-model.md) 검증에 실패하면 발생하며, 클라이언트 오류가 아니라 서버 오류(500)로 처리된다.
- `FastAPIError`, `DependencyScopeError`: 잘못된 사용(예: 의존성 scope 위반)을 알리는 개발자용 오류

## 인증 오류 상태 코드: 401 vs 403

FastAPI **0.122.0**부터 내장 보안 유틸리티는 인증 실패 시 HTTP 명세(RFC 7235, RFC 9110)에 맞게 **`401 Unauthorized`**와 적절한 `WWW-Authenticate` 헤더를 반환한다(이전에는 `403 Forbidden`). 예를 들어 `HTTPBearer`는 `HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})`를 만든다.

클라이언트가 예전 동작에 의존한다면, 보안 클래스를 상속해 `make_not_authenticated_error()`를 재정의한다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI()


class HTTPBearer403(HTTPBearer):
    def make_not_authenticated_error(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated"
        )


CredentialsDep = Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer403())]


@app.get("/me")
def read_me(credentials: CredentialsDep):
    return {"message": "You are authenticated", "token": credentials.credentials}
```

이 메서드는 예외를 **반환**할 뿐 발생시키지 않는다. 발생은 보안 클래스 내부 코드가 담당한다. `APIKeyHeader` 등 다른 보안 클래스도 같은 메서드를 가진다([HTTP Basic, API 키](../security/http-basic-and-api-keys.md)).

## 관련 페이지

- [상태 코드](../responses/status-codes.md)
- [yield를 사용하는 의존성](../dependencies/dependencies-with-yield.md) — 의존성에서 예외 잡기와 재발생
- [추가 응답](../responses/additional-responses.md) — 오류 응답을 OpenAPI에 문서화
- [미들웨어](../middleware/middleware-and-cors.md)
