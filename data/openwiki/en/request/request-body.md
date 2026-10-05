---
type: guide
title: Request Body, Body Fields and Nested Models
description: Receive JSON request bodies with Pydantic models, combine body, path and query parameters, use multiple body parameters, singular Body() values and Body(embed=True), validate fields with Field(), and build nested models with lists, sets, dicts and special types like HttpUrl.
tags: [request-body, body, pydantic, basemodel, field, embed, nested-models, validation]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-ee462d8bc4f7f301b937e395
    resource: repo://docs_src/body_fields/tutorial001_an_py310.py
  - id: openwiki-source-b88a6665ae3d6d2abadfedb9
    resource: repo://docs_src/body_multiple_params/tutorial002_py310.py
  - id: openwiki-source-ed5f30e5dd915342b67c0d1a
    resource: repo://docs_src/body_multiple_params/tutorial003_an_py310.py
  - id: openwiki-source-edde7209af105d0504353b66
    resource: repo://docs_src/body_multiple_params/tutorial005_an_py310.py
  - id: openwiki-source-7e79b62ecf86fb9fa481c885
    resource: repo://docs_src/body_nested_models/tutorial004_py310.py
  - id: openwiki-source-7d6cda5557db514372ff3101
    resource: repo://docs_src/body_nested_models/tutorial006_py310.py
  - id: openwiki-source-43421045c6ebf2c5687db002
    resource: repo://docs_src/body_nested_models/tutorial007_py310.py
  - id: openwiki-source-041961d82f16e30f23809b5d
    resource: repo://docs_src/body_nested_models/tutorial008_py310.py
  - id: openwiki-source-bf51b965cdd7f0dad647e4d2
    resource: repo://docs_src/body_nested_models/tutorial009_py310.py
  - id: openwiki-source-ca5920e3171f11d1aac4f0b1
    resource: repo://docs_src/body/tutorial001_py310.py
  - id: openwiki-source-3479104b34b02c0a1a358126
    resource: repo://docs_src/body/tutorial004_py310.py
  - id: openwiki-source-294a6d5904466cc19f308930
    resource: repo://docs/en/docs/tutorial/body.md
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Request Body, Body Fields and Nested Models

A **request body** is data the client sends (usually JSON), typically with `POST`, `PUT` or `PATCH`. Declare it with a Pydantic model.

## Basic body

`docs_src/body/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return item
```

The model works like query parameters: fields without defaults are required (`name`, `price`), fields with defaults are optional. Valid input:

```json
{"name": "Foo", "description": "An optional description", "price": 45.2, "tax": 3.5}
```

or just `{"name": "Foo", "price": 45.2}`.

With this declaration FastAPI will:

- read the body as JSON (when the `Content-Type` is `application/json` — see [Strict Content-Type](using-request-directly.md));
- convert types and validate; invalid data → 422 with the exact location of each error (e.g. `["body", "price"]`);
- give you an `Item` instance with editor completion;
- generate JSON Schema for the model in OpenAPI.

Use the model in your function (`tutorial002_py310.py`):

```python
@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.model_dump()
    if item.tax is not None:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict
```

Sending a body with `GET` is undefined in the HTTP spec. FastAPI supports it for extreme cases, but Swagger UI won't document it and proxies may drop it.

## Body + path + query parameters

`tutorial004_py310.py`:

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, q: str | None = None):
    result = {"item_id": item_id, **item.model_dump()}
    if q:
        result.update({"q": q})
    return result
```

How FastAPI classifies parameters:

1. Declared in the **path** → path parameter.
2. **Singular type** (`int`, `float`, `str`, `bool`, …) → query parameter.
3. **Pydantic model** → request body.

## Multiple body parameters

### Optional body

```python
@app.put("/items/{item_id}")
async def update_item(
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)],
    q: str | None = None,
    item: Item | None = None,
):
    ...
