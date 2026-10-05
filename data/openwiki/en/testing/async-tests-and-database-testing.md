---
type: guide
title: Async Tests and Testing Databases
description: Write async test functions with @pytest.mark.anyio and httpx.AsyncClient over ASGITransport, handle lifespan and event-loop pitfalls, and test database-backed apps by overriding the session dependency with a test database.
tags: [testing, async, anyio, pytest, httpx, asyncclient, asgitransport, database-testing, sqlmodel]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-7285f60e33fbaa50c895cd70
    resource: repo://docs_src/async_tests/app_a_py310/test_main.py
  - id: openwiki-source-ce488c1d921d5f2531ab24a4
    resource: repo://docs_src/sql_databases/tutorial002_an_py310.py
  - id: openwiki-source-e808f38e6d533f565983e57b
    resource: repo://docs/en/docs/advanced/async-tests.md
  - id: openwiki-source-aa3b69a785ca0c971dbe3a47
    resource: repo://docs/en/docs/how-to/testing-database.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Async Tests and Testing Databases

## When you need async tests

`TestClient` ([Testing Basics](testing-basics.md)) lets you test even `async def` endpoints from normal `def` test functions — it runs the app for you. But if your **test itself** needs to `await` something (e.g. query an async database driver to check results), the test function must be `async`, and then you can't use the synchronous `TestClient` inside it. Use `httpx.AsyncClient` instead.

## Example

`docs_src/async_tests/app_a_py310/main.py`:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Tomato"}
```

`docs_src/async_tests/app_a_py310/test_main.py`:

```python
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

- `@pytest.mark.anyio` tells pytest to run the test function asynchronously. It comes from the **AnyIO** pytest plugin (AnyIO is installed with Starlette/FastAPI), so you don't need `pytest-asyncio`.
- `ASGITransport(app=app)` sends requests straight to your ASGI app in-process — no server or network.
- `base_url` is required for relative URLs; any value works (`"http://test"`).
- Use `await ac.get(...)`, `await ac.post(...)`, etc. — the same API as `TestClient` (both are HTTPX-based).

Run with `pytest` as usual.

## Pitfalls

- **Lifespan events don't run** with `AsyncClient` + `ASGITransport`. If your app relies on `lifespan`/startup, wrap the app with `LifespanManager` from the `asgi-lifespan` package:

  ```python
  from asgi_lifespan import LifespanManager

  async with LifespanManager(app) as manager:
      async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as ac:
          ...
  ```

  (With `TestClient`, use `with TestClient(app) as client:` instead — see [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md).)
- **`RuntimeError: Task attached to a different loop`** (e.g. with MongoDB's `MotorClient`): create objects that bind to an event loop *inside* async code — e.g. in a lifespan or startup handler — not at import time.
- You can call other `async` functions in the test (e.g. check the database) after the request, since the test itself is async.

## Testing with a database

The recommended approach (detailed in the SQLModel tutorial's "testing" section) is to point the app at a **separate test database** by overriding the session dependency:

```python
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
    response = client.post("/heroes/", json={"name": "Deadpond", "secret_name": "Dive Wilson"})
    assert response.status_code == 200
    assert response.json()["name"] == "Deadpond"
```

Key ideas:

- `get_session` is the `yield` dependency from [SQL Databases with SQLModel](../integrations/sql-databases.md); `app.dependency_overrides` swaps it for a test session.
- An in-memory SQLite database (`"sqlite://"`) with `StaticPool` gives each test a fresh, fast database shared across threads.
- Pytest fixtures create the tables, provide the session and client, and clear overrides afterwards so tests stay isolated.
- The `session` fixture also lets tests insert data directly or verify what endpoints wrote.

## Related

- [Testing with TestClient](testing-basics.md)
- [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md)
- [Settings](../app-structure/settings.md) — overriding configuration in tests
