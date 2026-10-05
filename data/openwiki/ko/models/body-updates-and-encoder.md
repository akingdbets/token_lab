---
type: guide
title: 본문 업데이트(PUT/PATCH)와 jsonable_encoder
description: fastapi.encoders.jsonable_encoder로 Pydantic 모델·datetime 등을 JSON 호환 dict/list로 변환하는 방법과 지원 타입·옵션, PUT으로 전체 교체할 때 기본값이 덮어쓰는 함정, PATCH 부분 업데이트(model_dump(exclude_unset=True) + model_copy(update=...)) 패턴을 설명한다.
tags: [jsonable-encoder, put, patch, partial-update, pydantic, serialization]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-5f519de595b6849750f292ab
    resource: repo://docs_src/body_updates/tutorial001_py310.py
  - id: openwiki-source-bff631448023340ec732b8ef
    resource: repo://docs_src/body_updates/tutorial002_py310.py
  - id: openwiki-source-8757c8be1c8c9c702c8a82f0
    resource: repo://docs_src/encoder/tutorial001_py310.py
  - id: openwiki-source-46c2c90f17a97455b57ac0a9
    resource: repo://docs/en/docs/tutorial/body-updates.md
  - id: openwiki-source-bda410309c91cfcf3f7efe1b
    resource: repo://docs/en/docs/tutorial/encoder.md
  - id: openwiki-source-658293c5ba0aa1bcd6505fc5
    resource: repo://fastapi/encoders.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 본문 업데이트(PUT/PATCH)와 jsonable_encoder

## JSON 호환 인코더: jsonable_encoder

Pydantic 모델 같은 데이터 타입을 `dict`, `list` 등 **JSON과 호환되는** 형태로 바꿔야 할 때가 있다(예: JSON만 받는 DB에 저장). FastAPI는 `jsonable_encoder()`를 제공한다.

```Python
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

fake_db = {}


class Item(BaseModel):
    title: str
    timestamp: datetime
    description: str | None = None


app = FastAPI()


@app.put("/items/{id}")
def update_item(id: str, item: Item):
    json_compatible_item_data = jsonable_encoder(item)
    fake_db[id] = json_compatible_item_data
```

