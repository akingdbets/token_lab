---
type: guide
title: 응답 모델과 반환 타입
description: 반환 타입 주석 또는 response_model로 응답 데이터를 검증·필터링·문서화·고속 직렬화하는 방법, 두 방식의 우선순위, 입력/출력 모델 분리로 비밀번호 같은 필드 숨기기, Response 반환과 response_model=None, response_model_exclude_unset/exclude_defaults/exclude_none, response_model_include/exclude를 설명한다.
tags: [response-model, return-type, serialization, filtering, pydantic, openapi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-399f1fbc618338063cd744ad
    resource: repo://docs_src/response_model/tutorial001_01_py310.py
  - id: openwiki-source-9a62f7950d7a9b9ac95d2fa4
    resource: repo://docs_src/response_model/tutorial003_01_py310.py
  - id: openwiki-source-41ea77b7453e52dc9a990df8
    resource: repo://docs_src/response_model/tutorial003_05_py310.py
  - id: openwiki-source-bd6ac53b99ab082ca19d305a
    resource: repo://docs_src/response_model/tutorial003_py310.py
  - id: openwiki-source-f40a322e7e096e6207d3367b
    resource: repo://docs_src/response_model/tutorial004_py310.py
  - id: openwiki-source-246dc932abfd82985b764c70
    resource: repo://docs_src/response_model/tutorial005_py310.py
  - id: openwiki-source-d230ce716904a37a841c83bc
    resource: repo://docs_src/response_model/tutorial006_py310.py
  - id: openwiki-source-1815f7028972fe19690e83a7
    resource: repo://docs/en/docs/tutorial/response-model.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 응답 모델과 반환 타입

경로 작업 함수의 **반환 타입 주석**으로 응답 타입을 선언할 수 있다. 입력 파라미터처럼 Pydantic 모델, 리스트, 딕셔너리, 정수·불리언 같은 스칼라 값을 쓸 수 있다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/")
async def read_items() -> list[Item]:
    return [
        Item(name="Portal Gun", price=42.0),
        Item(name="Plumbus", price=32.0),
    ]
```

FastAPI는 이 반환 타입으로 다음을 한다.

- 반환 데이터를 **검증**한다. 유효하지 않으면(예: 필드 누락) *앱 코드*가 잘못된 것이므로 잘못된 데이터 대신 서버 오류(`ResponseValidationError`, 500)를 반환한다. 앱과 클라이언트 모두 예상한 형태의 데이터를 받는다고 확신할 수 있다.
- OpenAPI 경로 작업에 응답 **JSON Schema**를 추가한다(문서, 자동 클라이언트 생성에 사용).
- 출력 데이터를 타입에 정의된 것으로 **제한·필터링**한다(보안상 특히 중요).
- Rust로 작성된 Pydantic으로 반환 데이터를 JSON으로 **직렬화**해 훨씬 빠르다.

## response_model 파라미터

반환 타입과 실제 반환 데이터가 다를 때(예: `dict`나 DB 객체를 반환하지만 Pydantic 모델로 선언하고 싶을 때), 타입 주석을 쓰면 에디터와 mypy가 오류를 표시한다. 이럴 때 데코레이터의 `response_model`을 쓴다.

```Python
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []


@app.post("/items/", response_model=Item)
async def create_item(item: Item) -> Any:
    return item


@app.get("/items/", response_model=list[Item])
async def read_items() -> Any:
    return [
        {"name": "Portal Gun", "price": 42.0},
        {"name": "Plumbus", "price": 32.0},
    ]
```

- `response_model`은 함수가 아니라 **데코레이터**(`@app.get()`, `@app.post()` 등)의 파라미터다.
- Pydantic 모델 필드에 선언하는 것과 같은 타입을 받는다(예: `list[Item]`).
- 반환 타입을 `Any`로 두면 엄격한 타입 검사기를 쓰더라도 문제가 없다.

### 우선순위

반환 타입과 `response_model`을 둘 다 선언하면 **`response_model`이 우선**한다. 에디터용 타입 주석은 유지하면서 FastAPI에는 다른 모델로 검증·문서화를 맡길 수 있다. `response_model=None`으로 응답 모델 생성을 끌 수도 있다(아래 참고).

## 입력 데이터를 그대로 반환하면 안 되는 경우

```Python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI()


class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


# 운영 환경에서는 이렇게 하지 말 것!
@app.post("/user/")
async def create_user(user: UserIn) -> UserIn:
    return user
```

평문 비밀번호가 응답에 그대로 포함된다. 같은 사용자라 지금은 괜찮아 보여도, 다른 경로 작업에서 같은 모델을 쓰면 사용자 비밀번호를 모든 클라이언트에 보내게 될 수 있다. 절대 저장·노출하지 않는다.

### 출력 모델 추가

```Python
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI()


class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


@app.post("/user/", response_model=UserOut)
async def create_user(user: UserIn) -> Any:
    return user
```

함수는 비밀번호가 포함된 `UserIn`을 반환하지만 `response_model=UserOut`이므로 FastAPI가 `UserOut`에 없는 데이터를 모두 걸러낸다.

### 반환 타입과 데이터 필터링(상속 활용)

에디터 지원과 필터링을 둘 다 얻으려면 상속을 쓴다.

```Python
class BaseUser(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserIn(BaseUser):
    password: str


@app.post("/user/")
async def create_user(user: UserIn) -> BaseUser:
    return user
```

- 타입 관점에서 `UserIn`은 `BaseUser`의 하위 클래스이므로 반환 타입이 유효하다(에디터·mypy 만족).
- FastAPI는 반환 타입 `BaseUser`로 **필터링**하므로 `password`가 응답에서 빠진다. 단순 클래스 상속처럼 동작하지 않고 Pydantic으로 직렬화하기 때문이다.
- 문서에는 입력 모델과 출력 모델이 각자의 JSON Schema로 표시된다.

여러 모델 패턴은 [추가 모델](../models/extra-models-and-dataclasses.md)에서 자세히 다룬다.

## 기타 반환 타입 주석

### Response 직접 반환

```Python
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse

app = FastAPI()


@app.get("/portal")
async def get_portal(teleport: bool = False) -> Response:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return JSONResponse(content={"message": "Here's your interdimensional portal."})
```

반환 타입이 `Response` 클래스(또는 하위 클래스)이면 FastAPI가 자동으로 처리한다(응답 모델을 만들지 않음). `RedirectResponse`, `JSONResponse`가 `Response`의 하위 클래스라 타입도 올바르다. 하위 클래스로 주석해도 된다.

```Python
@app.get("/teleport")
async def get_teleport() -> RedirectResponse:
    return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

### 유효하지 않은 반환 타입 주석

```Python
@app.get("/portal")
async def get_portal(teleport: bool = False) -> Response | dict:
    ...
```

Pydantic 타입이 아니고 단일 `Response` 클래스도 아닌 유니언이므로 FastAPI가 응답 모델을 만들려다 **실패**한다(앱 시작 시 `FastAPIError`).

### 응답 모델 끄기: response_model=None

타입 주석은 유지하면서 FastAPI가 응답 모델을 만들지 않게 하려면:

```Python
@app.get("/portal", response_model=None)
async def get_portal(teleport: bool = False) -> Response | dict:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return {"message": "Here's your interdimensional portal."}
```

응답 모델 생성을 건너뛰므로 에디터·mypy 지원은 유지하면서 FastAPI에 영향을 주지 않는다. 이 경우 반환값은 `jsonable_encoder`로 변환된다.

## 응답 모델 인코딩 파라미터

### response_model_exclude_unset

```Python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float = 10.5
    tags: list[str] = []


items = {
    "foo": {"name": "Foo", "price": 50.2},
    "bar": {"name": "Bar", "description": "The bartenders", "price": 62, "tax": 20.2},
    "baz": {"name": "Baz", "description": None, "price": 50.2, "tax": 10.5, "tags": []},
}


@app.get("/items/{item_id}", response_model=Item, response_model_exclude_unset=True)
async def read_item(item_id: str):
    return items[item_id]
```

- `foo`: 기본값은 응답에 포함되지 않고 **실제로 설정된 값만** 포함된다 → `{"name": "Foo", "price": 50.2}`. NoSQL DB의 선택 속성이 많은 모델에서 기본값으로 가득 찬 긴 JSON을 피할 때 유용하다.
- `baz`: `description`, `tax`, `tags`가 기본값과 같은 값이지만 **명시적으로 설정**되었으므로 응답에 포함된다(Pydantic이 구분한다). 기본값은 `None`뿐 아니라 `[]`, `10.5` 등 무엇이든 될 수 있다.

비슷한 옵션:

- `response_model_exclude_defaults=True`: 기본값과 같은 값 제외
- `response_model_exclude_none=True`: `None` 값 제외
- `response_model_by_alias`(기본 `True`): 필드 alias로 직렬화

### response_model_include / response_model_exclude

포함할(나머지 제외) 또는 제외할(나머지 포함) 속성 이름의 `set`을 받는다. 모델이 하나뿐인데 일부 데이터만 빠르게 제외하고 싶을 때의 지름길이다.

```Python
@app.get(
    "/items/{item_id}/name",
    response_model=Item,
    response_model_include={"name", "description"},
)
async def read_item_name(item_id: str):
    return items[item_id]


@app.get("/items/{item_id}/public", response_model=Item, response_model_exclude={"tax"})
async def read_item_public_data(item_id: str):
    return items[item_id]
```

- `{"name", "description"}`는 `set(["name", "description"])`과 같다. `list`나 `tuple`을 넘겨도 FastAPI가 `set`으로 변환한다.
- 그래도 **여러 클래스**를 쓰는 방식을 권장한다. include/exclude를 써도 OpenAPI(문서)의 JSON Schema는 전체 모델 그대로이기 때문이다. `response_model_exclude_unset`도 마찬가지다.

## 관련 페이지

- [추가 모델과 dataclasses](../models/extra-models-and-dataclasses.md)
- [응답 직접 반환과 커스텀 응답](./custom-responses.md)
- [상태 코드](./status-codes.md)
- [OpenAPI 입력/출력 스키마 분리](../openapi/customizing-openapi-and-docs-ui.md)
- [요청 처리 흐름](../internals/request-lifecycle.md) — 응답 검증·직렬화 순서
