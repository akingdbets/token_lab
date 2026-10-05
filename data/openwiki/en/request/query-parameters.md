---
type: guide
title: Query Parameters, String Validation and Query Models
description: Declare query parameters with defaults, optional and required values, bool conversion; add Query() validation and metadata (min_length, max_length, pattern, alias, title, description, deprecated, include_in_schema); accept lists; run custom AfterValidator checks; and group parameters in Pydantic query models.
tags: [query-parameters, query, validation, min_length, pattern, alias, aftervalidator, query-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-c3463ac642282d1295429819
    resource: repo://docs_src/query_param_models/tutorial001_an_py310.py
  - id: openwiki-source-f9fab8c4c0cd9a48fc290d64
    resource: repo://docs_src/query_param_models/tutorial002_an_py310.py
  - id: openwiki-source-bfecd207b62fd1add418af15
    resource: repo://docs_src/query_params_str_validations/tutorial004_an_py310.py
  - id: openwiki-source-4c543e970630d93ac9d2bc3c
    resource: repo://docs_src/query_params_str_validations/tutorial010_an_py310.py
  - id: openwiki-source-82bd0c2cd2f545b07ca9b4a9
    resource: repo://docs_src/query_params_str_validations/tutorial011_an_py310.py
  - id: openwiki-source-5a46921e30adc93528f07e41
    resource: repo://docs_src/query_params_str_validations/tutorial012_an_py310.py
  - id: openwiki-source-8d52852e029948a6134be659
    resource: repo://docs_src/query_params_str_validations/tutorial014_an_py310.py
  - id: openwiki-source-9002331d6a69fc47a47e97a1
    resource: repo://docs_src/query_params_str_validations/tutorial015_an_py310.py
  - id: openwiki-source-374e6010bbc0a7d7ac10f0c2
    resource: repo://docs_src/query_params/tutorial001_py310.py
  - id: openwiki-source-a953d8b52b06de4ee9a15262
    resource: repo://docs_src/query_params/tutorial003_py310.py
  - id: openwiki-source-dcf5db78241bb394f47b0e8a
    resource: repo://docs_src/query_params/tutorial006_py310.py
  - id: openwiki-source-7942b45ca7312e2116551132
    resource: repo://docs/en/docs/tutorial/query-param-models.md
  - id: openwiki-source-b32b25e66b7af40f3eae0f8b
    resource: repo://docs/en/docs/tutorial/query-params.md
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Query Parameters, String Validation and Query Models

## Basics

Function parameters that aren't path parameters (and aren't Pydantic models or special types) are **query parameters** — the `?key=value&...` part of the URL (`docs_src/query_params/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


@app.get("/items/")
async def read_item(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]
```

`/items/?skip=20` → `skip=20, limit=10`. Values arrive as strings and are converted and validated according to the type.

### Optional, required and defaults

The **default value** decides whether a query parameter is required:

```python
@app.get("/items/{item_id}")
async def read_user_item(
    item_id: str, needy: str, skip: int = 0, limit: int | None = None
):
    item = {"item_id": item_id, "needy": needy, "skip": skip, "limit": limit}
    return item
```

(`tutorial006_py310.py`.)

- `needy: str` — **required** (no default); omitting it gives a 422 `missing` error.
- `skip: int = 0` — optional with a default.
- `limit: int | None = None` — optional; `None` if absent.

FastAPI tells path and query parameters apart by name: names in the path template are path parameters, the rest are query parameters, in any order.

### `bool` conversion

```python
async def read_item(item_id: str, q: str | None = None, short: bool = False):
```

(`tutorial003_py310.py`.) `short=1`, `short=True`, `short=true`, `short=on` and `short=yes` all become `True`; `0`, `false`, `off`, `no` become `False`.

## `Query()`: validation and metadata

Add constraints with `Query` inside `Annotated` (`docs_src/query_params_str_validations/tutorial002_an_py310.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/items/")
async def read_items(q: Annotated[str | None, Query(max_length=50)] = None):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results
```

`Annotated` support was added in FastAPI 0.95.0 and is the recommended style. In the older style, `q: str | None = Query(default=None, max_length=50)`, the default goes inside `Query`; with `Annotated` the default is the normal Python default, the function remains callable normally, and you can't accidentally set two defaults.

### String constraints

```python
q: Annotated[
    str | None, Query(min_length=3, max_length=50, pattern="^fixedquery$")
] = None
```

(`tutorial004_an_py310.py`.) `pattern` is a regular expression; the older `regex=` parameter is deprecated in favor of `pattern`. Numeric constraints `gt`, `ge`, `lt`, `le` are also available (see [Path Parameters](path-parameters.md)).

### Required with validation

- A default makes it optional: `q: Annotated[str, Query(min_length=3)] = "fixedquery"` (`tutorial005`).
- No default makes it required: `q: Annotated[str, Query(min_length=3)]` (`tutorial006`).
- Required but may be `None`: `q: Annotated[str | None, Query(min_length=3)]` — the client must send it, though `None` is a valid value (`tutorial006c`).

### Lists (multiple values)

Declare a list type with `Query()` explicitly — otherwise a `list` would be interpreted as a request body (`tutorial011_an_py310.py`):

```python
@app.get("/items/")
async def read_items(q: Annotated[list[str] | None, Query()] = None):
    query_items = {"q": q}
    return query_items
```

`/items/?q=foo&q=bar` → `{"q": ["foo", "bar"]}`. With a default list: `q: Annotated[list[str], Query()] = ["foo", "bar"]` (`tutorial012`). A bare `list` works but items aren't type-checked (`tutorial013`).

### Metadata, aliases and deprecation

```python
@app.get("/items/")
async def read_items(
    q: Annotated[
        str | None,
        Query(
            alias="item-query",
            title="Query string",
            description="Query string for the items to search in the database that have a good match",
            min_length=3,
            max_length=50,
            pattern="^fixedquery$",
            deprecated=True,
        ),
    ] = None,
):
    ...
```

(`tutorial010_an_py310.py`.)

- `alias="item-query"` — the URL uses `?item-query=...` (not a valid Python name) while your variable is `q` (`tutorial009`).
- `title`, `description` — documentation.
- `deprecated=True` — still works, but marked deprecated in the docs.

### Hiding a parameter from OpenAPI

```python
hidden_query: Annotated[str | None, Query(include_in_schema=False)] = None
```

(`tutorial014_an_py310.py`.) The parameter still works; it's just not documented.

## Custom validation with `AfterValidator`

For checks the built-in parameters can't express, use Pydantic's `AfterValidator` in `Annotated`; it runs after normal type validation (`tutorial015_an_py310.py`):

```python
import random
from typing import Annotated

from fastapi import FastAPI
from pydantic import AfterValidator

app = FastAPI()

data = {
    "isbn-9781529046137": "The Hitchhiker's Guide to the Galaxy",
    "imdb-tt0371724": "The Hitchhiker's Guide to the Galaxy",
    "isbn-9781439512982": "Isaac Asimov: The Complete Stories, Vol. 2",
}


def check_valid_id(id: str):
    if not id.startswith(("isbn-", "imdb-")):
        raise ValueError('Invalid ID format, it must start with "isbn-" or "imdb-"')
    return id


@app.get("/items/")
async def read_items(
    id: Annotated[str | None, AfterValidator(check_valid_id)] = None,
):
    if id:
        item = data.get(id)
    else:
        id, item = random.choice(list(data.items()))
    return {"id": id, "name": item}
```

Raising `ValueError` produces a normal 422 validation error. Pydantic also offers `BeforeValidator` and others. For checks that need other resources (e.g. a database lookup), use a [dependency](../dependencies/dependency-injection-basics.md) instead.

## Query parameter models

Group related query parameters in a Pydantic model and declare it with `Query()` (`docs_src/query_param_models/tutorial001_an_py310.py`):

```python
from typing import Annotated, Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []


@app.get("/items/")
async def read_items(filter_query: Annotated[FilterParams, Query()]):
    return filter_query
```

Each field is a separate query parameter (`?limit=10&tags=a&tags=b`), validated via the model and documented individually. Reuse the model across endpoints.

Forbid unknown parameters with `model_config = {"extra": "forbid"}` (`tutorial002_an_py310.py`): `?tool=plumbus` then returns a 422 `extra_forbidden` error.

## Related

- [Path Parameters and Numeric Validation](path-parameters.md)
- [Header and Cookie Parameters](headers-and-cookies.md)
- [Request Body](request-body.md)
- [Extra Data Types and Examples](extra-data-types-and-examples.md) — `examples` / `openapi_examples` on `Query`
