---
type: guide
title: 스키마 예제 선언
description: 문서(/docs)에 요청 예제를 표시하는 방법—Pydantic model_config의 json_schema_extra, Field(examples=[...]), Path/Query/Header/Cookie/Body/Form/File의 examples(JSON Schema 예제 리스트)와 openapi_examples(summary·description·value를 가진 OpenAPI 전용 예제 dict)—와 example/examples의 역사적 차이를 설명한다.
tags: [openapi, json-schema, examples, openapi-examples, pydantic, docs]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-f850ad8b6b3141eeb84cde3c
    resource: repo://docs_src/schema_extra_example/tutorial001_py310.py
  - id: openwiki-source-dc5000a0b05c97d273f8f89c
    resource: repo://docs_src/schema_extra_example/tutorial002_py310.py
  - id: openwiki-source-85aa3d959afff18201e713bf
    resource: repo://docs_src/schema_extra_example/tutorial004_an_py310.py
  - id: openwiki-source-71a4977d3025dd530ef71572
    resource: repo://docs_src/schema_extra_example/tutorial005_an_py310.py
  - id: openwiki-source-106f497dd08938cd7251aaf0
    resource: repo://docs/en/docs/tutorial/schema-extra-example.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 스키마 예제 선언

앱이 받을 수 있는 데이터의 예제를 선언해 자동 문서에 표시할 수 있다. 여러 방법이 있다.

## Pydantic 모델의 추가 JSON Schema 데이터

`model_config`의 `"json_schema_extra"`에 딕셔너리를 넣으면, 그 내용이 모델의 **JSON Schema**에 그대로 추가되어 API 문서에 사용된다. `examples`도 여기에 넣는다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 3.2,
                }
            ]
        }
    }


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    results = {"item_id": item_id, "item": item}
    return results
```

같은 기법으로 프런트엔드 UI용 메타데이터 같은 사용자 정의 정보도 JSON Schema에 추가할 수 있다.

> OpenAPI 3.1.0(FastAPI 0.99.0부터 사용)은 JSON Schema 표준의 `examples`(리스트)를 지원한다. 그 이전의 단일 `example` 키워드도 여전히 지원되지만 deprecated이며 JSON Schema 표준이 아니므로 `examples`로 옮기는 것을 권장한다.

## Field의 examples

```Python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class Item(BaseModel):
    name: str = Field(examples=["Foo"])
    description: str | None = Field(default=None, examples=["A very nice Item"])
    price: float = Field(examples=[35.4])
    tax: float | None = Field(default=None, examples=[3.2])
```

필드별 예제가 모델 JSON Schema의 각 속성에 추가된다([본문 Field](../request/request-body.md)).

## 파라미터 함수의 examples (JSON Schema)

`Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()`, `File()`에도 `examples` 리스트를 선언할 수 있으며, OpenAPI 안의 해당 데이터 **JSON Schema**에 추가된다.

```Python
from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Annotated[
        Item,
        Body(
            examples=[
                {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 3.2,
                }
            ],
        ),
    ],
):
    results = {"item_id": item_id, "item": item}
    return results
```

### 여러 examples

```Python
item: Annotated[
    Item,
    Body(
        examples=[
            {"name": "Foo", "description": "A very nice Item", "price": 35.4, "tax": 3.2},
            {"name": "Bar", "price": "35.4"},
            {"name": "Baz", "price": "thirty five point four"},
        ],
    ),
]
```

예제들은 본문 데이터의 JSON Schema 일부가 된다. 다만 문서 작성 시점 기준으로 Swagger UI는 JSON Schema 안의 **여러 예제를 표시하지 못한다**. 그래서 아래 `openapi_examples`를 쓴다.

## OpenAPI 전용 예제: openapi_examples

JSON Schema가 `examples`를 지원하기 전부터 OpenAPI에는 다른 `examples` 필드가 있었다. 이 필드는 각 JSON Schema 안이 아니라 **경로 작업의 세부(파라미터/미디어 타입)**에 들어가며, Swagger UI가 오래전부터 지원해 문서 UI에 여러 예제를 **선택 가능하게 표시**한다.

FastAPI에서는 `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()`, `File()`의 **`openapi_examples`** 파라미터로 선언한다(FastAPI 0.103.0+). 형식은 리스트가 아니라 **딕셔너리**다.

- 키: 각 예제의 식별자
- 값: 다음 키를 가진 딕셔너리
  - `summary`: 짧은 설명
  - `description`: Markdown 가능한 긴 설명
  - `value`: 실제 예제 값(예: `dict`)
  - `externalValue`: `value` 대신 예제를 가리키는 URL(지원 도구가 적음)

```Python
from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


