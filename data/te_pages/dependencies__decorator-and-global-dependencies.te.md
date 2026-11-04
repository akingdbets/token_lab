---
type: guide
title: dependencies IN DECORATORS, ROUTERS AND GLOBALLY
description: Run dependencies with unused return values via dependencies=[Depends(...)] on a path operation decorator, APIRouter, include_router(), or whole FastAPI app; ordering explained.
tags: [dependencies, Depends, decorator, global-dependencies, APIRouter, authentication]
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

H1: dependencies IN DECORATORS, ROUTERS AND GLOBALLY

dependencies MAY SERVE SIDE EFFECTS ONLY: HEADER CHECKING, Token VERIFICATION,
RATE-LIMITING, LOGGING; RETURN VALUE UNNEEDED. INSTEAD OF UNUSED PARAMETER,
list dependencies IN `dependencies=[...]`.

H2: ON A PATH OPERATION DECORATOR

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

- `dependencies` LISTS `Depends(...)` OR `Security(...)`.
- EXECUTION MATCHES PARAMETER dependencies: THEIR PARAMETERS (`x_token` FROM
  `X-Token` HEADER) ARE READ, VALIDATED AND **DOCUMENTED IN OpenAPI**;
  SUB-dependencies RESOLVED.
- dependencies CAN `raise HTTPException` TO STOP REQUEST.
- RETURN VALUES DISCARDED: HERE, `verify_key` RETURNS `x_key`, IGNORED.
  REUSE NORMAL dependencies WITHOUT EDITOR WARNINGS ABOUT UNUSED PARAMETERS.

> REAL APPS: PREFER INTEGRATED [Security UTILITIES](../Security/oauth2-password-flow.md)
> OVER HAND-ROLLED HEADER CHECKS.

H2: ON A GROUP OF OPERATIONS (`APIRouter`)

```python
router = APIRouter(
    prefix="/items",
    dependencies=[Depends(get_token_header)],
)
```

OR ADD dependencies AT INCLUDE TIME WITHOUT CHANGING ROUTER:

```python
app.include_router(admin.router, prefix="/admin", dependencies=[Depends(get_token_header)])
```

SEE [BIGGER APPLICATIONS WITH APIRouter](../app-structure/bigger-applications.md).

H2: GLOBAL dependencies (WHOLE APP)

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

EVERY APP PATH OPERATION, INCLUDING OPERATIONS FROM INCLUDED ROUTERS,
NOW REQUIRES BOTH HEADERS.

H2: EXECUTION ORDER

REQUEST DEPENDENCY LISTS COMBINE OUTERMOST TO INNERMOST:

1. APP-LEVEL `FastAPI(dependencies=...)`
2. ROUTER / `include_router(dependencies=...)`; OUTER INCLUDES BEFORE INNER
3. DECORATOR `dependencies=[...]`
4. PARAMETER dependencies IN FUNCTION SIGNATURE

WITHIN A REQUEST, EACH DEPENDENCY EVALUATES ONCE AND IS CACHED
(UNLESS `use_cache=False`); GLOBAL `verify_token` REUSED AS A PARAMETER
IS NOT CALLED TWICE. SEE [DEPENDENCY INJECTION BASICS](dependency-injection-basics.md).

H2: USING `yield` dependencies HERE

DECORATOR, ROUTER AND GLOBAL dependencies MAY ALSO USE `yield`
(e.g., OPEN/CLOSE SOMETHING AROUND EVERY REQUEST). TEARDOWN FOLLOWS
NORMAL RULES IN [dependencies WITH yield](dependencies-with-yield.md).

H2: RELATED

- [Security BASICS](../Security/oauth2-password-flow.md) — PROTECT WHOLE ROUTER
  WITH AUTH DEPENDENCY
- [TESTING dependencies](../testing/testing-dependencies-events-websockets.md) —
  OVERRIDE GLOBAL dependencies IN TESTS
