---
type: guide
title: Path Parameters and Numeric Validation
description: Declare path parameters with Python types for conversion and validation, order fixed routes before parameterized ones, restrict values with Enum, capture paths with :path, and add Path() metadata and numeric constraints (gt, ge, lt, le).
tags: [path-parameters, path, validation, enum, numeric-validation, routing]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-9718dff1ebb27c0b1bf1abf9
    resource: repo://docs_src/path_params_numeric_validations/tutorial004_an_py310.py
  - id: openwiki-source-d5ea2075b94825343c04edc8
    resource: repo://docs_src/path_params_numeric_validations/tutorial005_an_py310.py
  - id: openwiki-source-0fd032858ed69844c1398749
    resource: repo://docs_src/path_params_numeric_validations/tutorial006_an_py310.py
  - id: openwiki-source-38df07681a8fcbdb034904e9
    resource: repo://docs_src/path_params/tutorial002_py310.py
  - id: openwiki-source-3b9406805096315081c49590
    resource: repo://docs_src/path_params/tutorial003_py310.py
  - id: openwiki-source-cd9fb2b4addace155974917d
    resource: repo://docs_src/path_params/tutorial003b_py310.py
  - id: openwiki-source-84c4dbdfc11b1dfd298b8383
    resource: repo://docs_src/path_params/tutorial004_py310.py
  - id: openwiki-source-e891265db7ef0a76fe70d4f4
    resource: repo://docs_src/path_params/tutorial005_py310.py
  - id: openwiki-source-6a09064320fc387f97ffc738
    resource: repo://docs/en/docs/tutorial/path-params.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-4ba318fa02e49c0255b400c4
    resource: repo://fastapi/param_functions.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Path Parameters and Numeric Validation

## Declaring path parameters

Use Python format-string syntax in the path; the value is passed to the function argument of the same name (`docs_src/path_params/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}
```

`GET /items/foo` → `{"item_id": "foo"}`.

## Types: conversion and validation

Add a type annotation (`tutorial002_py310.py`):

```python
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

- `GET /items/3` → `{"item_id": 3}` — the string `"3"` is **converted** to the `int` `3`.
- `GET /items/foo` (or `/items/4.2`) → **422** error with type `int_parsing`, a `loc` of `["path", "item_id"]` and a readable message.
- The type is documented in OpenAPI and the docs UI.

All this is done by Pydantic; any Pydantic type works (`str`, `float`, `bool`, `UUID`, …).

## Route order matters

Path operations are matched **in declaration order**. Put fixed paths before parameterized ones (`tutorial003_py310.py`):

```python
@app.get("/users/me")
async def read_user_me():
    return {"user_id": "the current user"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}
```

Otherwise `/users/me` would match `/users/{user_id}` with `user_id="me"`. Likewise, if you redefine the same path and method (`tutorial003b_py310.py`), only the first definition is used.

## Predefined values with `Enum`

Subclass both `str` and `Enum` to restrict a path parameter to known values (`tutorial005_py310.py`):

```python
from enum import Enum

from fastapi import FastAPI


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


app = FastAPI()


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}

    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}

    return {"model_name": model_name, "message": "Have some residuals"}
```

- Inheriting from `str` makes the docs show the values as strings.
- The docs UI shows a dropdown with the allowed values; other values get a 422.
- Compare with enum members (`is ModelName.alexnet`) or use `.value`; returning an enum member serializes to its value.

## Paths inside path parameters

To capture a value containing slashes (e.g. a file path), use Starlette's `:path` converter (`tutorial004_py310.py`):

```python
@app.get("/files/{file_path:path}")
async def read_file(file_path: str):
    return {"file_path": file_path}
```

`/files/home/johndoe/myfile.txt` → `file_path="home/johndoe/myfile.txt"`. For a value starting with `/`, the URL has a double slash: `/files//home/johndoe/myfile.txt`. OpenAPI has no notion of path-containing parameters, so the docs won't hint at it, but it works.

## `Path()`: metadata and numeric validation

Use `Path` with `Annotated` to add metadata and constraints (`docs_src/path_params_numeric_validations/tutorial001_an_py310.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI()


@app.get("/items/{item_id}")
async def read_items(
    item_id: Annotated[int, Path(title="The ID of the item to get")],
    q: Annotated[str | None, Query(alias="item-query")] = None,
):
    results = {"item_id": item_id}
    if q:
        results.update({"q": q})
    return results
```

**A path parameter is always required**, because it's part of the path. `Path` asserts that you don't give it a default (`"Path parameters cannot have a default value"`), and FastAPI refuses a default for a path parameter too.

### Numeric constraints

| Parameter | Meaning |
|-----------|---------|
| `gt` | greater than |
| `ge` | greater than or equal |
| `lt` | less than |
| `le` | less than or equal |

```python
# ge=1 (tutorial004)
item_id: Annotated[int, Path(title="The ID of the item to get", ge=1)]

# gt=0, le=1000 (tutorial005)
item_id: Annotated[int, Path(title="The ID of the item to get", gt=0, le=1000)]
```

They work for `float` too (`tutorial006_an_py310.py`):

```python
@app.get("/items/{item_id}")
async def read_items(
    *,
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)],
    q: str,
    size: Annotated[float, Query(gt=0, lt=10.5)],
):
    ...
```

The same constraints exist on `Query`, `Header`, `Cookie`, `Body` and Pydantic's `Field`. Other `Path` parameters: `title`, `description`, `examples`, `openapi_examples`, `deprecated`, `include_in_schema`, plus string constraints (`min_length`, `max_length`, `pattern`).

### Parameter ordering

FastAPI identifies parameters by **name, type and default**, not by position, so order them however you like. With `Annotated`, required parameters without defaults can come after ones with defaults without upsetting Python. In the older default-value style (`item_id: int = Path(...)`), Python forbids non-default arguments after default ones; the docs' trick is to start the signature with `*` so all parameters become keyword-only (see `tutorial006`). `Annotated` avoids the issue entirely.

`Path`, `Query` and friends imported from `fastapi` are functions returning instances of the classes in `fastapi.params` (`fastapi/param_functions.py`), typed so editors don't complain.

## Related

- [Query Parameters, String Validation and Query Models](query-parameters.md)
- [Request Body](request-body.md)
- [Bigger Applications](../app-structure/bigger-applications.md) — route ordering across routers
