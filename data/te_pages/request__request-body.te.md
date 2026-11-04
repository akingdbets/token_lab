---
Type: guide
title: Request Body, Body Fields and Nested Models
description: Receive JSON request bodies with pydantic models, combine body, Path and Query parameters, use multiple body parameters, singular Body() values and Body(embed=True), validate fields with Field(), and build nested models with lists, sets, dicts and special types like HttpUrl.
tags: [request-body, body, pydantic, basemodel, Field, embed, nested-models, validation]
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

H1: Request Body, Body Fields and Nested Models

REQUEST BODY=DATA CLIENT SENDS (USUALLY JSON), TYPICALLY WITH `POST`, `PUT` OR `PATCH`. DECLARE USING pydantic MODEL.

H2: Basic body

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

MODEL WORKS LIKE Query PARAMETERS: FIELDS WITHOUT DEFAULTS REQUIRED (`name`, `price`); FIELDS WITH DEFAULTS OPTIONAL. VALID INPUT:

```json
{"name": "Foo", "description": "An optional description", "price": 45.2, "tax": 3.5}
```

OR JUST `{"name": "Foo", "price": 45.2}`.

WITH THIS DECLARATION, FASTAPI:
- READS BODY AS JSON WHEN `Content-Type` IS `application/json` — SEE [STRICT Content-Type](using-request-directly.md);
- CONVERTS TYPES AND VALIDATES; INVALID DATA → 422 WITH EXACT ERROR LOCATION (e.g. `["body", "price"]`);
- GIVES YOU `Item` INSTANCE WITH EDITOR COMPLETION;
- GENERATES JSON SCHEMA FOR MODEL IN OpenAPI.

USE MODEL IN FUNCTION (`tutorial002_py310.py`):

```python
@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.model_dump()
    if item.tax is not None:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict
```

SENDING BODY WITH `GET` UNDEFINED IN HTTP SPEC. FASTAPI SUPPORTS IT FOR EXTREME CASES, BUT SWAGGER UI WON'T DOCUMENT IT AND PROXIES MAY DROP IT.

H2: Body + Path + Query parameters

`tutorial004_py310.py`:

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, q: str | None = None):
    result = {"item_id": item_id, **item.model_dump()}
    if q:
        result.update({"q": q})
    return result
```

FASTAPI CLASSIFIES PARAMETERS:
1. DECLARED IN Path → Path PARAMETER.
2. SINGULAR Type (`int`, `float`, `str`, `bool`, …) → Query PARAMETER.
3. pydantic MODEL → REQUEST BODY.

H2: Multiple body parameters

H3: Optional body

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

H3: Several models

```python
class User(BaseModel):
    username: str
    full_name: str | None = None


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, user: User):
    results = {"item_id": item_id, "item": item, "user": user}
    return results
```

(`tutorial002_py310.py`.) WITH >1 BODY PARAMETER, FASTAPI EXPECTS JSON OBJECT KEYED BY PARAMETER NAMES:

```json
{
    "item": {"name": "Foo", "description": "The pretender", "price": 42.0, "tax": 3.2},
    "user": {"username": "dave", "full_name": "Dave Grohl"}
}
```

H3: Singular values in the body: `Body()`

PLAIN `int` WOULD BE Query PARAMETER; USE `Body()` TO READ FROM BODY (`tutorial003_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(
    item_id: int, item: Item, user: User, importance: Annotated[int, Body()]
):
    ...
```

BODY: `{"item": {...}, "user": {...}, "importance": 5}`. `Body` ACCEPTS SAME VALIDATION AS `Query`/`Path`, e.g. `Body(gt=0)` (`tutorial004_an_py310.py`). `Body` ALSO HAS `media_type`, `examples` AND `openapi_examples`.

H3: Embedding a single model: `Body(embed=True)`

BY default, SINGLE MODEL PARAMETER MEANS BODY IS MODEL. TO REQUIRE A KEY WRAPPING IT, USE `embed=True` (`tutorial005_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Annotated[Item, Body(embed=True)]):
    results = {"item_id": item_id, "item": item}
    return results
```

EXPECTED BODY: `{"item": {"name": "Foo", "price": 42.0, ...}}` INSTEAD OF `{"name": "Foo", ...}`.

H2: Field validation and metadata: `Field()`

INSIDE MODELS, USE pydantic'S `Field` AS YOU'D USE `Query`/`Path`/`Body` FOR PARAMETERS (`docs_src/body_fields/tutorial001_an_py310.py`):

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
`Field` IMPORTED FROM `pydantic`, NOT `fastapi`. SUPPORTS `default`, `title`,
`description`, `examples`, `alias`, NUMERIC (`gt`, `ge`, `lt`, `le`) AND STRING
(`min_length`, `max_length`, `pattern`) CONSTRAINTS; THESE APPEAR IN JSON SCHEMA.
FastAPI's `Query`, `Path`, `Body` ETC. ARE BUILT ON pydantic's `FieldInfo`.

H2: NESTED MODELS

H3: LISTS AND SETS

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []          # tutorial002
    # tags: set[str] = set()      # tutorial003: duplicates removed, uniqueItems in schema
```

H3: SUBMODELS

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

(`docs_src/body_nested_models/tutorial004_py310.py`.) EXPECTED JSON NESTS
`"image": {"url": ..., "name": ...}`; VALIDATION, CONVERSION, AND DOCS WORK
AT EVERY LEVEL.

H3: SPECIAL TYPES AND LISTS OF SUBMODELS

USE pydantic TYPES LIKE `HttpUrl` FOR VALIDATED STRINGS (`tutorial005`), AND
LISTS OF MODELS (`tutorial006`):

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

DEEP NESTING (`tutorial007_py310.py`):

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

H3: BODIES THAT ARE LISTS OR DICTS

TOP-LEVEL JSON ARRAY (`tutorial008_py310.py`):

```python
@app.post("/images/multiple/")
async def create_multiple_images(images: list[Image]):
    return images
```

DICT WITH ARBITRARY KEYS (`tutorial009_py310.py`):

```python
@app.post("/index-weights/")
async def create_index_weights(weights: dict[int, float]):
    return weights
```

JSON OBJECT KEYS ARE ALWAYS STRINGS; pydantic CONVERTS THEM TO `int` HERE,
AND VALIDATES VALUES AS `float`.

H2: RELATED

- [RESPONSE MODELS AND RETURN TYPES](../models/response-model.md)
- [EXTRA MODELS AND BODY UPDATES](../models/extra-models-and-updates.md) —
  INPUT/OUTPUT MODELS, PATCH
- [EXTRA DATA TYPES AND examples](extra-data-types-and-examples.md) —
  `datetime`, `UUID`, examples
- [FORMS AND FILE UPLOADS](forms-and-files.md) — NON-JSON BODIES
