---
type: guide
title: 헤더와 쿠키 파라미터
description: Header()로 요청 헤더를 받는 방법과 밑줄→하이픈 자동 변환(convert_underscores), 중복 헤더를 list로 받기, Cookie()로 쿠키 받기, Pydantic 모델로 헤더·쿠키 파라미터 묶기(FastAPI 0.115.0+)와 extra="forbid"로 추가 헤더·쿠키 거부, 문서 UI에서 쿠키를 보낼 수 없는 이유를 설명한다.
tags: [headers, cookies, parameters, header-models, cookie-models, validation]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-271b7b386e680a403ae9c8fa
    resource: repo://docs_src/cookie_param_models/tutorial002_an_py310.py
  - id: openwiki-source-77f5b306ccc4bddccb0a42cd
    resource: repo://docs_src/cookie_params/tutorial001_an_py310.py
  - id: openwiki-source-5a73b75e06fb149013513757
    resource: repo://docs_src/header_param_models/tutorial001_an_py310.py
  - id: openwiki-source-70dcd567830447381dd927d1
    resource: repo://docs_src/header_param_models/tutorial002_an_py310.py
  - id: openwiki-source-948856469daba4cc94172f7b
    resource: repo://docs_src/header_param_models/tutorial003_an_py310.py
  - id: openwiki-source-ecd3aca0ab3476cf99a5f88b
    resource: repo://docs_src/header_params/tutorial001_an_py310.py
  - id: openwiki-source-14c4faaaab7b5cb2487b7da0
    resource: repo://docs_src/header_params/tutorial002_an_py310.py
  - id: openwiki-source-3755bb50687e08f4a8baa3db
    resource: repo://docs_src/header_params/tutorial003_an_py310.py
  - id: openwiki-source-92b8161cd107b8fe2397b104
    resource: repo://docs/en/docs/tutorial/cookie-params.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 헤더와 쿠키 파라미터

`Header`와 `Cookie`는 `Query`, `Path`와 같은 방식으로 선언한다. 기본값과 모든 추가 검증·주석 파라미터(`alias`, `description`, `deprecated` 등)를 똑같이 쓸 수 있다. 내부적으로 `Header`와 `Cookie`는 `Path`, `Query`와 같은 공통 `Param` 클래스를 상속하며, `fastapi`에서 임포트하는 `Header()` 등은 그 클래스 인스턴스를 반환하는 함수다.

> `Header`/`Cookie`를 명시하지 않으면 해당 파라미터는 **쿼리 파라미터**로 해석된다.

## 헤더 파라미터

```Python
from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI()


@app.get("/items/")
async def read_items(user_agent: Annotated[str | None, Header()] = None):
    return {"User-Agent": user_agent}
```

### 자동 변환

대부분의 표준 헤더는 하이픈(`-`)으로 구분되지만 `user-agent`는 Python 변수 이름으로 쓸 수 없다. 그래서 `Header`는 기본적으로 파라미터 이름의 밑줄(`_`)을 하이픈(`-`)으로 바꿔 헤더를 추출하고 문서화한다. HTTP 헤더는 대소문자를 구분하지 않으므로 `User_Agent`처럼 쓸 필요 없이 snake_case `user_agent`로 선언하면 된다. 명시적 `alias`가 있으면 변환하지 않고 그 이름을 쓴다.

변환을 끄려면 `convert_underscores=False`를 지정한다.

```Python
@app.get("/items/")
async def read_items(
    strange_header: Annotated[str | None, Header(convert_underscores=False)] = None,
):
    return {"strange_header": strange_header}
```

> 일부 HTTP 프록시와 서버는 밑줄이 들어간 헤더를 허용하지 않으므로 주의한다.

### 중복 헤더

같은 헤더가 여러 값으로 올 수 있다. 타입을 리스트로 선언하면 모든 값을 Python `list`로 받는다.

```Python
@app.get("/items/")
async def read_items(x_token: Annotated[list[str] | None, Header()] = None):
    return {"X-Token values": x_token}
```

```
X-Token: foo
X-Token: bar
```

→ `{"X-Token values": ["bar", "foo"]}`

## 쿠키 파라미터

