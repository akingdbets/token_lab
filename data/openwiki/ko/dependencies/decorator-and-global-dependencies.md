---
type: guide
title: 데코레이터 의존성과 전역 의존성
description: 반환값이 필요 없는 의존성을 경로 작업 데코레이터의 dependencies=[Depends(...)]로 실행하는 방법, APIRouter·include_router·FastAPI(dependencies=...)로 경로 작업 그룹과 앱 전체에 의존성을 적용하는 방법, 실행 순서를 설명한다.
tags: [dependencies, path-operation-decorator, global-dependencies, apirouter]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-b0a86b25e563ca5939eb329b
    resource: repo://docs_src/dependencies/tutorial006_an_py310.py
  - id: openwiki-source-014453cf0a86d7a4a56e6da5
    resource: repo://docs_src/dependencies/tutorial012_an_py310.py
  - id: openwiki-source-ffe84a85602c83d29ec1965b
    resource: repo://docs/en/docs/tutorial/bigger-applications.md
  - id: openwiki-source-6d0f0988bc9119ce91077111
    resource: repo://docs/en/docs/tutorial/dependencies/dependencies-in-path-operation-decorators.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 데코레이터 의존성과 전역 의존성

어떤 의존성은 **실행만 되면 되고** 반환값은 경로 작업 함수에서 쓸 필요가 없다(예: 헤더 토큰 검증). 이럴 때 함수 파라미터 대신 데코레이터에 `dependencies` 리스트를 넘긴다.

## 경로 작업 데코레이터에 dependencies 추가

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()


async def verify_token(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def verify_key(x_key: Annotated[str, Header()]):
    if x_key != "fake-super-secret-key":
        raise HTTPException(status_code=400, detail="X-Key header invalid")
    return x_key


@app.get("/items/", dependencies=[Depends(verify_token), Depends(verify_key)])
async def read_items():
    return [{"item": "Foo"}, {"item": "Bar"}]
```

- `dependencies`는 `Depends()`의 **리스트**다.
- 일반 의존성과 똑같이 실행·해석되지만, 반환값은 경로 작업 함수에 **전달되지 않는다**.
- 사용하지 않는 파라미터를 경고하는 에디터 문제를 피하고, 새 개발자가 "쓰이지 않는 파라미터"로 오해해 지우는 것을 막는다.
- 예제의 `X-Key`, `X-Token`은 임의로 만든 헤더다. 실제 보안은 [보안 기초](../security/oauth2-password-flow.md)의 도구를 쓴다.

### 데코레이터 의존성이 할 수 있는 것

일반 의존성 함수를 그대로 재사용한다.

- **요청 요구사항 선언**: 헤더(`Header()`), 쿼리 등 파라미터와 하위 의존성. 이 요구사항은 OpenAPI 문서에도 반영되고 검증된다(헤더가 없으면 422).
- **예외 발생**: `HTTPException`을 `raise`하면 경로 작업 함수가 실행되지 않고 오류 응답이 반환된다.
- **값 반환**: 반환해도 되지만 사용되지 않는다. 다른 곳에서 값을 반환하는 용도로 쓰는 의존성(`verify_key`)도 그대로 재사용할 수 있다.

## 경로 작업 그룹: APIRouter

같은 의존성을 여러 경로 작업에 적용하려면 `APIRouter(dependencies=[...])` 또는 `app.include_router(router, dependencies=[...])`를 쓴다. 자세한 예제는 [큰 애플리케이션](../app-structure/bigger-applications.md)에 있다.

## 전역 의존성

앱 전체에 적용하려면 `FastAPI(dependencies=[...])`를 쓴다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException


async def verify_token(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def verify_key(x_key: Annotated[str, Header()]):
    if x_key != "fake-super-secret-key":
        raise HTTPException(status_code=400, detail="X-Key header invalid")
    return x_key


app = FastAPI(dependencies=[Depends(verify_token), Depends(verify_key)])


@app.get("/items/")
async def read_items():
    return [{"item": "Portal Gun"}, {"item": "Plumbus"}]


@app.get("/users/")
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]
```

데코레이터 의존성에 대한 모든 내용이 앱의 모든 경로 작업에 적용된다.

## 실행 순서

여러 수준에 의존성이 있으면 바깥 수준부터 실행된다.

1. 앱(`FastAPI(dependencies=...)`)과 라우터(`APIRouter`/`include_router`)의 의존성
2. 경로 작업 데코레이터의 `dependencies`
3. 경로 작업 함수 파라미터의 일반 의존성

같은 의존성이 여러 곳에서 쓰이면 기본적으로 요청당 한 번만 실행되고 결과가 캐시된다(`use_cache`, [의존성 주입 기초](./dependency-injection-basics.md) 참고).

## yield 의존성과 함께

데코레이터·전역 의존성도 `yield`를 쓸 수 있다. 예를 들어 요청마다 트랜잭션을 열고 닫는 전역 의존성을 만들 수 있다([yield를 사용하는 의존성](./dependencies-with-yield.md)).

## 관련 페이지

- [의존성 주입 기초](./dependency-injection-basics.md)
- [큰 애플리케이션](../app-structure/bigger-applications.md)
- [테스트: 의존성 오버라이드](../testing/testing-basics.md) — 전역 의존성도 `app.dependency_overrides`로 교체 가능
