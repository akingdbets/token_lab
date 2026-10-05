---
type: guide
title: Dependency Injection Basics, Classes and Sub-dependencies
description: Declare dependencies with Depends() and Annotated, share them with type aliases, use classes as dependencies (including the Depends() shortcut), build sub-dependency graphs, and control per-request caching with use_cache.
tags: [dependencies, depends, dependency-injection, annotated, classes, sub-dependencies, use_cache]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
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
  - id: openwiki-source-f93db83b191537d04ee5660b
    resource: repo://docs/en/docs/tutorial/dependencies/sub-dependencies.md
  - id: openwiki-source-c46ca1d7e534ec6d650bb745
    resource: repo://fastapi/dependencies/models.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Dependency Injection Basics, Classes and Sub-dependencies

FastAPI's dependency injection lets a path operation declare things it needs — shared parameters, a DB session, the current user — and FastAPI provides them per request. A **dependency** is just a callable (function or class) whose parameters are declared the same way as a path operation's: query, path, header, cookie, body, or other dependencies.

Typical uses: shared logic, database connections, security/authentication, role checks — with no "plugin registration" needed.

## A first dependency

`docs_src/dependencies/tutorial001_an_py310.py`:

```python
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

Per request, FastAPI:

1. Reads `q`, `skip`, `limit` from the query string, converts and validates them (errors → 422).
2. Calls `common_parameters(...)`.
3. Passes the result as `commons`.

The dependency's parameters also appear in the OpenAPI docs for every path operation that uses it.

Pass the function itself — `Depends(common_parameters)` — **don't call it**. `Depends` takes a single callable.

Dependencies can be `async def` or plain `def`, and you can mix them freely with `async def`/`def` path operations. Plain `def` dependencies run in a threadpool, like plain `def` endpoints (see [Python Types and async/await](../getting-started/python-types-and-async.md)).

## Reusable `Annotated` aliases

Because `Annotated[...]` is just a type, store it in a variable and reuse it (`tutorial001_02_an_py310.py`):

```python
CommonsDep = Annotated[dict, Depends(common_parameters)]


@app.get("/items/")
async def read_items(commons: CommonsDep):
    return commons
```

This is the recommended style (e.g. `SessionDep`, `CurrentUser`). The older `commons: dict = Depends(common_parameters)` default-value style still works, but `Annotated` keeps the type and works better with editors and when calling functions directly.

## Classes as dependencies

What FastAPI needs is a **callable** whose parameters it can inspect. A class is callable: calling it runs `__init__`. So a class can be a dependency, and the instance is what you receive — with full editor support (`tutorial002_an_py310.py`):

```python
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

The type in `Annotated[...]` is only for your editor; FastAPI uses the argument of `Depends`. So `Annotated[Any, Depends(CommonQueryParams)]` would work the same (`tutorial003_an_py310.py`).

### The `Depends()` shortcut

When the dependency *is* the annotated class, omit the argument (`tutorial004_an_py310.py`):

```python
async def read_items(commons: Annotated[CommonQueryParams, Depends()]):
    ...
```

If `Depends()` has no dependency, FastAPI uses the annotated type as the dependency (`dataclasses.replace(depends, dependency=type_annotation)` in `fastapi/dependencies/utils.py`).

Pydantic models and dataclasses also work as class dependencies.

## Sub-dependencies

Dependencies can depend on other dependencies, to any depth (`tutorial005_an_py310.py`):

```python
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

FastAPI resolves the graph: `query_extractor` first, then `query_or_cookie_extractor` (which also reads the `last_query` cookie), then the endpoint.

## Per-request caching (`use_cache`)

If the same dependency is used several times in one request (e.g. by two sub-dependencies and the endpoint), FastAPI calls it **once** and reuses the value for that request. The cache key is the dependency callable together with its effective security scopes and dependency scope, so the same callable with different OAuth2 scopes is evaluated separately.

To force a fresh call every time:

```python
async def needy_dependency(fresh_value: Annotated[str, Depends(get_value, use_cache=False)]):
    return {"fresh_value": fresh_value}
```

The cache lives only for one request; for cross-request caching use something like `functools.lru_cache` (see [Settings](../app-structure/settings.md)).

## Where dependencies can be declared

- As parameters (this page) — value is injected.
- In decorators, routers or the whole app with `dependencies=[...]` — value discarded ([Dependencies in Decorators, Routers and Globally](decorator-and-global-dependencies.md)).
- With `yield` for setup/teardown ([Dependencies with yield](dependencies-with-yield.md)).
- As configured callable instances ([Advanced Dependencies](advanced-dependencies.md)).
- In WebSocket endpoints ([WebSockets](../integrations/websockets.md)).

Dependencies may also receive special parameters such as `Request`, `Response`, `BackgroundTasks`, `WebSocket` and `SecurityScopes`.

## Related

- [Security Basics](../security/oauth2-password-flow.md) — `get_current_user` is a sub-dependency chain
- [Testing Dependencies](../testing/testing-dependencies-events-websockets.md) — `app.dependency_overrides`
- [How FastAPI Handles a Request](../internals/request-handling-internals.md)
