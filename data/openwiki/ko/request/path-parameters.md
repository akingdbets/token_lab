---
type: guide
title: 경로 파라미터와 숫자 검증
description: Python 포맷 문자열 문법으로 경로 파라미터를 선언하고 타입(int 등)으로 변환·검증하는 방법, 경로 작업 선언 순서, str+Enum으로 허용 값 제한, {file_path:path}로 경로를 포함하는 파라미터, Path()로 메타데이터와 gt/ge/lt/le 숫자 검증, 파라미터 순서와 * 트릭, FastAPI가 파라미터 종류를 판별하는 규칙을 설명한다.
tags: [path-parameters, validation, enum, path, numeric-validation, parameters]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-d6f8034b1114043ca3b6cde6
    resource: repo://docs_src/path_params_numeric_validations/tutorial002_py310.py
  - id: openwiki-source-11c3973cd0f96d9a4ea2a64a
    resource: repo://docs_src/path_params_numeric_validations/tutorial003_py310.py
  - id: openwiki-source-d5ea2075b94825343c04edc8
    resource: repo://docs_src/path_params_numeric_validations/tutorial005_an_py310.py
  - id: openwiki-source-0fd032858ed69844c1398749
    resource: repo://docs_src/path_params_numeric_validations/tutorial006_an_py310.py
  - id: openwiki-source-38df07681a8fcbdb034904e9
    resource: repo://docs_src/path_params/tutorial002_py310.py
  - id: openwiki-source-3b9406805096315081c49590
    resource: repo://docs_src/path_params/tutorial003_py310.py
  - id: openwiki-source-cd9fb2b4addace155974917d
    resource: repo://docs_src/path_params/tutorial003b_py310.py
  - id: openwiki-source-84c4dbdfc11b1dfd298b8383
    resource: repo://docs_src/path_params/tutorial004_py310.py
  - id: openwiki-source-e891265db7ef0a76fe70d4f4
    resource: repo://docs_src/path_params/tutorial005_py310.py
  - id: openwiki-source-6a09064320fc387f97ffc738
    resource: repo://docs/en/docs/tutorial/path-params.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 경로 파라미터와 숫자 검증

## 경로 파라미터 선언

Python 포맷 문자열과 같은 문법으로 경로 "파라미터"(변수)를 선언한다.

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}
```

경로의 `item_id` 값이 함수 인자 `item_id`로 전달된다. `/items/foo`에 접속하면 `{"item_id":"foo"}`를 받는다.

## 타입 선언과 변환

```Python
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

- 에디터 지원(오류 검사, 자동 완성)을 받는다.
- **데이터 변환**: `/items/3`이면 함수는 문자열 `"3"`이 아니라 Python `int` `3`을 받는다. HTTP 요청에서 온 문자열을 자동으로 파싱한다.
- **데이터 검증**: `/items/foo`나 `/items/4.2`이면 오류가 반환된다.

```JSON
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["path", "item_id"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "foo"
    }
  ]
}
```

오류는 검증에 실패한 정확한 위치(`loc`)를 알려 준다. 모든 검증은 Pydantic이 수행하며 `str`, `float`, `bool` 등 많은 타입을 같은 방식으로 쓸 수 있다. `/docs`(Swagger UI), `/redoc`(ReDoc)에 자동으로 문서화된다.

## 순서가 중요하다

경로 작업은 **선언 순서대로** 평가된다. `/users/me`(현재 사용자) 같은 고정 경로는 `/users/{user_id}`보다 **먼저** 선언해야 한다.

```Python
@app.get("/users/me")
async def read_user_me():
    return {"user_id": "the current user"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}
```

순서가 반대면 `/users/{user_id}`가 `/users/me`에도 일치해 `user_id="me"`로 처리된다. 같은 경로를 두 번 정의하면 항상 먼저 선언한 것이 사용된다.

```Python
@app.get("/users")
async def read_users():
    return ["Rick", "Morty"]


@app.get("/users")
async def read_users2():   # 절대 호출되지 않음
    return ["Bean", "Elfo"]
```

## 미리 정의된 값: Enum

허용 값을 미리 정하려면 `str`과 `Enum`을 상속한 클래스를 만든다. `str`을 상속하면 API 문서가 값의 타입이 `string`임을 알고 올바르게 렌더링한다.

```Python
from enum import Enum

from fastapi import FastAPI


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


app = FastAPI()


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}

    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}

    return {"model_name": model_name, "message": "Have some residuals"}
```

- 문서 UI에 가능한 값이 드롭다운으로 표시된다.
- 파라미터 값은 **열거형 멤버**다. `ModelName.alexnet`과 비교하거나 `model_name.value`(또는 `ModelName.lenet.value`)로 실제 문자열을 얻는다.
- 열거형 멤버를 반환하면(JSON 본문 안에 중첩되어도) 클라이언트로 보내기 전에 값(문자열)으로 변환된다.

## 경로를 포함하는 경로 파라미터

`/files/{file_path}`에서 `file_path`가 `home/johndoe/myfile.txt` 같은 경로 자체를 담아야 한다면, OpenAPI는 이를 공식 지원하지 않지만 Starlette의 경로 변환기 `:path`로 할 수 있다.

