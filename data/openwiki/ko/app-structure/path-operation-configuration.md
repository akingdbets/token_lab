---
type: guide
title: 경로 작업 설정(기본·고급)
description: 경로 작업 데코레이터 파라미터 status_code, tags(Enum 포함), summary, description, docstring(Markdown·\f 절단), response_description, deprecated와 고급 설정 operation_id, generate_unique_id_function, include_in_schema, openapi_extra(확장 필드, 직접 정의한 requestBody)를 예제와 함께 설명한다.
tags: [path-operation, openapi, tags, operation-id, openapi-extra, docstring]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-ad0a8ff31866f8e818625861
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial002_py310.py
  - id: openwiki-source-a3cd249f33ef1a33ee04bb25
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial003_py310.py
  - id: openwiki-source-e3ecfcdee33b1ee4dde9390a
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial004_py310.py
  - id: openwiki-source-730e611134b4eb2c482b9ba5
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial007_py310.py
  - id: openwiki-source-775c83f53a700889cd385d9f
    resource: repo://docs_src/path_operation_configuration/tutorial005_py310.py
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://fastapi/openapi/utils.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 경로 작업 설정(기본·고급)

`@app.get()`, `@app.post()`, `@router.put()` 같은 **경로 작업 데코레이터**에 넘기는 파라미터로 응답과 OpenAPI 문서를 설정한다. 이 파라미터들은 경로 작업 함수가 아니라 데코레이터에 직접 전달한다.

## 응답 상태 코드: status_code

```Python
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()


@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(item: Item) -> Item:
    return item
```

정수(`201`)나 `fastapi.status`의 상수를 쓸 수 있다. `http.HTTPStatus` 같은 `IntEnum`도 정수로 정규화된다. 자세한 내용은 [상태 코드](../responses/status-codes.md).

## tags

```Python
@app.post("/items/", tags=["items"])
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/", tags=["items"])
async def read_items():
    return [{"name": "Foo", "price": 42}]


@app.get("/users/", tags=["users"])
async def read_users():
    return [{"username": "johndoe"}]
```

태그는 OpenAPI 스키마에 들어가고 문서 UI에서 그룹으로 표시된다. 큰 앱에서는 태그 문자열을 `Enum`으로 관리하면 오타를 줄일 수 있다.

```Python
from enum import Enum

from fastapi import FastAPI

app = FastAPI()


class Tags(Enum):
    items = "items"
    users = "users"


@app.get("/items/", tags=[Tags.items])
async def get_items():
    return ["Portal gun", "Plumbus"]


@app.get("/users/", tags=[Tags.users])
async def read_users():
    return ["Rick", "Morty"]
```

태그 설명과 순서는 [메타데이터](./metadata-and-docs-urls.md)의 `openapi_tags`로 지정한다.

## summary와 description

```Python
@app.post(
    "/items/",
    summary="Create an item",
    description="Create an item with all the information, name, description, price, tax and a set of unique tags",
)
async def create_item(item: Item) -> Item:
    return item
```

`summary`를 생략하면 함수 이름의 `_`를 공백으로 바꾸고 단어 첫 글자를 대문자로 바꾼 값(예: `create_item` → `Create Item`)이 사용된다.

### docstring에서 description 가져오기

`description`을 지정하지 않으면 함수의 **docstring**을 `inspect.cleandoc()`으로 정리해 사용한다. docstring에는 **Markdown**을 쓸 수 있다.

```Python
@app.post("/items/", summary="Create an item")
async def create_item(item: Item) -> Item:
    """
    Create an item with all the information:

    - **name**: each item must have a name
    - **description**: a long description
    - **price**: required
    - **tax**: if the item doesn't have tax, you can omit this
    - **tags**: a set of unique tag strings for this item
    """
    return item
```

### `\f`로 docstring 자르기

docstring에 `\f`(form feed)가 있으면 그 앞부분만 OpenAPI에 사용된다. 뒷부분은 Sphinx 같은 다른 도구용 문서로 남길 수 있다.

```Python
@app.post("/items/", summary="Create an item")
async def create_item(item: Item) -> Item:
    """
    Create an item with all the information:

    - **name**: each item must have a name
    ...
    \f
    :param item: User input.
    """
    return item
```

## response_description

```Python
@app.post(
    "/items/",
    summary="Create an item",
    response_description="The created item",
)
async def create_item(item: Item) -> Item:
    ...
```

`response_description`은 응답에 대한 설명이고 `description`은 경로 작업 전체에 대한 설명이다. OpenAPI는 응답 설명을 필수로 요구하므로, 지정하지 않으면 기본값 `"Successful Response"`가 들어간다.

## deprecated

```Python
@app.get("/elements/", tags=["items"], deprecated=True)
async def read_elements():
    return [{"item_id": "Foo"}]
```

