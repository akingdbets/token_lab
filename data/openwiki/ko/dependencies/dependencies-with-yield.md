---
type: guide
title: yield를 사용하는 의존성
description: return 대신 yield를 쓰는 의존성으로 DB 세션 같은 리소스를 만들고 정리하는 방법, try/except/finally와 예외 재발생 규칙, 하위 의존성 종료 순서, Depends(scope="function"|"request")로 종료 시점 제어, 컨텍스트 매니저 사용을 설명한다.
tags: [dependencies, yield, cleanup, context-manager, scope, exceptions]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-583740a237b9ab47e76d1c22
    resource: repo://docs_src/dependencies/tutorial007_py310.py
  - id: openwiki-source-240339e7b0151f923e2246b7
    resource: repo://docs_src/dependencies/tutorial008b_an_py310.py
  - id: openwiki-source-221404f7d01ae1c3a9c584b4
    resource: repo://docs_src/dependencies/tutorial008c_an_py310.py
  - id: openwiki-source-feee32007905d941c3802b8d
    resource: repo://docs_src/dependencies/tutorial008d_an_py310.py
  - id: openwiki-source-36f6cb15f05a73d08e616361
    resource: repo://docs_src/dependencies/tutorial008e_an_py310.py
  - id: openwiki-source-27a19fc781701e100cf69310
    resource: repo://docs/en/docs/tutorial/dependencies/dependencies-with-yield.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# yield를 사용하는 의존성

FastAPI 의존성은 **작업이 끝난 뒤 추가 단계(종료/정리 코드)**를 실행할 수 있다. `return` 대신 `yield`를 쓰고, 정리 코드를 `yield` 뒤에 작성한다.

- 의존성 하나당 `yield`는 **한 번만** 사용한다.
- `@contextlib.contextmanager` 또는 `@contextlib.asynccontextmanager`와 함께 쓸 수 있는 함수라면 FastAPI 의존성으로 쓸 수 있다. FastAPI가 내부적으로 이 두 데코레이터를 사용하므로 **직접 붙이지 않는다**.
- `async def`와 일반 `def` 모두 가능하다. 일반 `def` 제너레이터는 스레드풀에서 실행된다.

## DB 세션 의존성

```Python
async def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()
```

- `yield`까지의 코드: 응답을 만들기 **전에** 실행
- `yield`한 값(`db`): 경로 작업과 다른 의존성에 주입되는 값
- `yield` 이후 코드: 기본적으로 응답을 보낸 **후**에 실행

실제 SQLModel 예제는 [SQL 데이터베이스](../integrations/sql-databases.md)를 참고한다.

## try와 함께 쓰기

`try` 블록 안에서 `yield`하면, 의존성을 사용하는 동안(다른 의존성이나 경로 작업 함수에서) 발생한 예외를 의존성에서 받는다. 예를 들어 트랜잭션 롤백을 일으킨 예외를 `except SomeException`으로 잡을 수 있다. `finally`를 쓰면 예외 여부와 관계없이 정리 코드가 실행된다.

## 하위 의존성과 yield

의존성 트리의 어느 의존성이든 `yield`를 쓸 수 있으며, FastAPI가 종료 코드를 **올바른 순서**(의존하는 쪽이 먼저 종료, 의존되는 쪽이 나중에 종료)로 실행한다.

```Python
from typing import Annotated

from fastapi import Depends


async def dependency_a():
    dep_a = generate_dep_a()
    try:
        yield dep_a
    finally:
        dep_a.close()


async def dependency_b(dep_a: Annotated[DepA, Depends(dependency_a)]):
    dep_b = generate_dep_b()
    try:
        yield dep_b
    finally:
        dep_b.close(dep_a)


async def dependency_c(dep_b: Annotated[DepB, Depends(dependency_b)]):
    dep_c = generate_dep_c()
    try:
        yield dep_c
    finally:
        dep_c.close(dep_b)
```

`dependency_c`의 종료 코드는 `dep_b`가, `dependency_b`의 종료 코드는 `dep_a`가 아직 유효해야 하므로 c → b → a 순서로 종료된다. 내부적으로 각 yield 의존성은 `AsyncExitStack`에 컨텍스트 매니저로 등록되어 역순으로 정리된다. `return` 의존성과 섞어 써도 된다.

## yield 의존성과 HTTPException

`except`로 잡은 예외를 다른 예외(예: `HTTPException`)로 바꿔 발생시킬 수 있다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

app = FastAPI()

data = {
    "plumbus": {"description": "Freshly pickled plumbus", "owner": "Morty"},
    "portal-gun": {"description": "Gun to create portals", "owner": "Rick"},
}