```

(`docs_src/body_multiple_params/tutorial001_an_py310.py`.)

### Several models

```python
class User(BaseModel):
    username: str
    full_name: str | None = None


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, user: User):
    results = {"item_id": item_id, "item": item, "user": user}
    return results
```

(`tutorial002_py310.py`.) With more than one body parameter, FastAPI expects a JSON object keyed by **parameter names**:

```json
{
    "item": {"name": "Foo", "description": "The pretender", "price": 42.0, "tax": 3.2},
    "user": {"username": "dave", "full_name": "Dave Grohl"}
}
```

### Singular values in the body: `Body()`

A plain `int` would be a query parameter; use `Body()` to read it from the body (`tutorial003_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(
    item_id: int, item: Item, user: User, importance: Annotated[int, Body()]
):
    ...
```

Body: `{"item": {...}, "user": {...}, "importance": 5}`. `Body` accepts the same validation as `Query`/`Path`, e.g. `Body(gt=0)` (`tutorial004_an_py310.py`). `Body` also has `media_type`, `examples` and `openapi_examples`.

### Embedding a single model: `Body(embed=True)`

By default a **single** model parameter means the body *is* the model. To require a key wrapping it, use `embed=True` (`tutorial005_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Annotated[Item, Body(embed=True)]):
    results = {"item_id": item_id, "item": item}
    return results
```

Expected body: `{"item": {"name": "Foo", "price": 42.0, ...}}` instead of `{"name": "Foo", ...}`.

## Field validation and metadata: `Field()`

Inside models, use Pydantic's `Field` the way you'd use `Query`/`Path`/`Body` for parameters (`docs_src/body_fields/tutorial001_an_py310.py`):

```python
from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str
    description: str | None = Field(
        default=None, title="The description of the item", max_length=300
    )
    price: float = Field(gt=0, description="The price must be greater than zero")
    tax: float | None = None
```

`Field` is imported from `pydantic`, not `fastapi`. It supports `default`, `title`, `description`, `examples`, `alias`, numeric (`gt`, `ge`, `lt`, `le`) and string (`min_length`, `max_length`, `pattern`) constraints; these show up in the JSON Schema. (FastAPI's `Query`, `Path`, `Body` etc. are themselves built on Pydantic's `FieldInfo`.)

## Nested models

### Lists and sets

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []          # tutorial002
    # tags: set[str] = set()      # tutorial003: duplicates removed, uniqueItems in schema
```

### Submodels

```python
class Image(BaseModel):
    url: str
    name: str


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()
    image: Image | None = None
```

(`docs_src/body_nested_models/tutorial004_py310.py`.) Expected JSON nests an `"image": {"url": ..., "name": ...}` object; validation, conversion and docs work at every level.

### Special types and lists of submodels

Use Pydantic types like `HttpUrl` for validated strings (`tutorial005`), and lists of models (`tutorial006`):

```python
from pydantic import BaseModel, HttpUrl


class Image(BaseModel):
    url: HttpUrl
    name: str


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()
    images: list[Image] | None = None
```

Deep nesting (`tutorial007_py310.py`):

```python
class Offer(BaseModel):
    name: str
    description: str | None = None
    price: float
    items: list[Item]


@app.post("/offers/")
async def create_offer(offer: Offer):
    return offer
```

### Bodies that are lists or dicts

A top-level JSON array (`tutorial008_py310.py`):

```python
@app.post("/images/multiple/")
async def create_multiple_images(images: list[Image]):
    return images
```

A dict with arbitrary keys (`tutorial009_py310.py`):

```python
@app.post("/index-weights/")
async def create_index_weights(weights: dict[int, float]):
    return weights
```

JSON object keys are always strings; Pydantic converts them to `int` here and validates the values as `float`.

## Related

- [Response Models and Return Types](../models/response-model.md)
- [Extra Models and Body Updates](../models/extra-models-and-updates.md) — input/output models, PATCH
- [Extra Data Types and Examples](extra-data-types-and-examples.md) — `datetime`, `UUID`, examples
- [Forms and File Uploads](forms-and-files.md) — non-JSON bodies
