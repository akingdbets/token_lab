---
type: "참조"
title: "의존성 주입 기초: Depends, 클래스, 하위 의존성"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-c8b50bb3c41c99eb10fe50d3
    resource: repo://docs_src/dependencies/tutorial001_02_an_py310.py
  - id: openwiki-source-f0b3cb498212542abd30c8cb
    resource: repo://docs_src/dependencies/tutorial001_an_py310.py
  - id: openwiki-source-cace6ad64745ec6136e807f0
    resource: repo://docs_src/dependencies/tutorial002_an_py310.py
  - id: openwiki-source-8df6874799b824643b98ad12
    resource: repo://docs_src/dependencies/tutorial004_an_py310.py
  - id: openwiki-source-5d0e4caa34767227e51c78f0
    resource: repo://docs_src/dependencies/tutorial005_an_py310.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-4ba318fa02e49c0255b400c4
    resource: repo://fastapi/param_functions.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 의존성 주입 기초: Depends, 클래스, 하위 의존성

**의존성 주입(Dependency Injection)**은 경로 작업 함수가 동작에 필요한 것(의존성)을 선언하면, FastAPI가 그것을 실행해 결과를 "주입"해 주는 방식이다. 다음에 유용하다.

- 공통 로직 공유(같은 코드 반복 제거)
- 데이터베이스 연결 공유
- 보안·인증·권한(역할) 요구사항 적용
- 그 밖의 다양한 통합 — 별도 "플러그인" 시스템 없이 의존성만으로 구현

## 첫 번째 의존성

의존성은 경로 작업 함수가 받을 수 있는 모든 파라미터를 받을 수 있는 **함수**일 뿐이다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return commons


@app.get("/users/")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return commons
```

- `Depends()`에는 **호출 가능한 객체 하나**를 넘긴다. 괄호를 붙여 직접 호출하지 않는다(`Depends(common_parameters)`, `Depends(common_parameters())` 아님).
- 요청이 오면 FastAPI는 의존성을 올바른 파라미터로 호출하고, 그 결과를 경로 작업 함수의 파라미터에 할당한다.
- `Annotated`는 FastAPI 0.95.0에서 지원되기 시작해 권장 방식이 되었다. 이전 버전이면 0.95.1 이상으로 업그레이드한다.

## Annotated 의존성 공유

`Annotated` 값을 변수(타입 별칭)에 저장해 여러 곳에서 재사용할 수 있다. 타입 정보가 유지되므로 에디터 자동 완성도 동작한다.

```Python
CommonsDep = Annotated[dict, Depends(common_parameters)]


@app.get("/items/")
async def read_items(commons: CommonsDep):
    return commons


@app.get("/users/")
async def read_users(commons: CommonsDep):
    return commons
```

## async 여부

의존성도 FastAPI가 호출하므로 경로 작업 함수와 같은 규칙이 적용된다. `async def`와 일반 `def` 모두 가능하고 섞어 쓸 수 있다. 일반 `def` 의존성은 이벤트 루프를 막지 않도록 스레드풀(`run_in_threadpool`)에서 실행된다([async/await](../getting-started/python-types-and-async.md)).

## OpenAPI 통합

의존성(및 하위 의존성)이 선언한 요청 파라미터·검증·요구사항은 모두 같은 OpenAPI 스키마에 통합되어, 대화형 문서에 경로 작업의 파라미터로 표시된다.

## 클래스를 의존성으로

의존성은 "호출 가능(callable)"하기만 하면 된다. Python 클래스도 `CommonQueryParams(...)`처럼 호출할 수 있으므로 의존성이 될 수 있다. FastAPI는 `__init__`의 파라미터를 분석한다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


class CommonQueryParams:
    def __init__(self, q: str | None = None, skip: int = 0, limit: int = 100):
        self.q = q
        self.skip = skip
        self.limit = limit


@app.get("/items/")
async def read_items(commons: Annotated[CommonQueryParams, Depends(CommonQueryParams)]):
    response = {}
    if commons.q:
        response.update({"q": commons.q})
    items = fake_items_db[commons.skip : commons.skip + commons.limit]
    response.update({"items": items})
    return response
```

딕셔너리 대신 클래스 인스턴스를 받으므로 에디터가 `commons.q`, `commons.skip`을 자동 완성한다.

### 타입과 Depends의 역할

`Annotated[CommonQueryParams, Depends(CommonQueryParams)]`에서 실제로 FastAPI가 의존성을 판단하는 것은 `Depends(CommonQueryParams)`이다. 첫 번째 `CommonQueryParams`는 에디터용 타입 정보일 뿐이므로 `Annotated[Any, Depends(CommonQueryParams)]`라고 써도 동작한다(다만 타입 정보가 사라진다).

### 축약: Depends()

의존성이 **클래스**이고 타입과 같다면 `Depends()`를 인자 없이 쓸 수 있다. FastAPI가 타입 주석의 클래스를 의존성으로 사용한다.

```Python
@app.get("/items/")
async def read_items(commons: Annotated[CommonQueryParams, Depends()]):
    ...
```

## 하위 의존성

의존성이 다시 의존성을 가질 수 있으며, 깊이에 제한이 없다. FastAPI가 트리를 모두 해석한다.

```Python
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI

app = FastAPI()


def query_extractor(q: str | None = None):
    return q


def query_or_cookie_extractor(
    q: Annotated[str, Depends(query_extractor)],
    last_query: Annotated[str | None, Cookie()] = None,
):
    if not q:
        return last_query
    return q


@app.get("/items/")
async def read_query(
    query_or_default: Annotated[str, Depends(query_or_cookie_extractor)],
):
    return {"q_or_cookie": query_or_default}
```

- `query_or_cookie_extractor`는 의존성이면서 동시에 `query_extractor`에 의존한다.
- 쿼리 `q`가 없으면 쿠키 `last_query`를 사용한다.
- 경로 작업 함수는 `query_or_cookie_extractor`만 선언하면 된다.

### 같은 의존성을 여러 번 쓸 때: 캐시

하나의 요청에서 같은 의존성이 여러 의존성에 선언되어 있으면, FastAPI는 **요청당 한 번만 호출**하고 반환값을 캐시해 필요한 모든 곳에 전달한다. 같은 요청 안에서 매번 새로 호출해야 한다면 `use_cache=False`를 지정한다.

```Python
async def needy_dependency(fresh_value: Annotated[str, Depends(get_value, use_cache=False)]):
    return {"fresh_value": fresh_value}
```

캐시 키는 의존성 호출 대상과 (보안 의존성의 경우) OAuth2 스코프 등을 기준으로 계산된다([OAuth2 스코프](../security/oauth2-scopes.md)).

## 의존성으로 할 수 있는 다른 것들

- 반환값 없이 실행만 하는 의존성: [데코레이터·전역 의존성](./decorator-and-global-dependencies.md)
- 리소스 생성·정리: [yield를 사용하는 의존성](./dependencies-with-yield.md)
- 설정값을 받는 의존성: [고급 의존성](./advanced-dependencies.md)
- 인증: [보안 기초](../security/oauth2-password-flow.md)
- 테스트에서 교체: [테스트 기초](../testing/testing-basics.md)의 `app.dependency_overrides`
- 내부 해석 흐름: [요청 처리 흐름](../internals/request-lifecycle.md)
