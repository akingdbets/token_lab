---
type: guide
title: ADVANCED dependencies
description: PARAMETERIZED dependencies USE CALLABLE CLASS INSTANCES AND Depends(use_cache, scope) OPTIONS; EXIT-CODE TIMING FOR dependencies with yield CHANGED ACROSS FastAPI VERSIONS (StreamingResponse, except, BACKGROUND TASKS).
tags: [dependencies, Depends, callable, scope, yield, StreamingResponse, background-tasks]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - ID: openwiki-source-36f6cb15f05a73d08e616361
    resource: repo://docs_src/dependencies/tutorial008e_an_py310.py
  - ID: openwiki-source-7811fd42dc79501daac1aed0
    resource: repo://docs_src/dependencies/tutorial011_an_py310.py
  - ID: openwiki-source-f4d3e24f1d5c2b648dac6455
    resource: repo://docs_src/dependencies/tutorial014_an_py310.py
  - ID: openwiki-source-8ae43a06e68950dd31ba2a17
    resource: repo://docs/en/docs/advanced/advanced-dependencies.md
  - ID: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://FastAPI/dependencies/utils.py
  - ID: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://FastAPI/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: ADVANCED dependencies

THIS PAGE BUILDS on [dependency INJECTION BASICS](dependency-injection-basics.md)
AND [dependencies with yield](dependencies-with-yield.md).

H2: The `Depends` OPTIONS

`fastapi.params.Depends` IS A SMALL FROZEN DATACLASS with 3 FIELDS:

| FIELD | DEFAULT | MEANING |
|-------|---------|---------|
| `dependency` | `None` | CALLABLE; IF OMITTED with `Annotated[SomeClass, Depends()]`, USE Annotated TYPE. |
| `use_cache` | `True` | REUSE VALUE IF SAME dependency NEEDED MORE THAN ONCE IN ONE request; `False` CALLS it EVERY TIME. |
| `scope` | `None` | FOR `yield` dependencies: `"request"` (DEFAULT) OR `"function"`; SEE BELOW. |

`fastapi.params.Security` SUBCLASSES `Depends` AND ADDS `scopes`;
SEE [OAUTH2 scopes](../security/oauth2-scopes.md).

H2: PARAMETERIZED dependencies with CALLABLE INSTANCES

SOMETIMES, CONFIGURE ONE dependency IMPLEMENTATION with DIFFERENT PARAMETERS.
ANY CALLABLE CAN BE A dependency, INCLUDING A CLASS INSTANCE DEFINING `__call__`.

`docs_src/dependencies/tutorial011_an_py310.py`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


class FixedContentQueryChecker:
    def __init__(self, fixed_content: str):
        self.fixed_content = fixed_content

    def __call__(self, q: str = ""):
        if q:
            return self.fixed_content in q
        return False


checker = FixedContentQueryChecker("bar")


@app.get("/query-checker/")
async def read_query_check(fixed_content_included: Annotated[bool, Depends(checker)]):
    return {"fixed_content_in_query": fixed_content_included}
```

- FastAPI NEVER INSPECTS `__init__`; YOU CALL it TO CONFIGURE The INSTANCE (`"bar"`).
- FastAPI INSPECTS `__call__`'S SIGNATURE FOR request PARAMETERS AND
  SUB-dependencies (`q` BECOMES A QUERY PARAMETER); THEN CALLS `checker(q=...)`
  PER request.
- USE `Depends(checker)` (The INSTANCE), NOT `Depends(FixedContentQueryChecker)`.

SECURITY UTILITIES WORK The SAME WAY:
`OAuth2PasswordBearer(tokenUrl="token")`, `HTTPBasic()`, AND
`APIKeyHeader(name=...)` ARE CONFIGURED INSTANCES with AN
`async def __call__(self, request)`. SEE [SECURITY BASICS]
(../security/oauth2-password-flow.md).

H2: dependency `scope` FOR `yield` dependencies

SINCE FastAPI 0.121.0, dependencies with `yield` ACCEPT `Depends(scope=...)`:

- `scope="request"` (DEFAULT): EXIT CODE RUNS AFTER RESPONSE has BEEN SENT.
- `scope="function"`: EXIT CODE RUNS RIGHT AFTER PATH OPERATION function RETURNS,
  BEFORE RESPONSE IS SENT.

```python
def get_username():
    try:
        yield "Rick"
    finally:
        print("Cleanup up before response is sent")