- Pydantic 모델은 `dict`로, `datetime`은 [ISO 형식](https://en.wikipedia.org/wiki/ISO_8601) `str`로 변환된다.
- 결과는 JSON 형식의 큰 **문자열이 아니라**, 값과 하위 값이 모두 JSON 호환인 Python 표준 자료구조(`dict` 등)다. 표준 `json.dumps()`로 인코딩할 수 있다.
- FastAPI도 응답 모델이 없을 때 반환값을 변환하는 데 내부적으로 사용한다([요청 처리 흐름](../internals/request-lifecycle.md)).

### 기본 변환 규칙(일부)

| 타입 | 변환 결과 |
| --- | --- |
| `datetime.date`/`datetime`/`time` | ISO 형식 문자열(`.isoformat()`) |
| `timedelta` | 총 초(`float`) |
| `Decimal` | 지수가 0 이상이면 `int`, 아니면 `float` (예: `Decimal("1")` → `1`, `Decimal("1.0")` → `1.0`) |
| `Enum` | `.value` |
| `UUID`, `Path`, `IPv4Address` 등, `SecretStr`, `Url`/`AnyUrl`, `NameEmail`, `Color` | `str` |
| `bytes` | `.decode()` 결과 문자열 |
| `set`, `frozenset` | `list` |
| 정규식 `Pattern` | `.pattern` |

### 주요 파라미터

`jsonable_encoder(obj, include=None, exclude=None, by_alias=True, exclude_unset=False, exclude_defaults=False, exclude_none=False, custom_encoder=None, sqlalchemy_safe=True)`

- `include`/`exclude`, `exclude_unset`/`exclude_defaults`/`exclude_none`, `by_alias`: Pydantic 모델 직렬화 옵션
- `custom_encoder`: `{타입: 변환함수}` 딕셔너리로 기본 규칙을 덮어쓴다.
- `sqlalchemy_safe`: SQLAlchemy 내부 속성(`_sa_` 접두사)을 제외한다.

예외 핸들러에서 `exc.errors()`와 `exc.body`를 JSON으로 만들 때도 쓴다([오류 처리](../errors/handling-errors.md)).

## PUT으로 전체 교체

[HTTP `PUT`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/PUT)은 기존 데이터를 **대체**할 데이터를 받는다.

```Python
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    tax: float = 10.5
    tags: list[str] = []


items = {
    "foo": {"name": "Foo", "price": 50.2},
    "bar": {"name": "Bar", "description": "The bartenders", "price": 62, "tax": 20.2},
    "baz": {"name": "Baz", "description": None, "price": 50.2, "tax": 10.5, "tags": []},
}


@app.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: str):
    return items[item_id]


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, item: Item):
    update_item_encoded = jsonable_encoder(item)
    items[item_id] = update_item_encoded
    return update_item_encoded
```

### 교체 시 주의

`bar`를 다음 본문으로 `PUT`하면:

```Python
{
    "name": "Barz",
    "price": 3,
    "description": None,
}
```

이미 저장된 `"tax": 20.2`가 본문에 없으므로 입력 모델의 기본값 `"tax": 10.5`가 적용되고, 그 "새" 값으로 저장된다.

## PATCH로 부분 업데이트

[HTTP `PATCH`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/PATCH)는 바꿀 데이터만 보내고 나머지는 그대로 두는 **부분** 업데이트에 쓴다. `PATCH`는 `PUT`보다 덜 쓰이며, 많은 팀이 부분 업데이트에도 `PUT`만 쓴다. FastAPI는 어떤 제약도 두지 않는다.

```Python
@app.patch("/items/{item_id}")
async def update_item(item_id: str, item: Item) -> Item:
    stored_item_data = items[item_id]
    stored_item_model = Item(**stored_item_data)
    update_data = item.model_dump(exclude_unset=True)
    updated_item = stored_item_model.model_copy(update=update_data)
    items[item_id] = jsonable_encoder(updated_item)
    return updated_item
```

### exclude_unset

`item.model_dump(exclude_unset=True)`는 `item` 모델을 만들 때 **실제로 설정된 값만** 담은 `dict`를 만든다(기본값 제외). 그래서 사용자가 보내지 않은 필드가 기본값으로 덮어써지지 않는다.

### model_copy(update=...)

기존 모델의 복사본을 `.model_copy()`로 만들고, `update` 파라미터에 바꿀 데이터 `dict`를 넘긴다.

### 부분 업데이트 순서 요약

1. (선택) `PUT` 대신 `PATCH` 사용
2. 저장된 데이터 조회
3. 그 데이터를 Pydantic 모델에 넣기
4. 입력 모델에서 `exclude_unset`으로 기본값 없는 `dict` 생성
5. 저장된 모델의 복사본을 `update` 파라미터로 갱신
6. 복사본을 DB에 저장 가능한 형태로 변환(예: `jsonable_encoder` — `model_dump()`와 비슷하지만 `datetime` → `str`처럼 JSON 호환 타입으로 변환까지 보장)
7. DB에 저장하고 갱신된 모델 반환

같은 기법을 `PUT`에도 쓸 수 있다.

> 입력 모델은 여전히 **검증**된다. 모든 속성을 생략할 수 있는 부분 업데이트를 받으려면 모든 속성을 선택적(기본값 또는 `None`)으로 선언한 모델이 필요하다. 생성용(필수 값) 모델과 업데이트용(모두 선택) 모델을 나누는 방법은 [추가 모델](./extra-models-and-dataclasses.md)을, SQLModel에서의 `sqlmodel_update()` 사용은 [SQL 데이터베이스](../integrations/sql-databases.md)를 참고한다.

## 관련 페이지

- [응답 모델](../responses/response-model.md) — `response_model_exclude_unset`
- [응답 직접 반환](../responses/custom-responses.md) — `JSONResponse`에 넣기 전 `jsonable_encoder` 사용
- [중첩 모델과 추가 데이터 타입](../request/nested-models-and-data-types.md)