```Python
from typing import Annotated

from fastapi import Cookie, FastAPI

app = FastAPI()


@app.get("/items/")
async def read_items(ads_id: Annotated[str | None, Cookie()] = None):
    return {"ads_id": ads_id}
```

> 브라우저는 쿠키를 특별하게 처리하며 JavaScript가 쿠키를 쉽게 다루지 못하게 한다. `/docs`에서 쿠키 문서는 볼 수 있지만, 문서 UI는 JavaScript로 동작하므로 값을 채우고 "Execute"를 눌러도 쿠키가 전송되지 않아 값을 쓰지 않은 것처럼 오류가 표시된다. 테스트는 `TestClient`나 실제 브라우저로 한다.

응답에 쿠키를 **설정**하는 방법은 [응답 헤더와 쿠키](../responses/response-headers-and-cookies.md)를 참고한다.

## 헤더 파라미터 모델

관련된 헤더를 Pydantic 모델로 묶어 여러 곳에서 재사용하고 검증·메타데이터를 한 번에 선언할 수 있다(FastAPI 0.115.0+).

```Python
from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI()


class CommonHeaders(BaseModel):
    host: str
    save_data: bool
    if_modified_since: str | None = None
    traceparent: str | None = None
    x_tag: list[str] = []


@app.get("/items/")
async def read_items(headers: Annotated[CommonHeaders, Header()]):
    return headers
```

FastAPI가 요청 헤더에서 **각 필드**를 추출해 모델을 만든다. 모델 필드에도 밑줄→하이픈 변환이 적용되어 `save_data`는 `save-data` 헤더로 읽히고 문서에도 그렇게 표시된다. `x_tag: list[str]`처럼 리스트 필드는 중복 헤더를 받는다.

### 추가 헤더 금지

```Python
class CommonHeaders(BaseModel):
    model_config = {"extra": "forbid"}

    host: str
    save_data: bool
    if_modified_since: str | None = None
    traceparent: str | None = None
    x_tag: list[str] = []
```

클라이언트가 `tool: plumbus` 같은 추가 헤더를 보내면 오류가 반환된다.

```JSON
{
    "detail": [
        {
            "type": "extra_forbidden",
            "loc": ["header", "tool"],
            "msg": "Extra inputs are not permitted",
            "input": "plumbus"
        }
    ]
}
```

변환된 헤더 이름(`save-data`)과 원래 필드 이름 모두 처리된 키로 간주되므로, 원래 이름이 "추가 헤더"로 오인되지 않는다.

### 모델에서 밑줄 변환 끄기

모델 수준의 `Header(convert_underscores=False)`로 모든 필드의 변환을 끈다.

```Python
@app.get("/items/")
async def read_items(
    headers: Annotated[CommonHeaders, Header(convert_underscores=False)],
):
    return headers
```

## 쿠키 파라미터 모델

```Python
from typing import Annotated

from fastapi import Cookie, FastAPI
from pydantic import BaseModel

app = FastAPI()


class Cookies(BaseModel):
    session_id: str
    fatebook_tracker: str | None = None
    googall_tracker: str | None = None


@app.get("/items/")
async def read_items(cookies: Annotated[Cookies, Cookie()]):
    return cookies
```

### 추가 쿠키 금지

드문 경우지만(예: 쿠키 동의 거부를 API 수준에서 강제) 받을 쿠키를 제한하려면:

```Python
class Cookies(BaseModel):
    model_config = {"extra": "forbid"}

    session_id: str
    fatebook_tracker: str | None = None
    googall_tracker: str | None = None
```

`santa_tracker` 같은 추가 쿠키를 보내면 `"type": "extra_forbidden"`, `"loc": ["cookie", "santa_tracker"]` 오류가 반환된다.

같은 기법은 [쿼리 파라미터 모델](./query-parameters.md)과 [폼 모델](./forms-and-files.md)에도 적용된다.

## 관련 페이지

- [쿼리 파라미터](./query-parameters.md)
- [응답 헤더와 쿠키](../responses/response-headers-and-cookies.md)
- [보안: API 키](../security/http-basic-and-api-keys.md) — `APIKeyHeader`, `APIKeyCookie`
- [미들웨어와 CORS](../middleware/middleware-and-cors.md) — 브라우저에서 사용자 정의 헤더 노출
