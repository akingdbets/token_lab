---
type: guide
title: 중첩 모델과 추가 데이터 타입
description: 요청 본문에서 list[str]·set[str] 같은 타입 파라미터 필드, 하위 모델 중첩, HttpUrl 같은 특수 타입, 모델 리스트·깊은 중첩, list/dict 본문(dict[int, float])을 쓰는 방법과 UUID·datetime·date·time·timedelta·frozenset·bytes·Decimal 등 추가 데이터 타입의 표현, val_json_bytes/ser_json_bytes로 JSON 안의 base64 bytes를 처리하는 방법을 설명한다.
tags: [pydantic, nested-models, data-types, uuid, datetime, base64, request-body]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-7e79b62ecf86fb9fa481c885
    resource: repo://docs_src/body_nested_models/tutorial004_py310.py
  - id: openwiki-source-92fa33475811879f431f1ad6
    resource: repo://docs_src/body_nested_models/tutorial005_py310.py
  - id: openwiki-source-43421045c6ebf2c5687db002
    resource: repo://docs_src/body_nested_models/tutorial007_py310.py
  - id: openwiki-source-041961d82f16e30f23809b5d
    resource: repo://docs_src/body_nested_models/tutorial008_py310.py
  - id: openwiki-source-bf51b965cdd7f0dad647e4d2
    resource: repo://docs_src/body_nested_models/tutorial009_py310.py
  - id: openwiki-source-83976647ebab5c40786b8b7d
    resource: repo://docs_src/extra_data_types/tutorial001_an_py310.py
  - id: openwiki-source-2bda54f1ef92ef644bcaf7ce
    resource: repo://docs_src/json_base64_bytes/tutorial001_py310.py
  - id: openwiki-source-cba9b46e921902a6e86b1318
    resource: repo://docs/en/docs/advanced/json-base64-bytes.md
  - id: openwiki-source-8b4440a8f2c3ab7672e432e2
    resource: repo://docs/en/docs/tutorial/body-nested-models.md
  - id: openwiki-source-b9633307ba09f9f9d701465c
    resource: repo://docs/en/docs/tutorial/extra-data-types.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 중첩 모델과 추가 데이터 타입

FastAPI에서는 (Pydantic 덕분에) 임의로 깊게 중첩된 모델을 정의·검증·문서화할 수 있다.

## 리스트·집합 필드

```Python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list = []          # 요소 타입 미지정
```

내부 타입을 지정하려면 타입 파라미터를 쓴다.

```Python
class Item(BaseModel):
    ...
    tags: list[str] = []     # 문자열 리스트
```

태그는 중복되면 안 되므로 `set`이 더 적절하다.

```Python
class Item(BaseModel):
    ...
    tags: set[str] = set()
```

중복 데이터를 보내도 고유한 항목의 집합으로 변환되고, 응답으로 내보낼 때도(원본에 중복이 있어도) 고유 항목의 집합으로 직렬화되며 문서에도 그렇게 표시된다.

## 중첩 모델

Pydantic 모델의 속성 타입으로 다른 Pydantic 모델을 쓸 수 있다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Image(BaseModel):
    url: str
    name: str


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()
    image: Image | None = None


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    results = {"item_id": item_id, "item": item}
    return results
```

다음과 같은 본문을 기대하며, 에디터 지원·데이터 변환·검증·자동 문서화가 중첩 모델에도 적용된다.

```JSON
{
    "name": "Foo",
    "description": "The pretender",
    "price": 42.0,
    "tax": 3.2,
    "tags": ["rock", "metal", "bar"],
    "image": {
        "url": "http://example.com/baz.jpg",
        "name": "The Foo live"
    }
}
```

## 특수 타입: HttpUrl 등

`str`, `int`, `float` 외에 `str`을 상속한 복잡한 단일 타입도 쓸 수 있다. 예를 들어 URL은 `HttpUrl`로 선언하면 유효한 URL인지 검사되고 JSON Schema/OpenAPI에도 그렇게 문서화된다. 전체 목록은 [Pydantic 타입 개요](https://pydantic.dev/docs/validation/latest/concepts/types/)를 참고한다.

```Python
from pydantic import BaseModel, HttpUrl


class Image(BaseModel):
    url: HttpUrl
    name: str
```

## 하위 모델 리스트

```Python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()
    images: list[Image] | None = None
```

```JSON
{
    "name": "Foo",
    "tags": ["rock", "metal", "bar"],
    "images": [
        {"url": "http://example.com/baz.jpg", "name": "The Foo live"},
        {"url": "http://example.com/dave.jpg", "name": "The Baz"}
    ]
}
```

## 깊은 중첩

```Python
class Offer(BaseModel):
    name: str
    description: str | None = None
    price: float
    items: list[Item]


@app.post("/offers/")
async def create_offer(offer: Offer):
    return offer