```Python
@app.get("/files/{file_path:path}")
async def read_file(file_path: str):
    return {"file_path": file_path}
```

`/files/home/johndoe/myfile.txt`이면 `file_path="home/johndoe/myfile.txt"`가 된다. 앞에 `/`가 포함된 `/home/johndoe/myfile.txt`가 필요하면 URL은 `/files//home/johndoe/myfile.txt`(이중 슬래시)가 된다. 문서는 일반 경로 파라미터처럼 표시된다.

## Path(): 메타데이터와 검증

쿼리 파라미터의 `Query`처럼, 경로 파라미터는 `Path`로 같은 종류의 검증과 메타데이터를 선언한다(`Annotated`는 FastAPI 0.95.0+ 지원, 0.95.1 이상 권장).

```Python
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI()


@app.get("/items/{item_id}")
async def read_items(
    item_id: Annotated[int, Path(title="The ID of the item to get")],
    q: Annotated[str | None, Query(alias="item-query")] = None,
):
    results = {"item_id": item_id}
    if q:
        results.update({"q": q})
    return results
```

`title`, `description`, `alias`, `deprecated`, `include_in_schema`, `examples`/`openapi_examples`, 문자열 검증(`min_length`, `max_length`, `pattern`) 등 `Query`와 같은 파라미터를 쓸 수 있다([쿼리 파라미터](./query-parameters.md)).

> 경로 파라미터는 경로의 일부이므로 **항상 필수**다. `Path()` 자체에는 기본값을 줄 수 없으며(`Path(default=...)`는 `AssertionError: Path parameters cannot have a default value`), `Annotated[..., Path()]`로 선언한 파라미터에 `= 값`을 주는 것도 `AssertionError`가 된다.

## 숫자 검증

`Query`, `Path`(그리고 이후의 다른 파라미터 함수)에 숫자 제약을 선언할 수 있다.

- `gt`: 초과(greater than)
- `ge`: 이상(greater than or equal)
- `lt`: 미만(less than)
- `le`: 이하(less than or equal)

```Python
@app.get("/items/{item_id}")
async def read_items(
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=1)], q: str
):
    ...


@app.get("/items/{item_id}")
async def read_items(
    item_id: Annotated[int, Path(title="The ID of the item to get", gt=0, le=1000)],
    q: str,
):
    ...
```

`float`에도 동작한다. `gt`를 쓰면 예를 들어 `0`보다 크지만 `1`보다 작은 값을 요구할 수 있다(`0.5`는 유효, `0.0`이나 `0`은 무효).

```Python
@app.get("/items/{item_id}")
async def read_items(
    *,
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)],
    q: str,
    size: Annotated[float, Query(gt=0, lt=10.5)],
):
    results = {"item_id": item_id}
    if q:
        results.update({"q": q})
    if size:
        results.update({"size": size})
    return results
```

## 파라미터 순서

FastAPI는 파라미터를 **이름, 타입, 기본값 선언(`Query`, `Path` 등)**으로 판별하며 **순서는 상관없다**. 다만 `Annotated` 없이 기본값 문법을 쓰면 Python은 기본값이 있는 인자 뒤에 기본값 없는 인자가 오는 것을 허용하지 않는다.

```Python
# 기본값 없는 q를 먼저 둔다
@app.get("/items/{item_id}")
async def read_items(q: str, item_id: int = Path(title="The ID of the item to get")):
    ...


# 또는 첫 파라미터로 *를 두어 이후 모든 인자를 키워드 인자로 만든다
@app.get("/items/{item_id}")
async def read_items(*, item_id: int = Path(title="The ID of the item to get"), q: str):
    ...
```

`Annotated`를 쓰면 함수 파라미터 기본값에 `Query()`/`Path()`를 쓰지 않으므로 이 문제가 없고 `*`도 대개 필요 없다.

## FastAPI의 파라미터 판별 규칙

명시적 `Path`/`Query`/`Header`/`Cookie`/`Body`/`Form`/`File`/`Depends`가 없으면 FastAPI는 다음 규칙으로 판별한다.

1. 이름이 경로(`{...}`)에 있으면 → **경로 파라미터**
2. 타입이 `UploadFile`(또는 그 리스트·Optional)이면 → **파일**
3. 타입이 단일 값이 아니면(Pydantic 모델 등) → **요청 본문**
4. 그 밖의 단일 타입(`int`, `str`, `float`, `bool` 등) → **쿼리 파라미터**

경로에 있는 이름에 `Path`가 아닌 다른 파라미터 함수를 쓰면 `AssertionError`가 발생한다. 본문 규칙은 [요청 본문](./request-body.md)을 참고한다.

## 기술적 세부

`Query`, `Path` 등은 공통 `Param` 클래스의 하위 클래스이며 같은 검증·메타데이터 파라미터를 공유한다. `fastapi`에서 임포트하는 `Query`, `Path`는 실제로는 **같은 이름의 클래스 인스턴스를 반환하는 함수**다(`fastapi.param_functions`). 에디터가 타입 오류를 표시하지 않게 하기 위해 함수로 제공된다.

## 관련 페이지

- [쿼리 파라미터](./query-parameters.md)
- [요청 본문](./request-body.md)
- [요청 처리 흐름](../internals/request-lifecycle.md) — 라우트 매칭 순서
