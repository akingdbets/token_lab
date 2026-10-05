---
type: guide
title: Response Models and Return Types
description: Declare the response shape with a return type annotation or response_model to validate, filter, document and serialize output; priority rules, returning Response objects, response_model=None, and the response_model_exclude_unset / include / exclude options.
tags: [response-model, return-type, pydantic, filtering, serialization, response_model_exclude_unset, openapi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-9a62f7950d7a9b9ac95d2fa4
    resource: repo://docs_src/response_model/tutorial003_01_py310.py
  - id: openwiki-source-41ea77b7453e52dc9a990df8
    resource: repo://docs_src/response_model/tutorial003_05_py310.py
  - id: openwiki-source-bd6ac53b99ab082ca19d305a
    resource: repo://docs_src/response_model/tutorial003_py310.py
  - id: openwiki-source-f40a322e7e096e6207d3367b
    resource: repo://docs_src/response_model/tutorial004_py310.py
  - id: openwiki-source-246dc932abfd82985b764c70
    resource: repo://docs_src/response_model/tutorial005_py310.py
  - id: openwiki-source-1815f7028972fe19690e83a7
    resource: repo://docs/en/docs/tutorial/response-model.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Response Models and Return Types

Declaring the **response type** of a path operation makes FastAPI:

- **validate** the returned data — if your code returns something invalid (e.g. a missing field), that's a bug in your app, and FastAPI responds with a server error instead of sending wrong data;
- **filter** the output to the declared fields (crucial for security, e.g. hiding passwords);
- **document** the response with JSON Schema in OpenAPI (and thus in generated clients);
- **serialize** efficiently — with a response type and the default response class, Pydantic serializes directly to JSON bytes (see [internals](../internals/request-handling-internals.md)).

## Return type annotations

`docs_src/response_model/tutorial001_01_py310.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/")
async def read_items() -> list[Item]:
    return [
        Item(name="Portal Gun", price=42.0),
        Item(name="Plumbus", price=32.0),
    ]
```

Any type valid for Pydantic fields works: models, `list[...]`, `dict[...]`, scalars, unions.

## The `response_model` parameter

When you return something that isn't literally the declared type — a dict, or a database object — the annotation would upset your editor/type checker. Use the decorator parameter `response_model` instead (`tutorial001_py310.py`):

```python
from typing import Any


@app.post("/items/", response_model=Item)
async def create_item(item: Item) -> Any:
    return item


@app.get("/items/", response_model=list[Item])
async def read_items() -> Any:
    return [
        {"name": "Portal Gun", "price": 42.0},
        {"name": "Plumbus", "price": 32.0},
    ]
```

`response_model` is a parameter of the decorator (`@app.get()`, `@app.post()`, …), not of your function.

**Priority:** if both are present, `response_model` wins. FastAPI only derives the response model from the return annotation when `response_model` isn't passed at all.

## Filtering output

Never echo sensitive input back (`tutorial002_py310.py` returns `UserIn` with the password — "Don't do this in production!"). Declare an output model (`tutorial003_py310.py`):

```python
class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


@app.post("/user/", response_model=UserOut)
async def create_user(user: UserIn) -> Any:
    return user
```

The returned `UserIn` is converted to `UserOut`; `password` is dropped.

### Filtering with inheritance and a return type

To keep a precise return annotation **and** filtering, make the input model a subclass of the output model (`tutorial003_01_py310.py`):

```python
class BaseUser(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserIn(BaseUser):
    password: str


@app.post("/user/")
async def create_user(user: UserIn) -> BaseUser:
    return user
```

Type checkers accept it (a `UserIn` *is a* `BaseUser`), and FastAPI still serializes only `BaseUser`'s fields. More patterns in [Extra Models](extra-models-and-updates.md).

## Returning `Response` objects

If the return annotation is `Response` or a subclass, FastAPI does **not** create a response model (`lenient_issubclass(return_annotation, Response)` → `response_model = None`):

```python
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse


@app.get("/portal")
async def get_portal(teleport: bool = False) -> Response:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return JSONResponse(content={"message": "Here's your interdimensional portal."})


@app.get("/teleport")
async def get_teleport() -> RedirectResponse:
    return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

Any returned `Response` instance is sent as-is, without validation or filtering. See [Custom Responses](../responses/custom-responses.md).

### Invalid annotations and `response_model=None`

An annotation that is neither a valid Pydantic type nor a plain `Response` class — e.g. `Response | dict` (`tutorial003_04_py310.py`) or an ORM class — makes FastAPI fail when creating the route, because it tries to build a Pydantic model from it. Keep the annotation for your tools and disable the response model (`tutorial003_05_py310.py`):

```python
@app.get("/portal", response_model=None)
async def get_portal(teleport: bool = False) -> Response | dict:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return {"message": "Here's your interdimensional portal."}
```

Without a response model, return values are converted with `jsonable_encoder`.

Generator endpoints are special: for streaming (JSON Lines / SSE) the **item** type is taken from annotations like `AsyncIterable[Item]` — see [Streaming](../responses/streaming-and-sse.md).

## Response model encoding options

`tutorial004_py310.py`:

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float = 10.5
    tags: list[str] = []


@app.get("/items/{item_id}", response_model=Item, response_model_exclude_unset=True)
async def read_item(item_id: str):
    return items[item_id]
```

With `response_model_exclude_unset=True`, fields not explicitly set keep out of the JSON. For `"foo": {"name": "Foo", "price": 50.2}` the response is `{"name": "Foo", "price": 50.2}` — no default `description`, `tax` or `tags`. Values explicitly set, even if equal to the default (like `baz`'s `"tax": 10.5`), are included.

Related options (all decorator parameters, applied via Pydantic serialization):

| Option | Effect |
|--------|--------|
| `response_model_exclude_unset` | Omit fields not explicitly set |
| `response_model_exclude_defaults` | Omit fields equal to their default |
| `response_model_exclude_none` | Omit fields whose value is `None` |
| `response_model_include` | Only these fields (set of names) |
| `response_model_exclude` | Drop these fields |
| `response_model_by_alias` | Use field aliases in output (default `True`) |

`response_model_include` / `response_model_exclude` (`tutorial005_py310.py`):

```python
@app.get(
    "/items/{item_id}/name",
    response_model=Item,
    response_model_include={"name", "description"},
)
async def read_item_name(item_id: str):
    return items[item_id]


@app.get("/items/{item_id}/public", response_model=Item, response_model_exclude={"tax"})
async def read_item_public_data(item_id: str):
    return items[item_id]
```

Lists or tuples are accepted too and converted to sets (`tutorial006_py310.py`). Prefer separate models over include/exclude: with include/exclude, the OpenAPI schema still shows the **full** model, while separate classes document exactly what is returned.

## Related

- [Response Status Codes](../responses/status-codes.md)
- [Dataclasses and Pydantic versions](dataclasses-and-pydantic-versions.md) — separate input/output schemas
- [Handling Errors](../errors/handling-errors.md) — `ResponseValidationError`
