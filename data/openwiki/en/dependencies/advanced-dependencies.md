---
type: guide
title: Advanced Dependencies
description: Parameterized dependencies using callable class instances, the Depends(use_cache, scope) options, and how the timing of exit code in dependencies with yield has changed across FastAPI versions (StreamingResponse, except, background tasks).
tags: [dependencies, depends, callable, scope, yield, streamingresponse, background-tasks]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-36f6cb15f05a73d08e616361
    resource: repo://docs_src/dependencies/tutorial008e_an_py310.py
  - id: openwiki-source-7811fd42dc79501daac1aed0
    resource: repo://docs_src/dependencies/tutorial011_an_py310.py
  - id: openwiki-source-f4d3e24f1d5c2b648dac6455
    resource: repo://docs_src/dependencies/tutorial014_an_py310.py
  - id: openwiki-source-8ae43a06e68950dd31ba2a17
    resource: repo://docs/en/docs/advanced/advanced-dependencies.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Advanced Dependencies

This page builds on [Dependency Injection Basics](dependency-injection-basics.md) and [Dependencies with yield](dependencies-with-yield.md).

## The `Depends` options

`fastapi.params.Depends` is a small frozen dataclass with three fields:

| Field | Default | Meaning |
|-------|---------|---------|
| `dependency` | `None` | The callable. If omitted with `Annotated[SomeClass, Depends()]`, the annotated type is used. |
| `use_cache` | `True` | Reuse the value if the same dependency is needed more than once in one request. Set `False` to call it every time. |
| `scope` | `None` | For `yield` dependencies: `"request"` (default behavior) or `"function"` — see below. |

`fastapi.params.Security` subclasses `Depends` and adds `scopes` (see [OAuth2 Scopes](../security/oauth2-scopes.md)).

## Parameterized dependencies with callable instances

Sometimes you want one dependency implementation configured with different parameters. Any **callable** can be a dependency — including an *instance* of a class that defines `__call__`.

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

- FastAPI never looks at `__init__`; **you** call it to configure the instance (`"bar"`).
- FastAPI inspects `__call__`'s signature for request parameters and sub-dependencies (`q` becomes a query parameter), then calls `checker(q=...)` per request.
- Use `Depends(checker)` (the instance), not `Depends(FixedContentQueryChecker)`.

This is exactly how the security utilities work: `OAuth2PasswordBearer(tokenUrl="token")`, `HTTPBasic()`, `APIKeyHeader(name=...)` are configured instances with an `async def __call__(self, request)`. See [Security Basics](../security/oauth2-password-flow.md).

## Dependency `scope` for `yield` dependencies

Since FastAPI 0.121.0, dependencies with `yield` accept `Depends(scope=...)`:

- `scope="request"` (default): exit code after `yield` runs **after the response has been sent**.
- `scope="function"`: exit code runs right after the path operation function returns, **before** the response is sent.

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

Internally FastAPI keeps two exit stacks per request — one for request scope and one for function scope — and pushes each generator dependency onto the matching one.

Rule: a `yield` dependency with request scope **cannot** depend on a sub-dependency with `scope="function"` (the sub-dependency would be torn down before its parent). FastAPI raises `DependencyScopeError` at route setup, e.g. *`The dependency "get_session" has a scope of "request", it cannot depend on dependencies with scope "function".`*

## How exit-code timing evolved (troubleshooting older apps)

You only need this if you upgrade an older app and see surprising behavior in `yield` dependencies.

- **< 0.106.0**: exit code ran after the response *and* background tasks, so background tasks could reuse yielded objects (e.g. a DB session), but exceptions raised after `yield` could not reach exception handlers.
- **0.106.0**: exit code moved before sending the response, so resources were not held while the response traveled. Background tasks should create their own resources (e.g. open a new DB session and pass an object **ID**, not the ORM object).
- **0.110.0**: if you catch an exception with `except` in a `yield` dependency and don't re-raise, it is no longer automatically forwarded to handlers — consistent with plain Python. Re-raise (`raise`) to keep it propagating.
- **0.118.0**: exit code again runs **after the response is sent**, so a `StreamingResponse` can keep using a yielded DB session while streaming.
- **0.121.0**: `Depends(scope="function")` added to opt into early exit.

### Releasing a resource early by hand

With the default request scope, a session yielded by `get_session` stays open until a slow `StreamingResponse` finishes, even if only an auth dependency used it (`docs_src/dependencies/tutorial013_an_py310.py`). If that matters, close it explicitly when you're done (`tutorial014_an_py310.py`):

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

## Related

- [Testing Dependencies](../testing/testing-dependencies-events-websockets.md) — `app.dependency_overrides`
- [Background Tasks](../integrations/background-tasks.md)
- [How FastAPI Handles a Request](../internals/request-handling-internals.md)
