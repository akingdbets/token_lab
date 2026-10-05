---
type: guide
title: Dependencies in Decorators, Routers and Globally
description: Run dependencies whose return values you don't need via dependencies=[Depends(...)] on a path operation decorator, an APIRouter, include_router(), or the whole FastAPI app, and how they are ordered.
tags: [dependencies, depends, decorator, global-dependencies, apirouter, authentication]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-b0a86b25e563ca5939eb329b
    resource: repo://docs_src/dependencies/tutorial006_an_py310.py
  - id: openwiki-source-014453cf0a86d7a4a56e6da5
    resource: repo://docs_src/dependencies/tutorial012_an_py310.py
  - id: openwiki-source-ffe84a85602c83d29ec1965b
    resource: repo://docs/en/docs/tutorial/bigger-applications.md
  - id: openwiki-source-6d0f0988bc9119ce91077111
    resource: repo://docs/en/docs/tutorial/dependencies/dependencies-in-path-operation-decorators.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Dependencies in Decorators, Routers and Globally

Some dependencies exist only for their **side effects** — checking a header, verifying a token, rate-limiting, logging — and their return value isn't needed in the function. Instead of adding an unused parameter, list them in `dependencies=[...]`.

## On a path operation decorator

`docs_src/dependencies/tutorial006_an_py310.py`:

```python
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

- `dependencies` is a `list` of `Depends(...)` (or `Security(...)`).
- They are executed exactly like parameter dependencies: their own parameters (`x_token` from the `X-Token` header) are read, validated and **documented in OpenAPI**; sub-dependencies are resolved.
- They can `raise HTTPException` to stop the request.
- Their return values are discarded (here `verify_key` returns `x_key`, which is ignored). This lets you reuse a normal dependency without editor warnings about unused parameters.

> In real apps, prefer the integrated [security utilities](../security/oauth2-password-flow.md) over hand-rolled header checks.

## On a group of operations (`APIRouter`)

```python
router = APIRouter(
    prefix="/items",
    dependencies=[Depends(get_token_header)],
)
```

or at include time without changing the router:

```python
app.include_router(admin.router, prefix="/admin", dependencies=[Depends(get_token_header)])
```

See [Bigger Applications with APIRouter](../app-structure/bigger-applications.md).

## Global dependencies (whole app)

`docs_src/dependencies/tutorial012_an_py310.py`:

```python
app = FastAPI(dependencies=[Depends(verify_token), Depends(verify_key)])


@app.get("/items/")
async def read_items():
    return [{"item": "Portal Gun"}, {"item": "Plumbus"}]


@app.get("/users/")
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]
```

Every path operation in the app — including those from included routers — now requires both headers.

## Execution order

For a given request the dependency lists are combined from outermost to innermost:

1. App-level `FastAPI(dependencies=...)`
2. Router / `include_router(dependencies=...)` (outer includes before inner)
3. Decorator `dependencies=[...]`
4. Parameter dependencies declared in the function signature

Within a request, the same dependency is evaluated once and cached (unless `use_cache=False`), so a global `verify_token` used again as a parameter is not called twice. See [Dependency Injection Basics](dependency-injection-basics.md).

## Using `yield` dependencies here

Decorator, router and global dependencies may be `yield` dependencies too (e.g. to open/close something around every request). Their teardown follows the normal rules in [Dependencies with yield](dependencies-with-yield.md).

## Related

- [Security Basics](../security/oauth2-password-flow.md) — protecting a whole router with an auth dependency
- [Testing Dependencies](../testing/testing-dependencies-events-websockets.md) — overriding global dependencies in tests
