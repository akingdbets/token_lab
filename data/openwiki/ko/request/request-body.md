---
type: "참조"
title: "요청 본문: Pydantic 모델, 여러 본문 파라미터, Field"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-ee462d8bc4f7f301b937e395
    resource: repo://docs_src/body_fields/tutorial001_an_py310.py
  - id: openwiki-source-ed5f30e5dd915342b67c0d1a
    resource: repo://docs_src/body_multiple_params/tutorial003_an_py310.py
  - id: openwiki-source-ba22e62e86923273c8d3f1d0
    resource: repo://docs_src/body_multiple_params/tutorial004_an_py310.py
  - id: openwiki-source-edde7209af105d0504353b66
    resource: repo://docs_src/body_multiple_params/tutorial005_an_py310.py
  - id: openwiki-source-ca5920e3171f11d1aac4f0b1
    resource: repo://docs_src/body/tutorial001_py310.py
  - id: openwiki-source-2adc6294134ebdf7ba1a1e0f
    resource: repo://docs_src/body/tutorial002_py310.py
  - id: openwiki-source-3479104b34b02c0a1a358126
    resource: repo://docs_src/body/tutorial004_py310.py
  - id: openwiki-source-c2610c12a0bb7697c1366728
    resource: repo://docs_src/strict_content_type/tutorial001_py310.py
  - id: openwiki-source-dca17208de257c294db55bc3
    resource: repo://docs/en/docs/advanced/strict-content-type.md
  - id: openwiki-source-294a6d5904466cc19f308930
    resource: repo://docs/en/docs/tutorial/body.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 요청 본문: Pydantic 모델, 여러 본문 파라미터, Field

