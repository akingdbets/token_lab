---
type: guide
title: Dependencies with yield
description: Write setup/teardown dependencies with yield (DB sessions, connections), handle and re-raise exceptions correctly, understand execution order and the request vs function scope, and use context managers inside dependencies.
tags: [dependencies, yield, teardown, try-finally, exceptions, scope, context-manager, database-session]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-2fce150728e9b45e011871c5
    resource: repo://docs_src/dependencies/tutorial008_an_py310.py
  - id: openwiki-source-240339e7b0151f923e2246b7
    resource: repo://docs_src/dependencies/tutorial008b_an_py310.py
  - id: openwiki-source-221404f7d01ae1c3a9c584b4
    resource: repo://docs_src/dependencies/tutorial008c_an_py310.py
  - id: openwiki-source-feee32007905d941c3802b8d
    resource: repo://docs_src/dependencies/tutorial008d_an_py310.py
  - id: openwiki-source-36f6cb15f05a73d08e616361
    resource: repo://docs_src/dependencies/tutorial008e_an_py310.py
  - id: openwiki-source-58ad6d145b38237fde3ce130
    resource: repo://docs_src/dependencies/tutorial010_py310.py
  - id: openwiki-source-27a19fc781701e100cf69310
    resource: repo://docs/en/docs/tutorial/dependencies/dependencies-with-yield.md
  - id: openwiki-source-46771283dce4d38560c5dc75
    resource: repo://fastapi/concurrency.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Dependencies with yield

A dependency can `yield` a value instead of returning it. Code **before** `yield` runs before your path operation; code **after** `yield` runs later as cleanup. This is the standard way to provide a database session, a connection or any resource that must be closed.

FastAPI turns such generator functions into context managers internally (`asynccontextmanager` for `async def`, `contextmanager` run in a threadpool for `def`), so both `async def` and plain `def` generator dependencies work.

**Use `yield` exactly once** per dependency.

## Basic example

`docs_src/dependencies/tutorial007_py310.py`:

```python
async def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()
```

- `db = DBSession()` runs before the request is handled.
- The yielded `db` is injected into the path operation (or another dependency).
- `finally` guarantees `db.close()` runs even if an exception happened.

A real SQLModel version is in [SQL Databases](../integrations/sql-databases.md):

```python
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]
```

## Sub-dependencies with yield

Any number of `yield` dependencies can depend on each other. FastAPI makes sure each one's exit code runs in the right (reverse) order, so a dependency can still use its sub-dependencies during cleanup (`docs_src/dependencies/tutorial008_an_py310.py`):

```python
async def dependency_a():
    dep_a = generate_dep_a()
    try:
        yield dep_a
    finally:
        dep_a.close()


async def dependency_b(dep_a: Annotated[DepA, Depends(dependency_a)]):
    dep_b = generate_dep_b()
    try:
        yield dep_b
    finally:
        dep_b.close(dep_a)


async def dependency_c(dep_b: Annotated[DepB, Depends(dependency_b)]):
    dep_c = generate_dep_c()
    try:
        yield dep_c
    finally:
        dep_c.close(dep_b)
```

Setup: a → b → c. Teardown: c → b → a. You can mix `yield` and `return` dependencies freely.

## Exceptions and yield

Exceptions raised in the path operation (or later dependencies) are thrown **into** the generator at the `yield` point, so you can catch them with `try/except`.

### Converting an exception into an HTTP error

`docs_src/dependencies/tutorial008b_an_py310.py`:

```python
class OwnerError(Exception):
    pass


def get_username():
    try:
        yield "Rick"
    except OwnerError as e:
        raise HTTPException(status_code=400, detail=f"Owner error: {e}")


@app.get("/items/{item_id}")
def get_item(item_id: str, username: Annotated[str, Depends(get_username)]):
    if item_id not in data:
        raise HTTPException(status_code=404, detail="Item not found")
    item = data[item_id]
    if item["owner"] != username:
        raise OwnerError(username)
    return item
```

You can also raise `HTTPException` in the exit code. Alternatively, register a [custom exception handler](../errors/handling-errors.md).

### Always re-raise what you catch

If you catch an exception and **don't** raise anything, FastAPI can't see it — like any Python code that swallows an exception (`tutorial008c_an_py310.py`):

```python
def get_username():
    try:
        yield "Rick"
    except InternalError:
        print("Oops, we didn't raise again, Britney 😱")
```

The client still gets a `500 Internal Server Error`, but the server logs **nothing** about the real error. Re-raise with a bare `raise` (`tutorial008d_an_py310.py`):

```python
def get_username():
    try:
        yield "Rick"
    except InternalError:
        print("We don't swallow the internal error here, we raise again 😎")
        raise
```

Now the 500 is accompanied by the `InternalError` traceback in the logs. The same applies to `HTTPException`s raised in the path operation: they pass through your `except` too, so re-raise them (or catch only specific exception types).

## Execution order

1. Dependencies run their code up to `yield`.
2. The path operation runs.
3. The response is produced (by your return value, or by an exception handler for a raised exception).
4. Depending on `scope`, exit code runs before or after sending the response.

Only **one** response is ever sent. Once it has been sent you cannot change it — raising an `HTTPException` in exit code that runs after the response (request scope) can't alter what the client received.

## Early exit with `scope`

`Depends()` accepts `scope`:

- `"request"` (default for `yield` dependencies): setup before the path operation, teardown **after the response is sent**. This means a `StreamingResponse` can keep using the resource while streaming.
- `"function"`: teardown right after the path operation function returns, **before** the response is sent.

`docs_src/dependencies/tutorial008e_an_py310.py`:

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

Sub-dependency rule: a `"request"`-scoped dependency may only depend on `"request"`-scoped dependencies; a `"function"`-scoped dependency may depend on both. Violating it raises `DependencyScopeError` when the route is created. History and edge cases are in [Advanced Dependencies](advanced-dependencies.md).

## Using context managers

Any context manager can be used inside a `yield` dependency with `with` / `async with` (`docs_src/dependencies/tutorial010_py310.py`):

```python
class MySuperContextManager:
    def __init__(self):
        self.db = DBSession()

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.close()


async def get_db():
    with MySuperContextManager() as db:
        yield db
```

Don't decorate the dependency itself with `@contextlib.contextmanager` / `@asynccontextmanager` — FastAPI already does that internally.

## Background tasks

Background tasks run after the response is sent. Don't rely on a yielded resource (e.g. a DB session) inside a background task; create a fresh resource in the task and pass IDs instead of ORM objects. See [Background Tasks](../integrations/background-tasks.md).

## Related

- [Dependency Injection Basics](dependency-injection-basics.md)
- [Handling Errors](../errors/handling-errors.md)
- [Lifespan Events](../app-structure/lifespan-events.md) — for app-wide (not per-request) resources