```

`Offer`는 `Item` 리스트를, 각 `Item`은 선택적 `Image` 리스트를 가진다.

## 순수 리스트 본문

JSON 본문 최상위가 배열이면 함수 파라미터 타입으로 선언한다.

```Python
@app.post("/images/multiple/")
async def create_multiple_images(images: list[Image]):
    return images
```

## 임의의 dict 본문

키 이름을 미리 모르거나 키를 다른 타입(예: `int`)으로 받고 싶을 때 `dict`로 선언한다.

```Python
@app.post("/index-weights/")
async def create_index_weights(weights: dict[int, float]):
    return weights
```

JSON은 키로 `str`만 지원하지만, 문자열이 순수 정수라면 Pydantic이 변환·검증하므로 `weights`는 실제로 `int` 키와 `float` 값을 가진다.

## 추가 데이터 타입

`int`, `float`, `str`, `bool` 외에도 다양한 타입을 쓸 수 있으며, 에디터 지원·요청/응답 데이터 변환·검증·자동 문서화가 동일하게 동작한다.

| 타입 | 요청·응답에서의 표현 |
| --- | --- |
| `UUID` | `str` |
| `datetime.datetime` | ISO 8601 `str`, 예: `2008-09-15T15:53:00+05:00` |
| `datetime.date` | ISO 8601 `str`, 예: `2008-09-15` |
| `datetime.time` | ISO 8601 `str`, 예: `14:23:55.003` |
| `datetime.timedelta` | 총 초 `float` (Pydantic은 ISO 8601 time diff 인코딩도 지원) |
| `frozenset` | 요청에서는 리스트를 읽어 중복 제거 후 `set`으로, 응답에서는 `list`로 |
| `bytes` | `str` (스키마에 `binary` format으로 표시) |
| `Decimal` | `float`처럼 처리 |

```Python
from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Body, FastAPI

app = FastAPI()


@app.put("/items/{item_id}")
async def read_items(
    item_id: UUID,
    start_datetime: Annotated[datetime, Body()],
    end_datetime: Annotated[datetime, Body()],
    process_after: Annotated[timedelta, Body()],
    repeat_at: Annotated[time | None, Body()] = None,
):
    start_process = start_datetime + process_after
    duration = end_datetime - start_process
    return {
        "item_id": item_id,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "process_after": process_after,
        "repeat_at": repeat_at,
        "start_process": start_process,
        "duration": duration,
    }
```

함수 안의 파라미터는 실제 Python 타입(`datetime` 등)이므로 날짜 연산을 그대로 할 수 있다. 응답으로 보낼 때의 변환 규칙은 [jsonable_encoder](../models/body-updates-and-encoder.md)와 같다.

## JSON 안의 bytes를 base64로

JSON은 UTF-8 문자열만 담을 수 있어 원시 바이트를 넣을 수 없다. 가능하면 업로드는 [파일](./forms-and-files.md), 다운로드는 [`FileResponse`](../responses/custom-responses.md)를 쓰는 것이 낫다. base64는 원본보다 많은 문자를 쓰므로 비효율적이며, JSON에 이진 데이터를 꼭 넣어야 할 때만 쓴다.

Pydantic 모델의 `bytes` 필드에 모델 설정으로 base64를 지정한다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel


class DataInput(BaseModel):
    description: str
    data: bytes

    model_config = {"val_json_bytes": "base64"}


class DataOutput(BaseModel):
    description: str
    data: bytes

    model_config = {"ser_json_bytes": "base64"}


class DataInputOutput(BaseModel):
    description: str
    data: bytes

    model_config = {
        "val_json_bytes": "base64",
        "ser_json_bytes": "base64",
    }


app = FastAPI()


@app.post("/data")
def post_data(body: DataInput):
    content = body.data.decode("utf-8")
    return {"description": body.description, "content": content}


@app.get("/data")
def get_data() -> DataOutput:
    data = "hello".encode("utf-8")
    return DataOutput(description="A plumbus", data=data)


@app.post("/data-in-out")
def post_data_in_out(body: DataInputOutput) -> DataInputOutput:
    return body
```

- `val_json_bytes="base64"`: 입력 JSON을 **검증**할 때 base64 문자열을 바이트로 디코딩한다. `{"description": "Some data", "data": "aGVsbG8="}`(`aGVsbG8=`는 `hello`의 base64)를 보내면 `{"description": "Some data", "content": "hello"}`를 받는다. `/docs`에도 base64 인코딩된 bytes로 표시된다.
- `ser_json_bytes="base64"`: JSON 응답을 만들 때 바이트를 base64로 **직렬화**한다.
- 두 설정을 함께 쓰면 입력과 출력 모두 base64로 처리한다.

## 관련 페이지

- [요청 본문](./request-body.md)
- [추가 모델과 dataclasses](../models/extra-models-and-dataclasses.md)
- [스키마 예제](../models/schema-examples.md)
