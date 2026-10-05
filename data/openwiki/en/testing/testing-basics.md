---
type: guide
title: Testing with TestClient
description: Test FastAPI apps with pytest and TestClient (HTTPX-based) — plain def test functions, separating app and tests into modules, and sending path/query parameters, headers, JSON bodies, form data and cookies.
tags: [testing, testclient, pytest, httpx]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-252031fc006dbd553c56ddbf
    resource: repo://docs_src/app_testing/app_a_py310/test_main.py
  - id: openwiki-source-8b271ea1e444e5315902fb58
    resource: repo://docs_src/app_testing/app_b_an_py310/main.py
  - id: openwiki-source-b4dc3eb56757a33b2aed4ee7
    resource: repo://docs_src/app_testing/app_b_an_py310/test_main.py
  - id: openwiki-source-495efc9c9a17fc0e77fcccf1
    resource: repo://docs_src/app_testing/tutorial001_py310.py
  - id: openwiki-source-e77ebf2ef52c5a94eb476b8b
    resource: repo://docs/en/docs/tutorial/testing.md
  - id: openwiki-source-c2aa67a6d15b272c485d017f
    resource: repo://fastapi/testclient.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Testing with TestClient

FastAPI apps are tested with `TestClient`, which calls your app in-process (no server needed). It's built on **HTTPX**, whose API mirrors `requests`, and works directly with **pytest**.

Install the dependencies (`httpx` is part of `fastapi[standard]`):

```bash
uv add httpx
uv add pytest
```

`fastapi.testclient.TestClient` is Starlette's `TestClient`, re-exported.

## A first test

`docs_src/app_testing/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Hello World"}
```

- Create a `TestClient(app)`.
- Write functions named `test_...` (pytest convention).
- Use the client like an HTTPX client: `client.get()`, `client.post()`, `client.put()`, `client.delete()`, ...
- Assert with plain `assert` on `response.status_code`, `response.json()`, `response.headers`, `response.text`.

Test functions are **normal `def`**, even when your endpoints are `async def` — the client runs the app for you. If the test itself must `await` things (e.g. an async DB call), see [Async Tests](async-tests-and-database-testing.md).

Run:

```bash
uv run pytest
```

## Separating app and tests

Typical layout (`docs_src/app_testing/app_a_py310/`):

```
.
├── app
│   ├── __init__.py
│   ├── main.py
│   └── test_main.py
```

```python
# main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}
```

```python
# test_main.py
from fastapi.testclient import TestClient

from .main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Hello World"}
```

Thanks to `__init__.py`, the relative import `from .main import app` works.

## Extended example: headers, bodies, error cases

App (`docs_src/app_testing/app_b_an_py310/main.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

fake_secret_token = "coneofsilence"

fake_db = {
    "foo": {"id": "foo", "title": "Foo", "description": "There goes my hero"},
    "bar": {"id": "bar", "title": "Bar", "description": "The bartenders"},
}

app = FastAPI()


class Item(BaseModel):
    id: str
    title: str
    description: str | None = None


@app.get("/items/{item_id}", response_model=Item)
async def read_main(item_id: str, x_token: Annotated[str, Header()]):
    if x_token != fake_secret_token:
        raise HTTPException(status_code=400, detail="Invalid X-Token header")
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]


@app.post("/items/")
async def create_item(item: Item, x_token: Annotated[str, Header()]) -> Item:
    if x_token != fake_secret_token:
        raise HTTPException(status_code=400, detail="Invalid X-Token header")
    if item.id in fake_db:
        raise HTTPException(status_code=409, detail="Item already exists")
    fake_db[item.id] = item.model_dump()
    return item
```

Tests (`test_main.py`, excerpt):

```python
def test_read_item():
    response = client.get("/items/foo", headers={"X-Token": "coneofsilence"})
    assert response.status_code == 200
    assert response.json() == {
        "id": "foo",
        "title": "Foo",
        "description": "There goes my hero",
    }


def test_read_item_bad_token():
    response = client.get("/items/foo", headers={"X-Token": "hailhydra"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid X-Token header"}


def test_create_item():
    response = client.post(
        "/items/",
        headers={"X-Token": "coneofsilence"},
        json={"id": "foobar", "title": "Foo Bar", "description": "The Foo Barters"},
    )
    assert response.status_code == 200


def test_create_existing_item():
    response = client.post(
        "/items/",
        headers={"X-Token": "coneofsilence"},
        json={
            "id": "foo",
            "title": "The Foo ID Stealers",
            "description": "There goes my stealer",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Item already exists"}
```

Test both success and failure paths (bad token → 400, missing item → 404, duplicate → 409).

## Passing data in requests

| Data | How |
|------|-----|
| Path / query parameters | in the URL: `client.get("/items/foo?q=1")`, or `params={"q": 1}` |
| JSON body | `json={...}` |
| Form data | `data={...}` |
| Files | `files={"file": ("name.txt", b"content")}` |
| Headers | `headers={...}` |
| Cookies | `cookies={...}` (on the request or the client) |

Since the API follows HTTPX (and `requests`), their docs answer most "how do I send X" questions.

To send a Pydantic model as JSON, convert it first with `jsonable_encoder` ([Extra Models and jsonable_encoder](../models/extra-models-and-updates.md)) or `model.model_dump(mode="json")`.

## Related

- [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md) — `dependency_overrides`, `with TestClient(app)`, `websocket_connect`
- [Async Tests and Testing Databases](async-tests-and-database-testing.md)
- [Settings](../app-structure/settings.md) — overriding settings in tests