@app.get("/users/me")
def get_user_me(username: Annotated[str, Depends(get_username, scope="function")]):
    return username
```

INTERNALLY, FastAPI KEEPS 2 EXIT STACKS PER request: ONE FOR request scope,
ONE FOR function scope; EACH GENERATOR dependency GOES on ITS MATCHING STACK.

RULE: A request-scope `yield` dependency cannot depend on A
`scope="function"` SUB-dependency; The SUB-dependency WOULD BE TORN DOWN
BEFORE ITS PARENT. FastAPI RAISES `DependencyScopeError` AT ROUTE SETUP,
e.g. *`The dependency "get_session" has a scope of "request", it cannot depend on dependencies with scope "function".`*

H2: EXIT-CODE TIMING EVOLUTION (TROUBLESHOOTING OLDER APPS)

ONLY NEEDED WHEN UPGRADING AN OLDER APP AND `yield` dependencies SHOW
SURPRISING BEHAVIOR.
- **< 0.106.0**: EXIT CODE RAN AFTER RESPONSE AND BACKGROUND TASKS; BACKGROUND TASKS COULD REUSE YIELDED OBJECTS (e.g., A DB SESSION), BUT EXCEPTIONS RAISED AFTER `yield` COULD NOT REACH EXCEPTION HANDLERS.
- **0.106.0**: EXIT CODE MOVED BEFORE RESPONSE SENDING; RESOURCES NOT HELD WHILE RESPONSE TRAVELED. BACKGROUND TASKS SHOULD CREATE THEIR OWN RESOURCES (e.g., OPEN A NEW DB SESSION AND PASS AN OBJECT **ID**, NOT The ORM OBJECT).
- **0.110.0**: CATCHING AN EXCEPTION with `except` IN A `yield` dependency WITHOUT RE-RAISING NO LONGER AUTOMATICALLY FORWARDS it TO HANDLERS; CONSISTENT with PLAIN PYTHON. RE-raise (`raise`) TO KEEP it PROPAGATING.
- **0.118.0**: EXIT CODE AGAIN RUNS **AFTER RESPONSE SENT**; `StreamingResponse` CAN USE A YIELDED DB SESSION WHILE STREAMING.
- **0.121.0**: `Depends(scope="function")` ADDED TO OPT INTO EARLY EXIT.

H3: RELEASING A RESOURCE EARLY BY HAND

DEFAULT request scope: SESSION YIELDED BY `get_session` STAYS OPEN UNTIL SLOW `StreamingResponse` FINISHES, EVEN IF ONLY AN AUTH dependency USED it (`docs_src/dependencies/tutorial013_an_py310.py`). IF THIS MATTERS, CLOSE it EXPLICITLY WHEN DONE (`tutorial014_an_py310.py`):

```python
def get_session():
    with Session(engine) as session:
        yield session


def get_user(user_id: int, session: Annotated[Session, Depends(get_session)]):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=403, detail="Not authorized")
    session.close()


def generate_stream(query: str):
    for ch in query:
        yield ch
        time.sleep(0.1)


@app.get("/generate", dependencies=[Depends(get_user)])
def generate(query: str):
    return StreamingResponse(content=generate_stream(query))
```

H2: RELATED

- [TESTING dependencies](../testing/testing-dependencies-events-websockets.md) — `app.dependency_overrides`
- [BACKGROUND TASKS](../integrations/background-tasks.md)
- [HOW FastAPI HANDLES A request](../internals/request-handling-internals.md)
