---
type: concept
title: Python Types and async/await
description: The Python type hints FastAPI relies on (str | None, list/dict generics, classes, Pydantic models, Annotated) and when to declare path operations and dependencies with async def versus def, including how def functions run in a threadpool.
tags: [python-types, type-hints, annotated, pydantic, async, await, concurrency, threadpool]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-fd7b2ae6eaa9dc0952e51e70
    resource: repo://docs_src/python_types/tutorial011_py310.py
  - id: openwiki-source-1deb722f21a51dbcd993b0eb
    resource: repo://docs_src/python_types/tutorial013_py310.py
  - id: openwiki-source-f0c19533402c6bf5c789f498
    resource: repo://docs/en/docs/advanced/advanced-python-types.md
  - id: openwiki-source-83099dea33ef3297e6faa1ec
    resource: repo://docs/en/docs/async.md
  - id: openwiki-source-14deaaf4cdf18f4e43256a4c
    resource: repo://docs/en/docs/python-types.md
  - id: openwiki-source-46771283dce4d38560c5dc75
    resource: repo://fastapi/concurrency.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Python Types and async/await

FastAPI is driven by standard Python type hints, and it supports both `async def` and plain `def` functions. Understanding both makes the rest of the framework predictable.

## Type hints

Type hints are optional annotations that editors and tools understand. FastAPI additionally uses them at runtime to **convert**, **validate** and **document** data.

```python
def get_full_name(first_name: str, last_name: str):
    full_name = first_name.title() + " " + last_name.title()
    return full_name
```

### Simple and generic types

- Simple: `str`, `int`, `float`, `bool`, `bytes`.
- Generic containers with inner types:
  - `list[str]` — a list of strings
  - `tuple[int, int, str]`, `set[bytes]`
  - `dict[str, float]` — keys `str`, values `float`
- Unions: `int | str`.
- Possibly `None`: `str | None`.

`docs_src/python_types/tutorial009_py310.py`:

```python
def say_hi(name: str | None = None):
    if name is not None:
        print(f"Hey {name}!")
    else:
        print("Hello World")
```

Where `|` can't be used (e.g. some non-annotation contexts), use `typing.Union[str, None]`. The docs suggest preferring `Union[X, None]` over `Optional[X]`, because a parameter typed `Optional[str]` **without a default is still required** — it merely accepts `None`. In FastAPI, a parameter is optional because of its **default value** (`= None`), not because of its type.

### Classes as types

```python
class Person:
    def __init__(self, name: str):
        self.name = name


def get_person_name(one_person: Person):
    return one_person.name
```

### Pydantic models

Pydantic classes declare data shapes with types; creating an instance validates and converts input (`tutorial011_py310.py`):

```python
from datetime import datetime

from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str = "John Doe"
    signup_ts: datetime | None = None
    friends: list[int] = []


external_data = {
    "id": "123",
    "signup_ts": "2017-06-01 12:22",
    "friends": [1, "2", b"3"],
}
user = User(**external_data)
print(user)
# > User id=123 name='John Doe' signup_ts=datetime.datetime(2017, 6, 1, 12, 22) friends=[1, 2, 3]
```

FastAPI uses Pydantic (v2) for all request and response data. See [Request Body](../request/request-body.md).

### `Annotated`: types with metadata

`typing.Annotated[T, ...]` attaches extra metadata to a type without changing it (`tutorial013_py310.py`):

```python
from typing import Annotated


def say_hello(name: Annotated[str, "this is just metadata"]) -> str:
    return f"Hello {name}"
```

Python ignores the metadata; FastAPI reads it. This is how you declare parameter sources, validation and dependencies:

```python
from typing import Annotated
from fastapi import Depends, Query

async def read_items(
    q: Annotated[str | None, Query(max_length=50)] = None,
    commons: Annotated[dict, Depends(common_parameters)] = ...,
): ...
```

`Annotated` is the recommended style throughout the docs.

### What FastAPI does with types

With one declaration you get: editor completion and type checks; conversion of incoming strings/JSON to Python types; validation with automatic 422 errors; conversion of outputs to JSON; and OpenAPI documentation.

## `async def` vs `def`

### Quick rules

- Library tells you to `await` it (e.g. an async DB driver, `httpx.AsyncClient`) → `async def` and `await`:

  ```python
  @app.get("/")
  async def read_results():
      results = await some_library()
      return results
  ```

- Library is blocking and doesn't support `await` (many DB libraries, file I/O, `requests`) → plain `def`:

  ```python
  @app.get("/")
  def results():
      results = some_library()
      return results
  ```

- Function doesn't wait on anything (pure computation that's quick) → `async def`.
- Not sure → plain `def`.

You can mix both freely across path operations and dependencies.

### Why it matters (what FastAPI does)

- `async def` path operations are **awaited directly on the event loop**. Calling a blocking function inside one blocks the whole server process for that time — avoid blocking I/O there.
- Plain `def` path operations are run in an **external threadpool** and awaited (`run_in_threadpool` in `run_endpoint_function`, `fastapi/routing.py`), so blocking calls don't freeze the event loop.
- The same applies to **dependencies** and sub-dependencies: `def` dependencies run in the threadpool, `async def` ones are awaited, and `def` generator (`yield`) dependencies run their enter/exit in threads.
- Your **own utility functions** are not affected: FastAPI only decides how to call functions *it* calls (path operations and dependencies). Call your helpers normally, or `await` them if they are `async def`.

Note: for trivial compute-only endpoints, `async def` is slightly faster than `def` in FastAPI (no thread hop) — the opposite of some other frameworks.

`fastapi.concurrency` re-exports Starlette's `run_in_threadpool`, `iterate_in_threadpool` and `run_until_first_complete`, which you can use to call blocking code from your own `async` code:

```python
from fastapi.concurrency import run_in_threadpool

result = await run_in_threadpool(blocking_function, arg1, arg2)
```

### Concurrency vs parallelism

`async` gives **concurrency**: while one request waits for I/O (network, DB, disk), the server works on others. That's ideal for web APIs, which spend most of their time waiting. CPU-bound work (e.g. ML inference) benefits from **parallelism** — multiple processes/workers (see [Deployment Concepts](../deployment/deployment-concepts-and-servers.md)) or a task queue.

## Related

- [First Steps](first-steps.md)
- [How FastAPI Handles a Request](../internals/request-handling-internals.md)
- [Dataclasses, Separate OpenAPI Schemas and Pydantic v1 to v2](../models/dataclasses-and-pydantic-versions.md)
