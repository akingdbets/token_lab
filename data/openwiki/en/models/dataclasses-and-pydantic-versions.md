---
type: guide
title: Dataclasses, Separate OpenAPI Schemas and Pydantic v1 to v2
description: Use standard or Pydantic dataclasses as request bodies and response models, understand why Pydantic v2 generates separate Item-Input/Item-Output schemas and how to disable it with separate_input_output_schemas=False, and migrate apps from Pydantic v1 to v2.
tags: [dataclasses, pydantic, pydantic-v2, migration, openapi, json-schema, separate_input_output_schemas]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-4fff8cb0aa0f6462c62095ec
    resource: repo://docs_src/dataclasses_/tutorial001_py310.py
  - id: openwiki-source-ced07dd154cac77e0f89290a
    resource: repo://docs_src/dataclasses_/tutorial002_py310.py
  - id: openwiki-source-1444b79c624a2dd4828c71dc
    resource: repo://docs_src/dataclasses_/tutorial003_py310.py
  - id: openwiki-source-11d9058e010a5259b2819d6c
    resource: repo://docs_src/separate_openapi_schemas/tutorial001_py310.py
  - id: openwiki-source-ee2a28566b2d27a7c248ea1c
    resource: repo://docs_src/separate_openapi_schemas/tutorial002_py310.py
  - id: openwiki-source-2f7bfc1b704b58f5752dfa5a
    resource: repo://docs/en/docs/advanced/dataclasses.md
  - id: openwiki-source-01c7db97f3abec2e53d5dfa5
    resource: repo://docs/en/docs/how-to/migrate-from-pydantic-v1-to-pydantic-v2.md
  - id: openwiki-source-bad0099f9c0fe805c4d8d348
    resource: repo://docs/en/docs/how-to/separate-openapi-schemas.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-6960ae62409012c9993d0ec2
    resource: repo://fastapi/exceptions.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Dataclasses, Separate OpenAPI Schemas and Pydantic v1 to v2

## Dataclasses

FastAPI accepts standard library `dataclasses` wherever it accepts Pydantic models: bodies, `response_model`, return types. Pydantic converts them internally into Pydantic dataclasses, so you get validation, serialization and docs (`docs_src/dataclasses_/tutorial001_py310.py`):

```python
from dataclasses import dataclass

from fastapi import FastAPI


@dataclass
class Item:
    name: str
    price: float
    description: str | None = None
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return item
```

As a response model (`tutorial002_py310.py`):

```python
from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    price: float
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    tax: float | None = None


@app.get("/items/next", response_model=Item)
async def read_next_item():
    return {
        "name": "Island In The Moon",
        "price": 12.99,
        "description": "A place to be playin' and havin' fun",
        "tags": ["breater"],
    }
```

Dataclasses can't do everything Pydantic models can (e.g. advanced validators, config), so you may still need `BaseModel`.

### `pydantic.dataclasses` as a drop-in replacement

If you hit problems (e.g. with generated docs for nested dataclasses), swap the import for Pydantic's version (`tutorial003_py310.py`):

```python
from dataclasses import field

from fastapi import FastAPI
from pydantic.dataclasses import dataclass


@dataclass
class Item:
    name: str
    description: str | None = None


@dataclass
class Author:
    name: str
    items: list[Item] = field(default_factory=list)


app = FastAPI()


@app.post("/authors/{author_id}/items/", response_model=Author)
async def create_author_items(author_id: str, items: list[Item]):
    return {"name": author_id, "items": items}


@app.get("/authors/", response_model=list[Author])
def get_authors():
    return [...]
```

Notes: `field` still comes from the stdlib; a `list[Item]` body is accepted; the endpoint returns plain dicts and `response_model` converts them. Dataclasses can be combined with, inherit from, and be nested in Pydantic models.

## Separate input and output schemas

With Pydantic v2, a model may get **two** JSON Schemas in OpenAPI. Take (`docs_src/separate_openapi_schemas/tutorial001_py310.py`):

```python
class Item(BaseModel):
    name: str
    description: str | None = None


@app.post("/items/")
def create_item(item: Item):
    return item


@app.get("/items/")
def read_items() -> list[Item]:
    return [
        Item(
            name="Portal Gun",
            description="Device to travel through the multi-rick-verse",
        ),
        Item(name="Plumbus"),
    ]
```

- As **input**, `description` is **not required** (it has a default).
- As **output**, `description` is **always present** in the JSON (possibly `null`), so it's marked **required**.

OpenAPI therefore contains `Item-Input` and `Item-Output`. This is more precise and produces better generated clients.

### Using one schema

If you need a single schema — e.g. existing generated clients you can't regenerate yet — disable it:

```python
app = FastAPI(separate_input_output_schemas=False)
```

Now there's just `Item`, with `description` not required, as in Pydantic v1-era output. The flag is passed to OpenAPI generation (`get_openapi(..., separate_input_output_schemas=...)`).

## Migrating from Pydantic v1 to v2

Current FastAPI requires **Pydantic v2** (`pydantic>=2.9.0`). Timeline:

| FastAPI | Pydantic support |
|---------|------------------|
| 0.100.0 | v1 **or** v2 (whichever is installed) |
| 0.119.0 | Partial support for `pydantic.v1` models inside Pydantic v2, to ease migration |
| 0.126.0 | Pydantic v1 dropped; `pydantic.v1` still temporarily supported |
| 0.128.0 | `pydantic.v1` dropped too — v2 only |

In current versions, using a `pydantic.v1` model raises `PydanticV1NotSupportedError` (e.g. *"pydantic.v1 models are no longer supported by FastAPI. Please update the response model ..."*). Also, the Pydantic team doesn't support v1 (including `pydantic.v1`) on Python 3.14+.

### How to migrate

1. **Have tests** and run them in CI ([Testing with TestClient](../testing/testing-basics.md)).
2. Read Pydantic's official migration guide (stricter, more correct validation; renamed APIs).
3. Run **`bump-pydantic`** to rewrite most code automatically.
4. Fix remaining issues, run tests.

Common renames you'll touch in FastAPI code: `.dict()` → `.model_dump()`, `.json()` → `.model_dump_json()`, `.parse_obj()` → `.model_validate()`, `.copy(update=...)` → `.model_copy(update=...)`, `class Config` → `model_config = ConfigDict(...)` (or `SettingsConfigDict` for settings), `schema_extra` → `json_schema_extra`, `orm_mode` → `from_attributes`.

### Gradual migration on older FastAPI (0.119–0.127)

On those versions only, you could upgrade to Pydantic v2 and temporarily import old models from `pydantic.v1`:

```python
from fastapi import FastAPI
from pydantic.v1 import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    size: float


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item
```

Separate v1 and v2 models could coexist (even in one path operation, e.g. v1 input with `response_model=ItemV2`), but a v2 model can never contain v1 model fields or vice versa. FastAPI parameter functions for v1 models were provided as `fastapi.temp_pydantic_v1_params` (`Body`, `Query`, `Form`, …). None of this exists in the current version — finish the migration before upgrading FastAPI past 0.127.

## Related

- [Response Models and Return Types](response-model.md)
- [Extra Models, jsonable_encoder and Body Updates](extra-models-and-updates.md)
- [Generating SDK Clients](../openapi/generating-clients.md)
