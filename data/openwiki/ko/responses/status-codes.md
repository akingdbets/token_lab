---
type: "참조"
title: "상태 코드: 기본·추가·동적 변경"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-64f65a49d9b0624f36e8c4da
    resource: repo://docs_src/additional_status_codes/tutorial001_an_py310.py
  - id: openwiki-source-f95dc6f662f6c7f6ffe6230f
    resource: repo://docs_src/response_change_status_code/tutorial001_py310.py
  - id: openwiki-source-96588f86415f73ebac05921c
    resource: repo://docs_src/response_status_code/tutorial001_py310.py
  - id: openwiki-source-253ff8d6337ec5a30ecba880
    resource: repo://docs_src/response_status_code/tutorial002_py310.py
  - id: openwiki-source-0266708b69f2d248a7bf8dd4
    resource: repo://docs/en/docs/advanced/additional-status-codes.md
  - id: openwiki-source-6465d6b8269aa4382332c841
    resource: repo://docs/en/docs/tutorial/response-status-code.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 상태 코드: 기본·추가·동적 변경

## 기본 응답 상태 코드: status_code

응답 모델처럼, 경로 작업 데코레이터(`@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()` 등)의 `status_code` 파라미터로 응답 HTTP 상태 코드를 선언한다. 함수 파라미터가 아니라 **데코레이터**의 파라미터다.

```Python
from fastapi import FastAPI

app = FastAPI()


@app.post("/items/", status_code=201)
async def create_item(name: str):
    return {"name": name}
```

- 정수 HTTP 상태 코드를 받는다. Python의 [`http.HTTPStatus`](https://docs.python.org/3/library/http.html#http.HTTPStatus) 같은 `IntEnum`도 받으며, 내부에서 정수로 정규화된다.
- 응답에 그 상태 코드를 사용하고, OpenAPI 스키마(따라서 문서 UI)에 문서화한다.
- 본문이 없어야 하는 상태 코드면 FastAPI가 OpenAPI 문서에 응답 본문이 없다고 표시하고, 실제 응답 본문도 비운다.

### HTTP 상태 코드 요약

| 범위 | 의미 |
| --- | --- |
| `100`–`199` | 정보. 직접 쓸 일이 드물며 **본문을 가질 수 없다** |
| **`200`–`299`** | 성공. 가장 많이 쓴다. `200` OK(기본값), `201` Created(DB에 새 레코드 생성 후), `204` No Content(**본문이 없어야 함**) |
| **`300`–`399`** | 리다이렉션. 본문이 있을 수도 없을 수도 있지만 `304` Not Modified는 **본문이 없어야 함** |
| **`400`–`499`** | 클라이언트 오류. 두 번째로 많이 쓴다. `404` Not Found, 일반 오류는 `400` |
| `500`–`599` | 서버 오류. 직접 쓰는 일은 거의 없다. 앱 코드나 서버에 문제가 있으면 자동으로 반환된다 |

자세한 내용은 [MDN HTTP 상태 코드 문서](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)를 참고한다.

### 이름으로 기억하기: fastapi.status

```Python
from fastapi import FastAPI, status

app = FastAPI()


@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(name: str):
    return {"name": name}
```

`fastapi.status`(= `starlette.status`)의 상수는 단순한 정수지만 에디터 자동 완성으로 찾기 쉽다.

## 추가 상태 코드

기본적으로 FastAPI는 `JSONResponse`(또는 응답 모델 직렬화 결과)에 경로 작업의 상태 코드를 넣어 반환한다. 기본 상태 코드 외에 **다른 상태 코드**도 반환해야 한다면 `Response`(예: `JSONResponse`)를 **직접 반환**한다.

예: 항목을 수정하면 `200`, 존재하지 않아 새로 만들면 `201 Created`.

```Python
from typing import Annotated

from fastapi import Body, FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()

items = {"foo": {"name": "Fighters", "size": 6}, "bar": {"name": "Tenders", "size": 3}}


@app.put("/items/{item_id}")
async def upsert_item(
    item_id: str,
    name: Annotated[str | None, Body()] = None,
    size: Annotated[int | None, Body()] = None,
):
    if item_id in items:
        item = items[item_id]
        item["name"] = name
        item["size"] = size
        return item
    else:
        item = {"name": name, "size": size}
        items[item_id] = item
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=item)
```

> `Response`를 직접 반환하면 그대로 반환된다. 모델로 직렬화되지 않으므로 원하는 데이터만 담겼는지, 값이 JSON으로 직렬화 가능한지 직접 확인해야 한다([응답 직접 반환](./custom-responses.md)).

직접 반환한 추가 상태 코드는 FastAPI가 무엇을 반환할지 미리 알 수 없으므로 OpenAPI에 포함되지 않는다. [추가 응답(`responses`)](./additional-responses.md)으로 문서화할 수 있다.

## 상태 코드 동적 변경: Response 파라미터

기본 상태 코드를 두되 상황에 따라 바꾸면서도, 반환 데이터는 응답 모델로 필터링하고 싶을 때가 있다. 예: 기본은 `200 OK`, 데이터가 없어서 새로 만들면 `201 Created`.

```Python
from fastapi import FastAPI, Response, status

app = FastAPI()

tasks = {"foo": "Listen to the Bar Fighters"}


@app.put("/get-or-create-task/{task_id}", status_code=200)
def get_or_create_task(task_id: str, response: Response):
    if task_id not in tasks:
        tasks[task_id] = "This didn't exist before"
        response.status_code = status.HTTP_201_CREATED
    return tasks[task_id]
```

- 경로 작업 함수에 `Response` 타입 파라미터를 선언하고, 그 **임시** 응답 객체에 `status_code`를 설정한다.
- 평소처럼 원하는 객체(`dict`, DB 모델 등)를 반환하면, `response_model`이 있다면 여전히 필터링·변환된다.
- FastAPI는 임시 응답에서 상태 코드(그리고 쿠키·헤더)를 추출해 최종 응답에 넣는다. `Response` 파라미터에 설정한 상태 코드는 데코레이터의 `status_code`보다 **우선**한다.
- `Response` 파라미터는 **의존성**에서도 선언해 상태 코드를 설정할 수 있다. 단, 마지막에 설정한 값이 이긴다.

헤더와 쿠키도 같은 방식으로 설정한다([응답 헤더와 쿠키](./response-headers-and-cookies.md)).

## 오류 상태 코드

4xx 오류를 반환할 때는 보통 `HTTPException`을 발생시킨다([오류 처리](../errors/handling-errors.md)). 요청 검증 실패는 기본적으로 `422`, 응답 모델 검증 실패는 `500`이 된다.

## 관련 페이지

- [응답 모델](./response-model.md)
- [추가 응답](./additional-responses.md)
- [경로 작업 설정](../app-structure/path-operation-configuration.md)
- [요청 처리 흐름](../internals/request-lifecycle.md) — 상태 코드 결정 순서