**요청 본문**은 클라이언트가 API로 보내는 데이터, **응답 본문**은 API가 클라이언트로 보내는 데이터다. 요청 본문은 [Pydantic](https://pydantic.dev/docs/) 모델로 선언한다.

데이터를 보낼 때는 `POST`(가장 흔함), `PUT`, `DELETE`, `PATCH`를 쓴다. `GET` 요청에 본문을 보내는 것은 명세상 정의되지 않은 동작이라 권장되지 않으며, FastAPI는 지원하지만 Swagger UI는 `GET`의 본문을 문서화하지 않고 중간 프록시가 지원하지 않을 수 있다.

## Pydantic 모델로 본문 선언

```Python
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return item
```

- 쿼리 파라미터처럼, 기본값이 있는 속성은 선택, 없으면 필수다. `None`으로 단순히 선택적으로 만든다.
- 다음 두 JSON 모두 유효하다.

```JSON
{"name": "Foo", "description": "An optional description", "price": 45.2, "tax": 3.5}
```

```JSON
{"name": "Foo", "price": 45.2}
```

이 타입 선언만으로 FastAPI는 다음을 한다.

- 요청 본문을 JSON으로 읽는다.
- 필요하면 해당 타입으로 변환한다.
- 데이터를 검증하고, 유효하지 않으면 정확히 어디가 잘못됐는지 알려 주는 오류를 반환한다.
- 받은 데이터를 파라미터 `item`에 넣어 준다. 함수 안에서 모든 속성의 타입을 알고 자동 완성을 받는다.
- 모델의 [JSON Schema](https://json-schema.org)를 생성해 OpenAPI 스키마와 문서 UI에 사용한다.

### 모델 사용

```Python
@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.model_dump()
    if item.tax is not None:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict
```

## 본문 + 경로 + 쿼리 파라미터

```Python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, q: str | None = None):
    result = {"item_id": item_id, **item.model_dump()}
    if q:
        result.update({"q": q})
    return result
```

판별 규칙:

- 경로에도 선언된 이름 → **경로** 파라미터
- 단일 타입(`int`, `float`, `str`, `bool` 등) → **쿼리** 파라미터
- **Pydantic 모델** 타입 → 요청 **본문**

`q: str | None = None`의 `None` 기본값으로 FastAPI는 `q`가 필수가 아님을 안다(`str | None` 타입은 FastAPI가 아니라 에디터 지원을 위한 것).

## 여러 본문 파라미터

### 선택적 본문

`Path`, `Query`, 본문 파라미터를 자유롭게 섞을 수 있고, 본문도 기본값 `None`으로 선택적으로 만들 수 있다.

```Python
@app.put("/items/{item_id}")
async def update_item(
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)],
    q: str | None = None,
    item: Item | None = None,
):
    ...
```

### 여러 모델

```Python
class User(BaseModel):
    username: str
    full_name: str | None = None


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, user: User):
    results = {"item_id": item_id, "item": item, "user": user}
    return results
```

본문 파라미터가 둘 이상이면 FastAPI는 **파라미터 이름을 키**로 쓰는 본문을 기대한다.

```JSON
{
    "item": {"name": "Foo", "description": "The pretender", "price": 42.0, "tax": 3.2},
    "user": {"username": "dave", "full_name": "Dave Grohl"}
}
```

### 본문의 단일 값: Body()

단일 값(`int` 등)은 기본적으로 쿼리 파라미터로 해석되므로, 본문의 키로 받으려면 `Body()`를 쓴다.

```Python
from typing import Annotated

from fastapi import Body, FastAPI


@app.put("/items/{item_id}")
async def update_item(
    item_id: int, item: Item, user: User, importance: Annotated[int, Body()]
):
    results = {"item_id": item_id, "item": item, "user": user, "importance": importance}
    return results
```

```JSON
{
    "item": {...},
    "user": {...},
    "importance": 5
}
```

`Body`도 `Query`, `Path`와 같은 검증·메타데이터 파라미터를 가진다(예: `Body(gt=0)`). 쿼리 파라미터와 함께 쓸 수도 있다.

```Python
@app.put("/items/{item_id}")
async def update_item(
    *,
    item_id: int,
    item: Item,
    user: User,
    importance: Annotated[int, Body(gt=0)],
    q: str | None = None,
):
    ...
```

### 단일 본문을 키로 감싸기: Body(embed=True)

본문 파라미터가 하나뿐이면 기본적으로 모델 내용을 그대로 본문으로 기대한다. 모델 이름을 키로 감싼 JSON을 기대하게 하려면 `embed=True`를 쓴다.

```Python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Annotated[Item, Body(embed=True)]):
    results = {"item_id": item_id, "item": item}
    return results
```

```JSON
{
    "item": {"name": "Foo", "description": "The pretender", "price": 42.0, "tax": 3.2}
}
```

Pydantic 모델 없이 본문을 받으려면 이처럼 `Body` 파라미터만 써도 된다.

## Field: 모델 필드 검증과 메타데이터

경로 작업 함수 파라미터에 `Query`, `Path`, `Body`를 쓰듯, Pydantic 모델 내부에는 `pydantic.Field`로 검증과 메타데이터를 선언한다. `Field`는 `fastapi`가 아니라 **`pydantic`에서 임포트**한다.

```Python
from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = Field(
        default=None, title="The description of the item", max_length=300
    )
    price: float = Field(gt=0, description="The price must be greater than zero")
    tax: float | None = None


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Annotated[Item, Body(embed=True)]):
    results = {"item_id": item_id, "item": item}
    return results
```

- `Field`는 `Query`, `Path`, `Body`와 같은 파라미터를 가진다. 사실 `Query`, `Path` 등은 Pydantic `FieldInfo`의 하위 클래스인 공통 `Param` 클래스의 하위 클래스이고, `Body`도 `FieldInfo`의 하위 클래스다.
- 모델 속성은 함수 파라미터와 같은 구조(타입, 기본값, `Field`)를 가진다.
- 추가 정보는 생성된 JSON Schema에 포함된다. 예제 추가는 [스키마 예제](../models/schema-examples.md)를 참고한다.

리스트·중첩 모델·특수 타입은 [중첩 모델과 추가 데이터 타입](./nested-models-and-data-types.md)을 참고한다.

## 엄격한 Content-Type 검사

FastAPI는 기본적으로 JSON 요청 본문에 대해 **엄격한 `Content-Type` 검사**를 한다. 즉 본문을 JSON으로 파싱하려면 요청에 유효한 `Content-Type`(예: `application/json` 또는 `application/*+json`)이 있어야 한다. `Content-Type`이 없으면 본문은 JSON으로 파싱되지 않아 모델 검증에 실패한다(FastAPI 0.132.0에서 추가된 동작·설정).

### 왜: CSRF 위험

브라우저는 다음 조건의 요청을 CORS preflight 없이 보낼 수 있다.

- `Content-Type` 헤더가 없다(예: `Blob` 본문을 쓴 `fetch()`).
- 인증 자격 증명을 보내지 않는다.

예를 들어 인증 없이 로컬(`http://localhost:8000`)에서 실행되는 AI 에이전트 API가 있고 "로컬 네트워크라 안전하다"고 가정한다면, 사용자가 악성 웹사이트(`https://evilhackers.example.com`)를 열었을 때 그 사이트가 `fetch()`로 로컬 API에 요청을 보내 에이전트를 조작할 수 있다. 엄격한 검사는 이런 **CSRF 공격**을 막는다.

공개 인터넷에서 운영하며 권한이 필요한 엔드포인트를 이미 인증으로 보호한다면 이 공격은 해당되지 않는다. 주로 **로컬/내부 네트워크**가 유일한 보호 수단일 때 관련된다.

### Content-Type 없는 요청 허용

`Content-Type`을 보내지 않는 클라이언트를 지원해야 한다면 끈다. 그러면 예전 버전처럼 `Content-Type`이 없는 요청 본문도 JSON으로 파싱한다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(strict_content_type=False)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items/")
async def create_item(item: Item):
    return item
```

## 관련 페이지

- [중첩 모델과 추가 데이터 타입](./nested-models-and-data-types.md)
- [폼 데이터와 파일 업로드](./forms-and-files.md) — JSON이 아닌 본문
- [응답 모델](../responses/response-model.md)
- [본문 업데이트(PUT/PATCH)](../models/body-updates-and-encoder.md)
- [Request 객체 직접 사용](./using-request-directly.md) — 원시 본문 읽기
