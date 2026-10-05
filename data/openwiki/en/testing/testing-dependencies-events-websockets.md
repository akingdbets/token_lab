---
type: guide
title: Testing Dependencies, Lifespan Events and WebSockets
description: Replace dependencies in tests with app.dependency_overrides, run lifespan and startup/shutdown code by using TestClient as a context manager, and test WebSocket endpoints with client.websocket_connect().
tags: [testing, dependency_overrides, lifespan, testclient, websockets, websocket_connect, pytest]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-59c9fd26e11b511bdb9a623d
    resource: repo://docs_src/app_testing/tutorial002_py310.py
  - id: openwiki-source-531954ed16fc7efe7e13db77
    resource: repo://docs_src/app_testing/tutorial003_py310.py
  - id: openwiki-source-1173922cb177b14322341b79
    resource: repo://docs_src/app_testing/tutorial004_py310.py
  - id: openwiki-source-bb553b0c924c015f7ad96484
    resource: repo://docs_src/dependency_testing/tutorial001_an_py310.py
  - id: openwiki-source-68e5278b7080f202ff12a79e
    resource: repo://docs/en/docs/advanced/testing-dependencies.md
  - id: openwiki-source-eeb2deecd0db3b76511145e7
    resource: repo://docs/en/docs/advanced/testing-events.md
  - id: openwiki-source-d8d06225f857c2f928f9901a
    resource: repo://docs/en/docs/advanced/testing-websockets.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Testing Dependencies, Lifespan Events and WebSockets

## Overriding dependencies

Sometimes a dependency must not run in tests — it calls an external service (e.g. an OAuth provider or payment API), needs a real database, or you want a fixed value. `app.dependency_overrides` is a plain `dict` on the `FastAPI` app: key = the **original** dependency callable, value = the **replacement** callable.

`docs_src/dependency_testing/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return {"message": "Hello Items!", "params": commons}


@app.get("/users/")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return {"message": "Hello Users!", "params": commons}


client = TestClient(app)


async def override_dependency(q: str | None = None):
    return {"q": q, "skip": 5, "limit": 10}


app.dependency_overrides[common_parameters] = override_dependency


def test_override_in_items():
    response = client.get("/items/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Items!",
        "params": {"q": None, "skip": 5, "limit": 10},
    }


def test_override_in_items_with_params():
    response = client.get("/items/?q=foo&skip=100&limit=200")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Items!",
        "params": {"q": "foo", "skip": 5, "limit": 10},
    }
```

How it works:

- FastAPI consults `dependency_overrides` while solving dependencies for every request and calls the override instead of the original — the original and its sub-dependencies don't run.
- The override's **own signature** defines which request parameters are read and validated: here `skip`/`limit` from the URL are ignored because the override doesn't declare them.
- Overrides apply wherever the dependency is used: function parameters, decorator `dependencies=[...]`, routers, `include_router()`, global app dependencies, and sub-dependencies.
- The override can be any callable: `async def`, `def`, a `yield` function, a class, or a lambda (e.g. `lambda: fake_user`).

Reset overrides afterwards so tests stay isolated:

```python
app.dependency_overrides = {}
# or
app.dependency_overrides.clear()
```

To override only in some tests, set the override at the start of the test (or in a pytest fixture) and clear it at the end. Typical uses: settings ([Settings](../app-structure/settings.md) overrides `get_settings`), DB sessions ([Async Tests and Testing Databases](async-tests-and-database-testing.md) overrides `get_session`), and current-user dependencies (return a fixed test user instead of validating tokens).

## Testing lifespan and startup/shutdown

`TestClient` runs the app's **lifespan** only when used as a **context manager**. Startup runs on entering the `with` block, shutdown on leaving it (`docs_src/app_testing/tutorial004_py310.py`):

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

items = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    items["foo"] = {"name": "Fighters"}
    items["bar"] = {"name": "Tenders"}
    yield
    # clean up items
    items.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/items/{item_id}")
async def read_items(item_id: str):
    return items[item_id]


def test_read_items():
    # Before the lifespan starts, "items" is still empty
    assert items == {}

    with TestClient(app) as client:
        # Inside the "with TestClient" block, the lifespan starts and items added
        assert items == {"foo": {"name": "Fighters"}, "bar": {"name": "Tenders"}}

        response = client.get("/items/foo")
        assert response.status_code == 200
        assert response.json() == {"name": "Fighters"}

    # The end of the "with TestClient" block simulates terminating the app, so
    # the lifespan ends and items are cleaned up
    assert items == {}
```

The same applies to deprecated `@app.on_event("startup")` / `("shutdown")` handlers (`tutorial003_py310.py`):

```python
def test_read_items():
    with TestClient(app) as client:
        response = client.get("/items/foo")
        assert response.status_code == 200
        assert response.json() == {"name": "Fighters"}
```

A module-level `client = TestClient(app)` used without `with` does **not** run lifespan. For `httpx.AsyncClient`, use `asgi-lifespan`'s `LifespanManager` ([Async Tests](async-tests-and-database-testing.md)). See [Lifespan Events](../app-structure/lifespan-events.md).

## Testing WebSockets

Use `client.websocket_connect(path)` as a context manager (`docs_src/app_testing/tutorial002_py310.py`):

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

app = FastAPI()


@app.websocket("/ws")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"msg": "Hello WebSocket"})
    await websocket.close()


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data == {"msg": "Hello WebSocket"}
```

The test session supports `send_text()`, `send_bytes()`, `send_json()`, `receive_text()`, `receive_bytes()`, `receive_json()` and `close()`. Pass query parameters in the URL, and `headers=` / cookies on the client for auth. If the server closes or rejects the connection (e.g. `WebSocketException` with code 1008), the test client raises `WebSocketDisconnect`, which you can assert with `pytest.raises`. See [WebSockets](../integrations/websockets.md).

## Related

- [Testing with TestClient](testing-basics.md)
- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
- [How FastAPI Handles a Request](../internals/request-handling-internals.md) — where overrides are applied