삭제하지 않고 "사용 중단"으로 표시한다. 문서 UI에서 구분되어 표시된다. 파라미터 단위의 사용 중단은 [쿼리 파라미터](../request/query-parameters.md)의 `Query(deprecated=True)`를 참고한다.

## 고급: operation_id

> OpenAPI "전문가"가 아니라면 보통 필요 없다.

```Python
@app.get("/items/", operation_id="some_specific_id_you_define")
async def read_items():
    return [{"item_id": "Foo"}]
```

`operation_id`는 모든 경로 작업에서 **고유**해야 한다.

### generate_unique_id_function

기본 `operationId`는 `fastapi.utils.generate_unique_id()`가 `함수이름 + 경로`의 비영숫자 문자를 `_`로 바꾸고 첫 HTTP 메서드를 붙여 만든다(예: `read_items_items__get`). 함수 이름 자체를 `operationId`로 쓰려면 사용자 정의 함수를 넘긴다.

```Python
from fastapi import FastAPI
from fastapi.routing import APIRoute


def custom_generate_unique_id(route: APIRoute) -> str:
    return route.name


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)


@app.get("/items/")
async def read_items():
    return [{"item_id": "Foo"}]
```

이렇게 하면 **모든 경로 작업 함수 이름이 고유해야 한다**(다른 모듈에 있더라도). `generate_unique_id_function`은 `FastAPI`, `APIRouter`, `include_router()`, 개별 경로 작업 데코레이터 모두에서 지정할 수 있으며, 명시적 `operation_id`가 있으면 그것이 우선한다. 클라이언트 SDK 생성 시 활용법은 [클라이언트 SDK 생성](../openapi/generate-clients.md).

## 고급: include_in_schema

```Python
@app.get("/items/", include_in_schema=False)
async def read_items():
    return [{"item_id": "Foo"}]
```

OpenAPI 스키마(따라서 자동 문서)에서 제외한다. 경로 작업 자체는 여전히 동작한다.

## 고급: openapi_extra

`openapi_extra` 딕셔너리는 자동 생성된 해당 경로 작업의 OpenAPI 스키마(Operation Object)에 **깊게 병합(deep merge)**된다.

### OpenAPI 확장 필드

```Python
@app.get("/items/", openapi_extra={"x-aperture-labs-portal": "blue"})
async def read_items():
    return [{"item_id": "portal-gun"}]
```

`/openapi.json`의 해당 작업에 `"x-aperture-labs-portal": "blue"`가 추가된다.

### 직접 파싱하는 요청 본문을 문서화

Pydantic 모델을 선언하지 않고 `Request`로 원본 바이트를 읽으면서도, 문서에는 요청 본문 스키마를 표시할 수 있다.

```Python
from fastapi import FastAPI, Request

app = FastAPI()


def magic_data_reader(raw_body: bytes):
    return {
        "size": len(raw_body),
        "content": {
            "name": "Maaaagic",
            "price": 42,
            "description": "Just kiddin', no magic here. ✨",
        },
    }


@app.post(
    "/items/",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "required": ["name", "price"],
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                            "description": {"type": "string"},
                        },
                    }
                }
            },
            "required": True,
        },
    },
)
async def create_item(request: Request):
    raw_body = await request.body()
    data = magic_data_reader(raw_body)
    return data
```

### JSON이 아닌 콘텐츠(YAML)를 Pydantic으로 검증

```Python
import yaml
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ValidationError

app = FastAPI()


class Item(BaseModel):
    name: str
    tags: list[str]


@app.post(
    "/items/",
    openapi_extra={
        "requestBody": {
            "content": {"application/x-yaml": {"schema": Item.model_json_schema()}},
            "required": True,
        },
    },
)
async def create_item(request: Request):
    raw_body = await request.body()
    try:
        data = yaml.safe_load(raw_body)
    except yaml.YAMLError:
        raise HTTPException(status_code=422, detail="Invalid YAML")
    try:
        item = Item.model_validate(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False))
    return item
```

`Item.model_json_schema()`로 스키마를 만들고, 같은 모델의 `model_validate()`로 수동 검증한다. FastAPI의 자동 JSON 파싱·검증은 사용하지 않는다.

추가 응답만 문서화하려면 `openapi_extra`보다 [추가 응답(responses)](../responses/additional-responses.md)이 편하다.

## 관련 페이지

- [응답 모델](../responses/response-model.md) — `response_model`과 관련 파라미터
- [데코레이터 의존성](../dependencies/decorator-and-global-dependencies.md) — `dependencies=[...]`
- [OpenAPI 콜백과 웹훅](../openapi/callbacks-and-webhooks.md) — `callbacks`
- [Request 객체 직접 사용](../request/using-request-directly.md)
