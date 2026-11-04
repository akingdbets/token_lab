---
type: guide
title: TESTING with TestClient
description: TEST FastAPI APPS with pytest AND TestClient (HTTPX-BASED): PLAIN def test FUNCTIONS; app/TEST MODULE SEPARATION; PATH/QUERY PARAMETERS, headers, JSON BODIES, FORM data, cookies.
tags: [testing, TestClient, pytest, httpx]
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

H1: TESTING with TestClient

Test FastAPI APPS IN-PROCESS VIA `TestClient`; NO SERVER NEEDED.
`TestClient` BUILT ON **HTTPX**; API MIRRORS `requests`; WORKS with **pytest**.

INSTALL DEPENDENCIES; `httpx` INCLUDED IN `fastapi[standard]`:

```bash
uv add httpx
uv add pytest
```

`fastapi.testclient.TestClient` = Starlette's `TestClient`, RE-EXPORTED.

H2: A FIRST TEST

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

- CREATE `TestClient(app)`.
- NAME TEST FUNCTIONS `test_...` (pytest CONVENTION).
- USE CLIENT LIKE HTTPX CLIENT: `client.get()`, `client.post()`, `client.put()`, `client.delete()`, ...
- assert `response.status_code`, `response.json()`, `response.headers`, `response.text`
  with PLAIN `assert`.

TEST FUNCTIONS USE NORMAL `def`, EVEN IF ENDPOINTS USE `async def`;
CLIENT RUNS app.
IF TEST ITSELF MUST `await` (e.g., async DB CALL), SEE
[async TESTS](async-tests-and-database-testing.md).

RUN:

```bash
uv run pytest
```

H2: SEPARATING app AND TESTS

TYPICAL LAYOUT: `docs_src/app_testing/app_a_py310/`

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

`__init__.py` ENABLES RELATIVE import `from .main import app`.

H2: EXTENDED EXAMPLE: headers, BODIES, ERROR CASES

app: `docs_src/app_testing/app_b_an_py310/main.py`

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

TESTS: `test_main.py` (EXCERPT)

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

TEST SUCCESS AND FAILURE PATHS: BAD TOKEN → 400; MISSING ITEM → 404;
DUPLICATE → 409.

H2: PASSING data IN requests

| data | HOW |
|------|-----|
| PATH / QUERY PARAMETERS | URL: `client.get("/items/foo?q=1")`, OR `params={"q": 1}` |
| JSON BODY | `json={...}` |
| FORM data | `data={...}` |
| files | `files={"file": ("name.txt", b"content")}` |
| headers | `headers={...}` |
| cookies | `cookies={...}` (REQUEST OR CLIENT) |

API FOLLOWS HTTPX AND `requests`; THEIR DOCS ANSWER MOST
"HOW DO I SEND X" QUESTIONS.

SEND PYDANTIC MODEL AS JSON: FIRST CONVERT with `jsonable_encoder`
([EXTRA MODELS AND jsonable_encoder](../models/extra-models-and-updates.md))
OR `model.model_dump(mode="json")`.

H2: RELATED

- [TESTING DEPENDENCIES, LIFESPAN EVENTS AND WebSockets](testing-dependencies-events-websockets.md) —
  `dependency_overrides`, `with TestClient(app)`, `websocket_connect`
- [async TESTS AND TESTING DATABASES](async-tests-and-database-testing.md)
- [SETTINGS](../app-structure/settings.md) — OVERRIDE SETTINGS IN TESTS