class OwnerError(Exception):
    pass


def get_username():
    try:
        yield "Rick"
    except OwnerError as e:
        raise HTTPException(status_code=400, detail=f"Owner error: {e}")


@app.get("/items/{item_id}")
def get_item(item_id: str, username: Annotated[str, Depends(get_username)]):
    if item_id not in data:
        raise HTTPException(status_code=404, detail="Item not found")
    item = data[item_id]
    if item["owner"] != username:
        raise OwnerError(username)
    return item
```

대부분은 경로 작업 함수에서 직접 `HTTPException`을 발생시키면 충분하다. 예외를 잡아 사용자 정의 응답을 만들고 싶다면 [사용자 정의 예외 핸들러](../errors/handling-errors.md)를 쓴다.

## except 후에는 반드시 raise

`except`로 예외를 잡고 다시 발생시키지 않으면(또는 새 예외를 발생시키지 않으면), 일반 Python처럼 FastAPI는 예외가 있었다는 것을 알 수 없다.

```Python
def get_username():
    try:
        yield "Rick"
    except InternalError:
        print("Oops, we didn't raise again, Britney 😱")
```

이 경우 클라이언트는 *500 Internal Server Error*를 받지만 서버에는 **아무 로그도 남지 않는다**. `HTTPException` 등으로 바꾸지 않는 한, 원래 예외를 `raise`로 다시 발생시켜야 한다.

```Python
def get_username():
    try:
        yield "Rick"
    except InternalError:
        print("We don't swallow the internal error here, we raise again 😎")
        raise
```

이제 클라이언트는 같은 500 응답을 받고 서버 로그에는 `InternalError`가 남는다.

경로 작업 함수에서 발생한 예외는 `HTTPException`을 포함해 모두 yield 의존성으로 전달된다. 클라이언트에는 **응답이 하나만** 전송된다(오류 응답이거나 경로 작업의 응답).

## 조기 종료와 scope

기본적으로 yield 의존성의 종료 코드는 **응답을 보낸 후** 실행된다. 경로 작업 함수가 반환된 뒤에는 의존성이 필요 없다면 `Depends(scope="function")`으로 **응답을 보내기 전에** 종료할 수 있다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


def get_username():
    try:
        yield "Rick"
    finally:
        print("Cleanup up before response is sent")


@app.get("/users/me")
def get_user_me(username: Annotated[str, Depends(get_username, scope="function")]):
    return username
```

| `scope` | 시작 | 종료 |
| --- | --- | --- |
| `"function"` | 경로 작업 함수 전 | 경로 작업 함수 종료 후, **응답 전송 전** |
| `"request"` (yield 의존성의 기본값) | 경로 작업 함수 전 | **응답 전송 후** |

### 하위 의존성의 scope 규칙

- `scope="request"` 의존성은 `scope="function"` 의존성에 의존할 수 **없다**. 위반하면 의존성 그래프를 만들 때 `DependencyScopeError`("The dependency "…" has a scope of "request", it cannot depend on dependencies with scope "function".")가 발생한다.
- `scope="function"` 의존성은 `"function"`, `"request"` 의존성 모두에 의존할 수 있다.

어떤 의존성이든 종료 코드에서 하위 의존성을 사용할 수 있어야 하므로, 하위 의존성이 더 늦게(또는 같이) 종료되어야 하기 때문이다. 내부적으로 요청 범위와 함수 범위에 각각 별도의 `AsyncExitStack`(`fastapi_inner_astack`, `fastapi_function_astack`)이 사용된다.

버전별 동작 변화(0.106.0, 0.110.0, 0.118.0, 0.121.0)는 [고급 의존성](./advanced-dependencies.md)에 정리되어 있다.

## 컨텍스트 매니저 사용

`with`문에 쓸 수 있는 객체가 컨텍스트 매니저다(`open()`이 대표적). yield 의존성을 만들면 FastAPI가 내부적으로 컨텍스트 매니저를 만든다. 의존성 함수 안에서 `with`/`async with`로 다른 컨텍스트 매니저를 사용할 수도 있다.

```Python
class MySuperContextManager:
    def __init__(self):
        self.db = DBSession()

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.close()


async def get_db():
    with MySuperContextManager() as db:
        yield db
```

## 관련 페이지

- [의존성 주입 기초](./dependency-injection-basics.md)
- [고급 의존성](./advanced-dependencies.md) — StreamingResponse, 백그라운드 작업과의 상호작용
- [수명 주기 이벤트](../app-structure/lifespan-events.md) — 앱 전체 리소스는 lifespan으로
- [오류 처리](../errors/handling-errors.md)
