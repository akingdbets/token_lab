---
type: guide
title: Bigger Applications with APIRouter
description: How to split a FastAPI app into multiple modules with APIRouter, apply prefix, tags, responses and dependencies per router or at include time, nest routers, and configure the CLI entrypoint.
tags: [apirouter, include_router, project-structure, routing, dependencies, tags]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-689087189304d4d19a915e26
    resource: repo://docs_src/bigger_applications/app_an_py310/main.py
  - id: openwiki-source-a93f3fe8fdcae43cc7777c57
    resource: repo://docs_src/bigger_applications/app_an_py310/routers/items.py
  - id: openwiki-source-ffe84a85602c83d29ec1965b
    resource: repo://docs/en/docs/tutorial/bigger-applications.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Bigger Applications with APIRouter

When an app grows beyond one file, FastAPI lets you group *path operations* into `APIRouter` objects (one per module) and combine them in the main `FastAPI` app with `include_router()`. Think of `APIRouter` as a "mini `FastAPI`": it supports the same decorators (`.get()`, `.post()`, `.put()`, `.delete()`, `.websocket()`, …) and the same parameters.

## Example layout

The tutorial example lives in `docs_src/bigger_applications/app_an_py310/`:

```
app/
├── __init__.py
├── main.py             # creates FastAPI() and includes routers
├── dependencies.py     # shared dependencies
├── routers/
│   ├── __init__.py
│   ├── items.py        # APIRouter with prefix /items
│   └── users.py        # APIRouter without prefix
└── internal/
    ├── __init__.py
    └── admin.py        # a router "shared with other projects"
```

Each directory has an `__init__.py`, which makes `app` a Python package so you can use relative imports such as `from ..dependencies import get_token_header` (two dots = parent package).

## A plain router

`app/routers/users.py` creates a router and declares path operations exactly as you would with `app`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/users/", tags=["users"])
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]


@router.get("/users/me", tags=["users"])
async def read_user_me():
    return {"username": "fakecurrentuser"}


@router.get("/users/{username}", tags=["users"])
async def read_user(username: str):
    return {"username": username}
```

Note the order: `/users/me` is declared before `/users/{username}` so the fixed path wins (see [Path Parameters](../request/path-parameters.md)).

## Shared settings on the router

Instead of repeating the same prefix, tags, responses and dependencies in every decorator, pass them to `APIRouter(...)`. From `app/routers/items.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_token_header

router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)

fake_items_db = {"plumbus": {"name": "Plumbus"}, "gun": {"name": "Portal Gun"}}


@router.get("/")
async def read_items():
    return fake_items_db


@router.get("/{item_id}")
async def read_item(item_id: str):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"name": fake_items_db[item_id]["name"], "item_id": item_id}


@router.put(
    "/{item_id}",
    tags=["custom"],
    responses={403: {"description": "Operation forbidden"}},
)
async def update_item(item_id: str):
    ...
```

Resulting behavior:

- Paths become `/items/` and `/items/{item_id}`.
- All operations get the tag `items`; `update_item` gets both `items` and `custom`.
- All operations document the `404` response; `update_item` additionally documents `403`.
- `get_token_header` runs before each request to these operations. Its return value is **not** passed to your function (same as [dependencies in decorators](../dependencies/decorator-and-global-dependencies.md)).

Rules for `prefix` (enforced by assertions in `APIRouter.__init__` and `include_router`):

- It must start with `/`.
- It must **not** end with `/`, because every route path already starts with `/`.
- If both the include prefix and a route's path are empty, `include_router` raises `FastAPIError("Prefix and path cannot be both empty ...")`.

Dependency order for a request: router dependencies first, then the decorator's `dependencies=[...]`, then normal parameter dependencies.

The shared dependencies in `app/dependencies.py`:

```python
from typing import Annotated

from fastapi import Header, HTTPException


async def get_token_header(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def get_query_token(token: str):
    if token != "jessica":
        raise HTTPException(status_code=400, detail="No Jessica token provided")
```

## The main app

`app/main.py` imports the router *modules* (not the `router` variables, to avoid the two `router` names colliding) and includes them:

```python
from fastapi import Depends, FastAPI

from .dependencies import get_query_token, get_token_header
from .internal import admin
from .routers import items, users

app = FastAPI(dependencies=[Depends(get_query_token)])


app.include_router(users.router)
app.include_router(items.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_token_header)],
    responses={418: {"description": "I'm a teapot"}},
)


@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications!"}
```

- `FastAPI(dependencies=[...])` adds a **global** dependency to every operation, including those from routers.
- `include_router()` accepts the same grouping options as `APIRouter()` — `prefix`, `tags`, `dependencies`, `responses`, plus `default_response_class`, `callbacks`, `deprecated`, `include_in_schema` and `generate_unique_id_function`. This lets you configure a router you cannot edit (here `admin.router`, imagined as shared with other projects) only for this app; other apps can include the same router with different settings.
- You can still add path operations directly on `app`.

## Routers are included "live", not copied

Routers are not mounted as isolated sub-apps; their operations are part of the same app and the same OpenAPI schema. In this version of FastAPI, `include_router()` appends an internal `_IncludedRouter` entry that references the original router and the include context, and FastAPI combines prefixes, dependencies, tags, responses and other metadata when matching requests and generating OpenAPI. Practical consequences:

- Path operations added to a router **after** it was included are still visible through the earlier inclusion.
- You can `router.include_router(other_router)` before or after including `router` in the app.
- Do not mutate `router.routes` directly after inclusion; treat it as a lower-level route tree (it may contain included routers), not a flat list of final operations. Use decorators and `include_router()` instead.
- A router cannot include itself, nor a router that already includes it (both raise an assertion error).

## Including a router multiple times

The same router can be included more than once with different prefixes, for example to expose the same API under `/api/v1` and `/api/latest`:

```python
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api/latest")
```

## Nesting routers

```python
router.include_router(other_router)
app.include_router(router)
```

Prefixes and other settings accumulate from the outer include to the inner router.

## Telling the CLI where the app is

Because the app now lives in `app/main.py`, configure the entrypoint once in `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

Then `fastapi dev` / `fastapi run` find it without a path argument, and so do the editor extension and FastAPI Cloud. See [First Steps and the FastAPI CLI](../getting-started/first-steps.md).

## Related

- [Dependencies in Decorators, Routers and Globally](../dependencies/decorator-and-global-dependencies.md)
- [Path Operation Configuration](path-operation-configuration.md) — tags, summaries, deprecation
- [Sub-applications](sub-applications-proxy-and-wsgi.md) — when you *do* want an isolated, separately documented app (`app.mount()`)