@app.put("/items/{item_id}")
async def update_item(
    *,
    item_id: int,
    item: Annotated[
        Item,
        Body(
            openapi_examples={
                "normal": {
                    "summary": "A normal example",
                    "description": "A **normal** item works correctly.",
                    "value": {
                        "name": "Foo",
                        "description": "A very nice Item",
                        "price": 35.4,
                        "tax": 3.2,
                    },
                },
                "converted": {
                    "summary": "An example with converted data",
                    "description": "FastAPI can convert price `strings` to actual `numbers` automatically",
                    "value": {
                        "name": "Bar",
                        "price": "35.4",
                    },
                },
                "invalid": {
                    "summary": "Invalid data is rejected with an error",
                    "value": {
                        "name": "Baz",
                        "price": "thirty five point four",
                    },
                },
            },
        ),
    ],
):
    results = {"item_id": item_id, "item": item}
    return results
```

`/docs`에서 "normal", "converted", "invalid" 예제를 드롭다운으로 선택할 수 있다.

## 정리: examples vs openapi_examples

| 위치 | 파라미터 | 형식 | 들어가는 곳 | Swagger UI 다중 표시 |
| --- | --- | --- | --- | --- |
| Pydantic 모델 | `model_config["json_schema_extra"]["examples"]`, `Field(examples=...)` | 리스트 | 모델 JSON Schema | 첫 예제 위주 |
| 파라미터 함수 | `examples=` | 리스트 | 파라미터/본문 JSON Schema | 제한적 |
| 파라미터 함수 | `openapi_examples=` | dict(`summary`, `description`, `value`, `externalValue`) | 경로 작업의 Parameter/Media Type 객체 | 지원 |

## 기술적 배경(요약)

- OpenAPI 3.1.0 이전에는 수정된 구버전 JSON Schema를 써서 자체 `example` 필드를 추가했고, Parameter Object(`Path`/`Query`/`Header`/`Cookie`)와 Request Body의 Media Type Object(`Body`/`File`/`Form`)에도 `example`/`examples`를 두었다.
- 이후 JSON Schema(2019-09, 2020-12)가 리스트 형식 `examples`를 추가했고, 이를 기반으로 한 OpenAPI 3.1.0에서는 이 `examples`가 deprecated된 단일 `example`보다 우선한다.
- Swagger UI는 5.0.0부터 OpenAPI 3.1.0을 지원하며, FastAPI 0.99.0 이전은 3.1.0 미만 OpenAPI를 사용했다.
- 0.99.0 이전에는 `Query()`, `Body()` 등의 예제가 JSON Schema가 아니라 경로 작업에 직접 들어갔다. 이 옛 OpenAPI 전용 방식이 0.103.0부터 `openapi_examples`가 되었다.

요컨대 FastAPI 0.99.0 이상을 쓰면 훨씬 단순하고 일관적이다.

## 관련 페이지

- [요청 본문](../request/request-body.md)
- [쿼리 파라미터](../request/query-parameters.md)
- [OpenAPI 확장과 문서 UI](../openapi/customizing-openapi-and-docs-ui.md)
