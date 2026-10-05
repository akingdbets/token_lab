---
type: guide
title: 쿼리 파라미터, 문자열 검증, 쿼리 파라미터 모델
description: 경로에 없는 함수 파라미터가 쿼리 파라미터가 되는 규칙, 기본값·선택·필수 파라미터와 bool 변환, Annotated + Query()로 min_length/max_length/pattern 검증과 title/description/alias/deprecated/include_in_schema 메타데이터, 리스트(다중 값) 쿼리, AfterValidator 사용자 검증, Pydantic 모델로 쿼리 파라미터 묶기와 extra="forbid"를 설명한다.
tags: [query-parameters, validation, query, annotated, aftervalidator, query-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-c3463ac642282d1295429819
    resource: repo://docs_src/query_param_models/tutorial001_an_py310.py
  - id: openwiki-source-f9fab8c4c0cd9a48fc290d64
    resource: repo://docs_src/query_param_models/tutorial002_an_py310.py
  - id: openwiki-source-bfecd207b62fd1add418af15
    resource: repo://docs_src/query_params_str_validations/tutorial004_an_py310.py
  - id: openwiki-source-4c543e970630d93ac9d2bc3c
    resource: repo://docs_src/query_params_str_validations/tutorial010_an_py310.py
  - id: openwiki-source-82bd0c2cd2f545b07ca9b4a9
    resource: repo://docs_src/query_params_str_validations/tutorial011_an_py310.py
  - id: openwiki-source-5a46921e30adc93528f07e41
    resource: repo://docs_src/query_params_str_validations/tutorial012_an_py310.py
  - id: openwiki-source-8d52852e029948a6134be659
    resource: repo://docs_src/query_params_str_validations/tutorial014_an_py310.py
  - id: openwiki-source-9002331d6a69fc47a47e97a1
    resource: repo://docs_src/query_params_str_validations/tutorial015_an_py310.py
  - id: openwiki-source-374e6010bbc0a7d7ac10f0c2
    resource: repo://docs_src/query_params/tutorial001_py310.py
  - id: openwiki-source-524e20dee9eff970905e78f1
    resource: repo://docs_src/query_params/tutorial002_py310.py
  - id: openwiki-source-a953d8b52b06de4ee9a15262
    resource: repo://docs_src/query_params/tutorial003_py310.py
  - id: openwiki-source-700f99a650ff27760c56f474
    resource: repo://docs_src/query_params/tutorial005_py310.py
  - id: openwiki-source-a9c8a0f197e19dedb80dd9dd
    resource: repo://docs/en/docs/tutorial/query-params-str-validations.md
  - id: openwiki-source-b32b25e66b7af40f3eae0f8b
    resource: repo://docs/en/docs/tutorial/query-params.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 쿼리 파라미터, 문자열 검증, 쿼리 파라미터 모델

## 기본

경로 파라미터가 아닌 함수 파라미터는 자동으로 **쿼리 파라미터**로 해석된다.

```Python
from fastapi import FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


@app.get("/items/")
async def read_item(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]
```

쿼리는 URL의 `?` 뒤에 `&`로 구분된 키-값 쌍이다: `http://127.0.0.1:8000/items/?skip=0&limit=10`. URL에서는 문자열이지만 Python 타입으로 선언하면 변환·검증되고 문서화된다. 경로의 고정 부분이 아니므로 선택적이며 기본값을 가질 수 있다. `/items/?skip=20`이면 `skip=20`, `limit=10`(기본값)이다.

### 선택적 파라미터

```Python
@app.get("/items/{item_id}")
async def read_item(item_id: str, q: str | None = None):
    if q:
        return {"item_id": item_id, "q": q}
    return {"item_id": item_id}
```

기본값이 `None`이면 선택적이다. FastAPI는 `item_id`는 경로 파라미터, `q`는 쿼리 파라미터임을 스스로 판별한다.

### bool 변환

```Python
@app.get("/items/{item_id}")
async def read_item(item_id: str, q: str | None = None, short: bool = False):
    ...
```

`?short=1`, `?short=True`, `?short=true`, `?short=on`, `?short=yes`(대소문자 무관)는 `True`, 그 밖에는 `False`로 변환된다.

### 여러 경로·쿼리 파라미터

여러 경로 파라미터와 쿼리 파라미터를 동시에, 어떤 순서로든 선언할 수 있다. 이름으로 구분된다.

```Python
@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(
    user_id: int, item_id: str, q: str | None = None, short: bool = False
):
    ...
```

### 필수 쿼리 파라미터

기본값을 선언하지 않으면 필수다.

```Python
@app.get("/items/{item_id}")
async def read_user_item(item_id: str, needy: str):
    item = {"item_id": item_id, "needy": needy}
    return item
```

`needy` 없이 요청하면 `"type": "missing"`, `"loc": ["query", "needy"]`, `"msg": "Field required"` 오류가 반환된다. 필수, 기본값 있음, 완전 선택을 섞을 수 있다.

```Python
async def read_user_item(
    item_id: str, needy: str, skip: int = 0, limit: int | None = None
):
    ...
```

경로 파라미터처럼 `Enum`도 쓸 수 있다([경로 파라미터](./path-parameters.md)).

## Query()로 추가 검증

`Annotated`(FastAPI 0.95.0+)로 타입을 감싸고 그 안에 `Query`를 넣는다.

```Python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/items/")
async def read_items(q: Annotated[str | None, Query(max_length=50)] = None):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results
```

기본값이 여전히 `None`이므로 선택적이며, 값이 있으면 최대 50자인지 **검증**하고, 위반 시 명확한 오류를 반환하며, OpenAPI에 **문서화**한다.

### 옛 방식: Query를 기본값으로

FastAPI 0.95.0 이전 코드에서는 `Query`를 함수 파라미터 기본값으로 썼다.

```Python
q: str | None = Query(default=None, max_length=50)
```

- `Annotated` 안의 `Query`에는 `default`를 쓸 수 **없다**(`Annotated[str, Query(default="rick")] = "morty"`는 모호하므로 `AssertionError`). 함수 파라미터의 실제 기본값을 쓴다: `q: Annotated[str, Query()] = "rick"`.
- 새 코드에는 `Annotated`를 권장한다. 함수 기본값이 실제 기본값이라 FastAPI 밖에서 함수를 호출해도 예상대로 동작하고, 여러 메타데이터를 담을 수 있어 [Typer](https://typer.tiangolo.com/) 같은 도구와 함께 쓸 수도 있다.

### 문자열 검증

```Python
# 최소 길이
q: Annotated[str | None, Query(min_length=3, max_length=50)] = None

# 정규식
q: Annotated[
    str | None, Query(min_length=3, max_length=50, pattern="^fixedquery$")
] = None
```

`^fixedquery$`는 정확히 `fixedquery`인 값만 허용한다(`^` 시작, `$` 끝).

### 기본값과 필수 여부

```Python
# None 이외의 기본값 — 선택적
q: Annotated[str, Query(min_length=3)] = "fixedquery"

# 기본값 없음 — 필수
q: Annotated[str, Query(min_length=3)]

# None을 허용하지만 필수 (클라이언트는 값을 반드시 보내야 함)
q: Annotated[str | None, Query(min_length=3)]
```

`None`을 포함해 어떤 타입이든 기본값이 있으면 선택적이다.

## 리스트 / 다중 값

`Query`를 명시하면 같은 쿼리 파라미터를 여러 번 받을 수 있다.

```Python
@app.get("/items/")
async def read_items(q: Annotated[list[str] | None, Query()] = None):
    query_items = {"q": q}
    return query_items
```

`/items/?q=foo&q=bar` → `{"q": ["foo", "bar"]}`. `list` 타입은 **`Query`를 명시하지 않으면 요청 본문으로 해석**된다.

기본 리스트도 지정할 수 있다.

```Python
async def read_items(q: Annotated[list[str], Query()] = ["foo", "bar"]):
    ...
```

`list[str]` 대신 `list`만 쓰면 내용 타입은 검사(문서화)하지 않는다.

```Python
async def read_items(q: Annotated[list, Query()] = []):
    ...
```

## 메타데이터

OpenAPI와 문서 UI에 포함된다(도구마다 지원 수준은 다를 수 있음).

```Python
q: Annotated[
    str | None,
    Query(
        title="Query string",
        description="Query string for the items to search in the database that have a good match",
        min_length=3,
    ),
] = None
```

### alias

`item-query`처럼 유효한 Python 변수 이름이 아닌 파라미터 이름을 쓰려면 `alias`를 선언한다. 값을 찾을 때 alias가 사용된다.

```Python
async def read_items(q: Annotated[str | None, Query(alias="item-query")] = None):
    ...
```

`http://127.0.0.1:8000/items/?item-query=foobaritems`

### deprecated

클라이언트가 아직 쓰고 있어 남겨 두지만 문서에 사용 중단을 표시하려면 `deprecated=True`를 쓴다.

```Python
q: Annotated[
    str | None,
    Query(
        alias="item-query",
        title="Query string",
        description="Query string for the items to search in the database that have a good match",
        min_length=3,
        max_length=50,
        pattern="^fixedquery$",
        deprecated=True,
    ),
] = None
```

### OpenAPI에서 제외

```Python
async def read_items(
    hidden_query: Annotated[str | None, Query(include_in_schema=False)] = None,
):
    if hidden_query:
        return {"hidden_query": hidden_query}
    else:
        return {"hidden_query": "Not found"}
```

## 사용자 정의 검증: AfterValidator

위 파라미터로 할 수 없는 검증은 Pydantic의 [`AfterValidator`](https://pydantic.dev/docs/validation/latest/concepts/validators/#field-after-validator)를 `Annotated` 안에 넣어 일반 검증 **이후**에 적용한다(Pydantic v2 필요). `BeforeValidator` 등도 있다.

```Python
import random
from typing import Annotated

from fastapi import FastAPI
from pydantic import AfterValidator

app = FastAPI()

data = {
    "isbn-9781529046137": "The Hitchhiker's Guide to the Galaxy",
    "imdb-tt0371724": "The Hitchhiker's Guide to the Galaxy",
    "isbn-9781439512982": "Isaac Asimov: The Complete Stories, Vol. 2",
}


def check_valid_id(id: str):
    if not id.startswith(("isbn-", "imdb-")):
        raise ValueError('Invalid ID format, it must start with "isbn-" or "imdb-"')
    return id


@app.get("/items/")
async def read_items(
    id: Annotated[str | None, AfterValidator(check_valid_id)] = None,
):
    if id:
        item = data.get(id)
    else:
        id, item = random.choice(list(data.items()))
    return {"id": id, "name": item}
```

`ValueError`를 발생시키면 검증 오류(422)로 반환된다. DB나 다른 API 같은 **외부 컴포넌트**와 통신해야 하는 검증은 [의존성](../dependencies/dependency-injection-basics.md)으로 한다.

## 쿼리 파라미터 모델

관련된 쿼리 파라미터를 Pydantic 모델로 묶어 재사용하고 검증·메타데이터를 한 번에 선언한다(FastAPI 0.115.0+).

```Python
from typing import Annotated, Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []


@app.get("/items/")
async def read_items(filter_query: Annotated[FilterParams, Query()]):
    return filter_query
```

FastAPI가 쿼리 파라미터에서 **각 필드**를 추출해 모델을 만든다. 문서에도 각 쿼리 파라미터로 표시된다. `tags: list[str]`은 `?tags=a&tags=b`처럼 다중 값을 받는다.

### 추가 쿼리 파라미터 금지

```Python
class FilterParams(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []
```

`/items/?limit=10&tool=plumbus`처럼 추가 파라미터를 보내면 `"type": "extra_forbidden"`, `"loc": ["query", "tool"]` 오류가 반환된다.

같은 기법을 [헤더·쿠키](./headers-and-cookies.md), [폼](./forms-and-files.md)에도 쓸 수 있다.

## 관련 페이지

- [경로 파라미터와 숫자 검증](./path-parameters.md) — `gt`, `ge`, `lt`, `le`
- [요청 본문](./request-body.md)
- [의존성 주입 기초](../dependencies/dependency-injection-basics.md) — 공통 쿼리 파라미터를 의존성으로 공유
- [스키마 예제](../models/schema-examples.md) — `Query(examples=...)`, `openapi_examples`
