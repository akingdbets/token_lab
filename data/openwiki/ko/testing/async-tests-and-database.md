---
type: guide
title: 비동기 테스트와 데이터베이스 테스트
description: pytest.mark.anyio와 httpx.AsyncClient(ASGITransport)로 async def 테스트에서 FastAPI 앱을 호출하는 방법, AsyncClient가 lifespan을 실행하지 않는 문제와 asgi-lifespan, 다른 이벤트 루프 오류 대처, 그리고 세션 의존성을 dependency_overrides로 교체해 테스트용 데이터베이스(SQLModel/SQLite)로 테스트하는 방법을 설명한다.
tags: [testing, async-tests, anyio, httpx, asyncclient, database-testing]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-7285f60e33fbaa50c895cd70
    resource: repo://docs_src/async_tests/app_a_py310/test_main.py
  - id: openwiki-source-e808f38e6d533f565983e57b
    resource: repo://docs/en/docs/advanced/async-tests.md
  - id: openwiki-source-aa3b69a785ca0c971dbe3a47
    resource: repo://docs/en/docs/how-to/testing-database.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 비동기 테스트와 데이터베이스 테스트

## 비동기 테스트

지금까지는 `TestClient`로 일반 `def` 테스트 함수를 작성했다([테스트 기초](./testing-basics.md)). 테스트에서 **비동기 함수**를 호출해야 할 때가 있다. 예: 앱에 요청을 보낸 뒤, 비동기 DB 라이브러리로 데이터가 제대로 저장됐는지 확인하는 경우.

### pytest.mark.anyio

테스트에서 async 함수를 호출하려면 테스트 함수 자체가 async여야 한다. AnyIO가 제공하는 pytest 플러그인으로 특정 테스트 함수를 비동기로 실행하도록 표시할 수 있다(`@pytest.mark.anyio`). AnyIO는 FastAPI(Starlette)가 의존하는 라이브러리라 함께 설치되어 있다.

### HTTPX AsyncClient

FastAPI 앱은 일반 `def` 함수를 써도 내부적으로는 async 앱이다. `TestClient`는 일반 `def` 테스트에서 async 앱을 호출하기 위한 내부 처리를 하지만, **async 테스트 함수 안에서는 그 처리가 동작하지 않는다**. 테스트를 비동기로 실행하면 `TestClient`를 쓸 수 없다. `TestClient`는 [HTTPX](https://www.python-httpx.org) 기반이므로, HTTPX를 직접 쓴다.

```
.
├── app
│   ├── __init__.py
│   ├── main.py
│   └── test_main.py
```

```Python
# app/main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Tomato"}
```

```Python
# app/test_main.py
import pytest
from httpx import ASGITransport, AsyncClient

from .main import app


@pytest.mark.anyio
async def test_root():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Tomato"}
```

```console
$ uv run pytest
```

- 테스트 함수가 `def`가 아니라 `async def`다.
- `ASGITransport(app=app)`로 네트워크 없이 ASGI 앱을 직접 호출하는 `AsyncClient`를 만들고, `await ac.get("/")`처럼 요청을 `await`한다. `TestClient`의 `response = client.get('/')`와 같은 역할이다.
- `base_url`은 상대 경로 요청에 쓰일 임의의 기본 URL이다.

> 앱이 [lifespan 이벤트](../app-structure/lifespan-events.md)에 의존한다면 `AsyncClient`는 이를 **실행하지 않는다**. 실행하려면 [florimondmanca/asgi-lifespan](https://github.com/florimondmanca/asgi-lifespan#usage)의 `LifespanManager`를 쓴다.

### 다른 비동기 함수 호출

테스트 함수가 비동기이므로 앱에 요청을 보내는 것 외에도 다른 `async` 함수를 코드의 다른 곳에서처럼 호출(`await`)할 수 있다.

테스트에 비동기 함수 호출을 넣었을 때(예: MongoDB의 MotorClient 사용 시) `RuntimeError: Task attached to a different loop`가 발생하면, 이벤트 루프가 필요한 객체를 async 함수 **안에서** 인스턴스화해야 한다. 예를 들어 `@app.on_event("startup")` 콜백(또는 lifespan) 안에서 만든다.

## 데이터베이스 테스트

FastAPI 문서는 DB 테스트에 대해 SQLModel 문서를 안내한다.

- [SQLModel 문서](https://sqlmodel.tiangolo.com/): 데이터베이스, SQL, SQLModel 학습
- [SQLModel + FastAPI 미니 튜토리얼](https://sqlmodel.tiangolo.com/tutorial/fastapi/)
- [SQL 데이터베이스 테스트 섹션](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/)

### 일반적인 패턴: 세션 의존성 교체

[SQL 데이터베이스](../integrations/sql-databases.md) 페이지처럼 세션을 yield 의존성(`get_session`)으로 제공했다면, 테스트에서는 `app.dependency_overrides`로 **테스트용 DB 세션**을 주입한다. 아래는 SQLModel 문서가 소개하는 방식과 같은 흐름의 예시다(메모리 SQLite + `StaticPool`로 여러 스레드가 같은 메모리 DB를 공유).

```Python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from .main import app, get_session


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_create_hero(client: TestClient):
    response = client.post(
        "/heroes/", json={"name": "Deadpond", "secret_name": "Dive Wilson"}
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Deadpond"
    assert data["id"] is not None
```

핵심:

- 운영 DB 대신 테스트마다 새로 만드는 격리된 DB를 쓴다.
- 의존성 오버라이드는 테스트가 끝나면 `app.dependency_overrides.clear()`(또는 `= {}`)로 되돌린다.
- 앱이 시작 이벤트에서 테이블을 만든다면 `TestClient`를 `with` 문 없이 쓰면 시작 이벤트가 실행되지 않으므로, 픽스처에서 직접 `create_all()`을 호출한다([테스트 기초](./testing-basics.md)).

## 관련 페이지

- [테스트 기초](./testing-basics.md) — `TestClient`, `dependency_overrides`, lifespan·WebSocket 테스트
- [SQL 데이터베이스](../integrations/sql-databases.md)
- [설정](../app-structure/settings.md) — 테스트용 설정 오버라이드
