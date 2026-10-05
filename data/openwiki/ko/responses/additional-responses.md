---
type: guide
title: OpenAPI 추가 응답 선언
description: 경로 작업 데코레이터(및 APIRouter·include_router)의 responses 파라미터로 상태 코드별 응답을 OpenAPI에 문서화하는 방법—model 키로 Pydantic 스키마 참조, 주 응답에 image/png 같은 추가 미디어 타입, response_model·status_code와 정보 결합(description, example), **dict 언패킹으로 사전 정의 응답 재사용—과 실제 응답은 직접 반환해야 한다는 점을 설명한다.
tags: [openapi, responses, additional-responses, documentation, status-codes]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-7cc48311268aa0d38d19fddb
    resource: repo://docs_src/additional_responses/tutorial001_py310.py
  - id: openwiki-source-519b9f75ea66441d1eec4826
    resource: repo://docs_src/additional_responses/tutorial002_py310.py
  - id: openwiki-source-60dfdf714574820fae613649
    resource: repo://docs_src/additional_responses/tutorial003_py310.py
  - id: openwiki-source-50c6831cad808f0578ac1cad
    resource: repo://docs_src/additional_responses/tutorial004_py310.py
  - id: openwiki-source-724e759f2e2841d6ad6ccb8b
    resource: repo://docs/en/docs/advanced/additional-responses.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# OpenAPI 추가 응답 선언

> 다소 고급 주제다. FastAPI를 막 시작했다면 필요 없을 수 있다.

추가 상태 코드, 미디어 타입, 설명 등을 가진 **추가 응답**을 선언할 수 있다. 이 응답들은 OpenAPI 스키마에 포함되어 문서에 나타난다. 단, 추가 응답은 **문서화만** 할 뿐이므로, 실제로는 `JSONResponse` 같은 `Response`를 상태 코드·내용과 함께 **직접 반환**해야 한다([상태 코드](./status-codes.md), [응답 직접 반환](./custom-responses.md)).

## model을 가진 추가 응답

경로 작업 데코레이터에 `responses` 파라미터를 넘긴다. 키는 상태 코드(예: `200`), 값은 각 응답 정보를 담은 `dict`다. 각 응답 `dict`에는 `response_model`처럼 Pydantic 모델을 담는 `model` 키를 둘 수 있다.

```Python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Item(BaseModel):
    id: str
    value: str


class Message(BaseModel):
    message: str


app = FastAPI()


@app.get("/items/{item_id}", response_model=Item, responses={404: {"model": Message}})
async def read_item(item_id: str):
    if item_id == "foo":
        return {"id": "foo", "value": "there goes my hero"}
    return JSONResponse(status_code=404, content={"message": "Item not found"})
```

- `model` 키는 OpenAPI의 일부가 아니다. FastAPI가 모델의 JSON Schema를 생성해 올바른 위치, 즉 `content` → 미디어 타입(예: `application/json`) → `schema`에 넣는다.
- 스키마를 직접 넣지 않고 OpenAPI 전역 스키마(`#/components/schemas/Message`)에 대한 **참조**로 넣으므로, 다른 앱과 클라이언트가 그 스키마를 재사용하고 코드 생성 도구가 더 잘 동작한다.
- 생성된 응답에는 `200`(`Item`), `404`(`Message`), 그리고 자동으로 추가되는 `422`(검증 오류, `HTTPValidationError`)가 포함된다.

## 주 응답의 추가 미디어 타입

같은 `responses` 파라미터로 주 응답에 다른 미디어 타입을 추가할 수 있다. 예: JSON 또는 PNG 이미지를 반환.

```Python
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


class Item(BaseModel):
    id: str
    value: str


app = FastAPI()


@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Return the JSON item or an image.",
        }
    },
)
async def read_item(item_id: str, img: bool | None = None):
    if img:
        return FileResponse("image.png", media_type="image/png")
    else:
        return {"id": "foo", "value": "there goes my hero"}
```

- 이미지는 `FileResponse`로 직접 반환해야 한다.
- `responses`에 다른 미디어 타입을 명시하지 않으면 FastAPI는 추가 응답이 주 응답 클래스와 같은 미디어 타입(기본 `application/json`)이라고 가정한다. 미디어 타입이 `None`인 사용자 정의 응답 클래스를 쓰면, 모델이 연결된 추가 응답에는 `application/json`을 사용한다.

## 정보 결합

`response_model`, `status_code`, `responses`의 정보를 결합할 수 있다. 기본 상태 코드 `200`(또는 지정한 코드)로 `response_model`을 선언하고, 같은 응답에 대한 추가 정보를 `responses`에 직접 OpenAPI 형식으로 선언하면 FastAPI가 모델의 JSON Schema와 합친다.

```Python
@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={
        404: {"model": Message, "description": "The item was not found"},
        200: {
            "description": "Item requested by ID",
            "content": {
                "application/json": {
                    "example": {"id": "bar", "value": "The bar tenders"}
                }
            },
        },
    },
)
async def read_item(item_id: str):
    if item_id == "foo":
        return {"id": "foo", "value": "there goes my hero"}
    else:
        return JSONResponse(status_code=404, content={"message": "Item not found"})
```

- `404`: Pydantic 모델 + 사용자 정의 `description`
- `200`: `response_model`의 스키마 + 사용자 정의 `description`과 `example`

## 사전 정의 응답과 결합

여러 경로 작업에 공통으로 쓸 응답을 정의하고, 각 경로 작업의 응답과 합치려면 Python의 `**dict` 언패킹을 쓴다.

```Python
old_dict = {"old key": "old value", "second old key": "second old value"}
new_dict = {**old_dict, "new key": "new value"}
```

```Python
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


class Item(BaseModel):
    id: str
    value: str


responses = {
    404: {"description": "Item not found"},
    302: {"description": "The item was moved"},
    403: {"description": "Not enough privileges"},
}


app = FastAPI()


@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={**responses, 200: {"content": {"image/png": {}}}},
)
async def read_item(item_id: str, img: bool | None = None):
    if img:
        return FileResponse("image.png", media_type="image/png")
    else:
        return {"id": "foo", "value": "there goes my hero"}
```

라우터 단위로 공통 응답을 붙이려면 `APIRouter(responses=...)` 또는 `include_router(..., responses=...)`를 쓴다. 라우터와 경로 작업의 응답이 합쳐진다([큰 애플리케이션](../app-structure/bigger-applications.md)).

## 응답에 넣을 수 있는 것

`responses`의 각 응답에는 OpenAPI [Response Object](https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.1.0.md#response-object)의 모든 필드(`description`, `headers`, `content`, `links` 등)를 직접 넣을 수 있다. 전체 구조는 [Responses Object](https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.1.0.md#responses-object)를 참고한다.

## 관련 페이지

- [상태 코드](./status-codes.md)
- [응답 직접 반환과 커스텀 응답](./custom-responses.md)
- [오류 처리](../errors/handling-errors.md)
- [경로 작업 설정](../app-structure/path-operation-configuration.md) — `openapi_extra`
