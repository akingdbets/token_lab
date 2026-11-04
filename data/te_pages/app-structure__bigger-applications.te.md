---
type: guide
title: Bigger Applications with APIRouter
description: SPLIT FASTAPI APPS INTO MODULES WITH APIRouter; APPLY PREFIX, tags,
  responses, dependencies PER router OR AT INCLUDE TIME; NEST routers; CONFIGURE CLI ENTRYPOINT.
tags: [APIRouter, include_router, project-structure, routing, dependencies, tags]
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

H1: Bigger Applications with APIRouter

app GROWS BEYOND ONE FILE? FASTAPI GROUPS *path OPERATIONS* INTO
`APIRouter` OBJECTS (ONE PER MODULE), THEN COMBINES THEM IN MAIN `FastAPI`
app WITH `include_router()`. THINK OF `APIRouter` AS A "MINI `FastAPI`":
SUPPORTS SAME DECORATORS (`.get()`, `.post()`, `.put()`, `.delete()`,
`.websocket()`, …) and PARAMETERS.

H2: Example layout

TUTORIAL EXAMPLE: `docs_src/bigger_applications/app_an_py310/`

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

EACH DIRECTORY HAS AN `__init__.py`, MAKING `app` A PYTHON PACKAGE;
ENABLES RELATIVE IMPORTS SUCH AS
`from ..dependencies import get_token_header` (TWO DOTS = PARENT PACKAGE).

H2: A plain router

`app/routers/users.py` CREATES A router and DECLARES path OPERATIONS
JUST AS WITH `app`:

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

ORDER MATTERS: DECLARE `/users/me` BEFORE `/users/{username}` SO FIXED
path WINS (SEE [path Parameters](../request/path-parameters.md)).

H2: Shared settings on the router

INSTEAD OF REPEATING PREFIX, tags, responses, dependencies IN EVERY
DECORATOR, PASS THEM TO `APIRouter(...)`. from `app/routers/items.py`:

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

RESULT:

- PATHS BECOME `/items/` and `/items/{item_id}`.
- ALL OPERATIONS GET TAG `items`; `update_item` GETS `items` and `custom`.
- ALL OPERATIONS DOCUMENT `404` RESPONSE; `update_item` ALSO DOCUMENTS `403`.
- `get_token_header` RUNS BEFORE EACH REQUEST TO THESE OPERATIONS. ITS
  RETURN VALUE IS **NOT** PASSED TO YOUR FUNCTION (SAME AS
  [dependencies IN DECORATORS](../dependencies/decorator-and-global-dependencies.md)).

`prefix` RULES (ASSERTIONS ENFORCE THESE IN `APIRouter.__init__` and
`include_router`):

- MUST START WITH `/`.
- MUST **NOT** END WITH `/`, SINCE EVERY ROUTE path ALREADY STARTS WITH `/`.
- IF INCLUDE PREFIX and ROUTE path ARE both empty, `include_router` RAISES
  `FastAPIError("Prefix and path cannot be both empty ...")`.

REQUEST DEPENDENCY ORDER: router dependencies FIRST; THEN DECORATOR'S
`dependencies=[...]`; THEN NORMAL PARAMETER dependencies.

SHARED dependencies IN `app/dependencies.py`:

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

H2: The main app

`app/main.py` IMPORTS router *MODULES* (NOT `router` VARIABLES, TO AVOID
COLLISION BETWEEN THE TWO `router` NAMES), THEN INCLUDES THEM:

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

- `FastAPI(dependencies=[...])` ADDS A **GLOBAL** DEPENDENCY TO EVERY
  OPERATION, INCLUDING router OPERATIONS.
- `include_router()` ACCEPTS SAME GROUPING OPTIONS AS `APIRouter()`:
  `prefix`, `tags`, `dependencies`, `responses`, PLUS
  `default_response_class`, `callbacks`, `deprecated`, `include_in_schema`
  and `generate_unique_id_function`. CONFIGURE A router YOU cannot EDIT
  (HERE `admin.router`, IMAGINED AS SHARED WITH OTHER PROJECTS) FOR THIS
  app ONLY; OTHER APPS CAN INCLUDE SAME router WITH DIFFERENT SETTINGS.
- path OPERATIONS CAN STILL be ADDED DIRECTLY ON `app`.

H2: routers are included "live", not copied
routers ARE NOT MOUNTED AS ISOLATED SUB-APPS; THEIR OPERATIONS BELONG TO THE SAME app and OpenAPI SCHEMA. IN THIS FASTAPI VERSION, `include_router()` APPENDS AN INTERNAL `_IncludedRouter` ENTRY REFERENCING THE ORIGINAL router and INCLUDE CONTEXT. FASTAPI COMBINES PREFIXES, dependencies, tags, responses and OTHER METADATA WHEN MATCHING REQUESTS and GENERATING OpenAPI.

PRACTICAL CONSEQUENCES:
- path OPERATIONS ADDED TO A router AFTER INCLUSION REMAIN VISIBLE THROUGH THE EARLIER INCLUSION.
- `router.include_router(other_router)` CAN OCCUR BEFORE OR AFTER INCLUDING `router` IN THE app.
- DO NOT MUTATE `router.routes` DIRECTLY AFTER INCLUSION. TREAT IT AS A LOWER-LEVEL ROUTE TREE, WHICH MAY CONTAIN INCLUDED routers, NOT A FLAT LIST OF FINAL OPERATIONS. USE DECORATORS and `include_router()` INSTEAD.
- A router cannot INCLUDE ITSELF OR A router THAT ALREADY INCLUDES IT; both RAISE AN ASSERTION ERROR.

H2: INCLUDING A router MULTIPLE TIMES

THE SAME router CAN be INCLUDED MORE THAN ONCE WITH DIFFERENT PREFIXES, E.G., TO EXPOSE THE SAME API UNDER `/api/v1` and `/api/latest`:

```python
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api/latest")
```

H2: NESTING routers

```python
router.include_router(other_router)
app.include_router(router)
```

PREFIXES and OTHER SETTINGS ACCUMULATE from THE OUTER INCLUDE TO THE INNER router.

H2: TELLING THE CLI WHERE THE app IS

BECAUSE THE app NOW LIVES IN `app/main.py`, CONFIGURE THE ENTRYPOINT ONCE IN `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

THEN `fastapi dev` / `fastapi run` FIND THE app WITHOUT A path ARGUMENT; SO DO THE EDITOR EXTENSION and FASTAPI CLOUD. SEE [FIRST STEPS and THE FASTAPI CLI](../getting-started/first-steps.md).

H2: RELATED

- [dependencies IN DECORATORS, routers and GLOBALLY](../dependencies/decorator-and-global-dependencies.md)
- [path OPERATION CONFIGURATION](path-operation-configuration.md) — tags, SUMMARIES, DEPRECATION
- [SUB-APPLICATIONS](sub-applications-proxy-and-wsgi.md) — USE `app.mount()` WHEN YOU WANT AN ISOLATED, SEPARATELY DOCUMENTED app
