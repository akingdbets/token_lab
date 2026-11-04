---
type: guide
title: dependency Injection Basics, Classes and Sub-dependencies
description: Declare dependencies with Depends() and Annotated, share them with type aliases, use classes as dependencies (including the Depends() shortcut), build sub-dependency graphs, and control per-Request caching with use_cache.
tags: [dependencies, depends, dependency-injection, Annotated, classes, sub-dependencies, use_cache]
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

H1: dependency INJECTION BASICS, CLASSES AND SUB-dependencies

FASTAPI dependency INJECTION LETS PATH OPERATIONS DECLARE NEEDS:
SHARED PARAMETERS, DB SESSION, CURRENT USER, ETC.
FASTAPI PROVIDES THESE PER Request.

dependency=CALLABLE (FUNCTION OR CLASS); PARAMETERS DECLARED LIKE
PATH-OPERATION PARAMETERS: QUERY, PATH, HEADER, COOKIE, BODY, OR
OTHER dependencies.

TYPICAL USES: SHARED LOGIC, DATABASE CONNECTIONS,
SECURITY/AUTHENTICATION, ROLE CHECKS; NO "PLUGIN REGISTRATION" NEEDED.

H2: A FIRST dependency

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

PER Request, FASTAPI:

1. READS `q`, `skip`, `limit` FROM QUERY STRING; CONVERTS AND
   VALIDATES THEM (ERRORS → 422).
2. CALLS `common_parameters(...)`.
3. PASSES RESULT AS `commons`.

dependency PARAMETERS ALSO APPEAR IN OpenAPI DOCS FOR EVERY
PATH OPERATION THAT USES IT.

PASS FUNCTION ITSELF — `Depends(common_parameters)` — **DON'T CALL IT**.
`Depends` TAKES ONE CALLABLE.

dependencies CAN BE `async def` OR PLAIN `def`; MIX FREELY WITH
`async def`/`def` PATH OPERATIONS. PLAIN `def` dependencies RUN IN
THREADPOOL, LIKE PLAIN `def` ENDPOINTS (SEE
[Python Types and async/await](../getting-started/python-types-and-async.md)).

H2: REUSABLE `Annotated` ALIASES

`Annotated[...]` IS A TYPE; STORE IT IN A VARIABLE AND REUSE IT
(`tutorial001_02_an_py310.py`):

```python
CommonsDep = Annotated[dict, Depends(common_parameters)]


@app.get("/items/")
async def read_items(commons: CommonsDep):
    return commons
```

RECOMMENDED STYLE (e.g. `SessionDep`, `CurrentUser`).
OLDER `commons: dict = Depends(common_parameters)` DEFAULT-VALUE
STYLE STILL WORKS; `Annotated` KEEPS THE TYPE AND WORKS BETTER WITH
EDITORS AND WHEN CALLING FUNCTIONS DIRECTLY.

H2: CLASSES AS dependencies

FASTAPI NEEDS A **CALLABLE** WHOSE PARAMETERS IT CAN INSPECT.
A CLASS IS CALLABLE: CALLING IT RUNS `__init__`.
THUS, A CLASS CAN BE A dependency; THE RECEIVED VALUE IS THE
INSTANCE, WITH FULL EDITOR SUPPORT (`tutorial002_an_py310.py`):

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

TYPE IN `Annotated[...]` IS ONLY FOR YOUR EDITOR;
FASTAPI USES THE ARGUMENT OF `Depends`.
THUS, `Annotated[Any, Depends(CommonQueryParams)]` WORKS THE SAME
(`tutorial003_an_py310.py`).

H3: THE `Depends()` SHORTCUT

WHEN THE dependency **IS** THE Annotated CLASS, OMIT THE ARGUMENT
(`tutorial004_an_py310.py`):

```python
async def read_items(commons: Annotated[CommonQueryParams, Depends()]):
    ...
```

IF `Depends()` HAS NO dependency, FASTAPI USES Annotated TYPE AS
THE dependency (`dataclasses.replace(depends, dependency=type_annotation)`
IN `fastapi/dependencies/utils.py`).

PYDANTIC MODELS AND DATACLASSES ALSO WORK AS CLASS dependencies.

H2: SUB-dependencies

dependencies CAN DEPEND ON OTHER dependencies, TO Any DEPTH
(`tutorial005_an_py310.py`):

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

FASTAPI RESOLVES THE GRAPH IN THIS ORDER:
`query_extractor` FIRST; THEN `query_or_cookie_extractor` (WHICH ALSO
READS `last_query` COOKIE); THEN THE ENDPOINT.

H2: PER-Request CACHING (`use_cache`)
IF SAME dependency IS USED MULTIPLE TIMES IN ONE Request (e.g., BY TWO SUB-dependencies AND THE ENDPOINT), FastAPI CALLS IT ONCE AND REUSES THE VALUE FOR THAT Request.
CACHE KEY: dependency CALLABLE + EFFECTIVE SECURITY SCOPES + dependency SCOPE
SAME CALLABLE WITH DIFFERENT OAuth2 SCOPES → SEPARATE EVALUATIONS.
FOR A FRESH CALL EVERY TIME:

```python
async def needy_dependency(fresh_value: Annotated[str, Depends(get_value, use_cache=False)]):
    return {"fresh_value": fresh_value}
```

CACHE LIVES FOR ONE Request ONLY; FOR CROSS-Request CACHING, USE SOMETHING LIKE `functools.lru_cache` (SEE [SETTINGS](../app-structure/settings.md)).

H2: WHERE dependencies CAN BE DECLARED

- AS PARAMETERS (THIS PAGE): VALUE INJECTED.
- IN DECORATORS, ROUTERS, OR THE WHOLE APP WITH dependencies=[...]: VALUE DISCARDED ([dependencies IN DECORATORS, ROUTERS AND GLOBALLY](decorator-and-global-dependencies.md)).
- WITH `yield` FOR SETUP/TEARDOWN ([dependencies WITH yield](dependencies-with-yield.md)).
- AS CONFIGURED CALLABLE INSTANCES ([ADVANCED dependencies](advanced-dependencies.md)).
- IN WebSocket ENDPOINTS ([WebSockets](../integrations/websockets.md)).

dependencies MAY ALSO RECEIVE SPECIAL PARAMETERS SUCH AS `Request`, `Response`,
`BackgroundTasks`, `WebSocket`, AND `SecurityScopes`.

H2: RELATED

- [SECURITY BASICS](../security/oauth2-password-flow.md) — `get_current_user` IS A SUB-dependency CHAIN.
- [TESTING dependencies](../testing/testing-dependencies-events-websockets.md) — `app.dependency_overrides`.
- [HOW FASTAPI HANDLES A Request](../internals/Request-handling-internals.md)
