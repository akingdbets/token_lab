---
type: reference
title: Path Operation Configuration
description: Decorator parameters that shape a path operation's documentation and OpenAPI entry — status_code, tags, summary, description and docstrings, response_description, deprecated, operation_id, generate_unique_id_function, include_in_schema and openapi_extra.
tags: [path-operation, openapi, tags, operation_id, docstring, deprecated, openapi_extra]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-a3cd249f33ef1a33ee04bb25
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial003_py310.py
  - id: openwiki-source-e3ecfcdee33b1ee4dde9390a
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial004_py310.py
  - id: openwiki-source-730e611134b4eb2c482b9ba5
    resource: repo://docs_src/path_operation_advanced_configuration/tutorial007_py310.py
  - id: openwiki-source-f998075208952cb02aa6d8b2
    resource: repo://docs/en/docs/advanced/path-operation-advanced-configuration.md
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://fastapi/openapi/utils.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Path Operation Configuration

Every path operation decorator (`@app.get()`, `@app.post()`, `@router.put()`, …) accepts parameters that configure how the operation appears in OpenAPI and the docs UI. These are parameters of the **decorator**, not of your function.

## Status code

```python
from fastapi import FastAPI, status

@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(item: Item) -> Item:
    return item
```

`status_code` accepts an `int` or a constant from `fastapi.status` (also `http.HTTPStatus`; IntEnum values are normalized to `int`). See [Response Status Codes](../responses/status-codes.md).

## Tags

`tags` groups operations in the docs UI (`docs_src/path_operation_configuration/tutorial002_py310.py`):

```python
@app.post("/items/", tags=["items"])
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/", tags=["items"])
async def read_items():
    return [{"name": "Foo", "price": 42}]


@app.get("/users/", tags=["users"])
async def read_users():
    return [{"username": "johndoe"}]
```

For larger apps, use an `Enum` so tag names stay consistent (`tutorial002b_py310.py`):

```python
from enum import Enum


class Tags(Enum):
    items = "items"
    users = "users"


@app.get("/items/", tags=[Tags.items])
async def get_items():
    return ["Portal gun", "Plumbus"]
```

Tags can also be set on an `APIRouter` or in `include_router()` (see [Bigger Applications](bigger-applications.md)), and described with `openapi_tags` on the app (see [API Metadata and Docs UIs](../openapi/metadata-and-docs-ui.md)).

## Summary and description

```python
@app.post(
    "/items/",
    summary="Create an item",
    description="Create an item with all the information, name, description, price, tax and a set of unique tags",
)
async def create_item(item: Item) -> Item:
    return item
```

If you omit `summary`, the docs derive a title from the function name. If you omit `description`, FastAPI uses the function's **docstring** (cleaned with `inspect.cleandoc`), which supports Markdown:

```python
@app.post("/items/", summary="Create an item")
async def create_item(item: Item) -> Item:
    """
    Create an item with all the information:

    - **name**: each item must have a name
    - **description**: a long description
    - **price**: required
    - **tax**: if the item doesn't have tax, you can omit this
    - **tags**: a set of unique tag strings for this item
    """
    return item
```

### Truncating the docstring with `\f`

To keep internal notes (e.g. Sphinx `:param:` lines) out of OpenAPI, put a form feed `\f` in the docstring. FastAPI keeps only the text before the first `\f` (`route.description.split("\f")[0]` in `fastapi/routing.py`):

```python
    """
    Create an item with all the information:
    ...
    - **tags**: a set of unique tag strings for this item
    \f
    :param item: User input.
    """
```

## Response description

`response_description` describes the main response; it defaults to `"Successful Response"`.

```python
@app.post(
    "/items/",
    summary="Create an item",
    response_description="The created item",
)
```

## Deprecating an operation

```python
@app.get("/elements/", tags=["items"], deprecated=True)
async def read_elements():
    return [{"item_id": "Foo"}]
```

The operation still works; the docs mark it deprecated. `deprecated=True` can also be set for a whole router. Individual parameters can be deprecated with `Query(deprecated=True)` etc. (see [Query Parameters](../request/query-parameters.md)).

## Operation IDs

Each operation gets a unique OpenAPI `operationId`. By default it is produced by `fastapi.utils.generate_unique_id`: the route name + path, with non-word characters replaced by `_`, plus the lowercased HTTP method (e.g. `read_items_items__get`).

Set it explicitly with `operation_id` (you must keep it unique):

```python
@app.get("/items/", operation_id="some_specific_id_you_define")
async def read_items():
    return [{"item_id": "Foo"}]
```

Or change the strategy for the whole app (or a router / include) with `generate_unique_id_function`, which receives each `APIRoute`:

```python
from fastapi import FastAPI
from fastapi.routing import APIRoute


def custom_generate_unique_id(route: APIRoute) -> str:
    return route.name


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

An explicit `operation_id` always wins over the function. If you use the function name, every path operation function must have a unique name, even across modules. Clean IDs matter most when [generating client SDKs](../openapi/generating-clients.md).

## Excluding from OpenAPI

```python
@app.get("/items/", include_in_schema=False)
async def read_items():
    return [{"item_id": "Foo"}]
```

The endpoint still works but does not appear in `/openapi.json` or the docs. Also available on routers and in `include_router()`.

## Additional responses

`responses={...}` documents extra status codes and models. See [Extending OpenAPI](../openapi/extending-openapi.md).

## `openapi_extra`: editing the operation object

`openapi_extra` is a dict that is **deep-merged** into the generated OpenAPI Operation Object (`deep_dict_update(operation, route.openapi_extra)` in `fastapi/openapi/utils.py`).

OpenAPI extensions (`x-...` keys):

```python
@app.get("/items/", openapi_extra={"x-aperture-labs-portal": "blue"})
async def read_items():
    return [{"item_id": "portal-gun"}]
```

Documenting a request body you parse yourself (`tutorial006_py310.py`) — FastAPI does not read or validate the body, but the docs show the schema:

```python
@app.post(
    "/items/",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "required": ["name", "price"],
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                            "description": {"type": "string"},
                        },
                    }
                }
            },
            "required": True,
        },
    },
)
async def create_item(request: Request):
    raw_body = await request.body()
    data = magic_data_reader(raw_body)
    return data
```

Accepting a non-JSON content type while reusing a Pydantic model for schema and validation (`tutorial007_py310.py`):

```python
import yaml
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ValidationError


class Item(BaseModel):
    name: str
    tags: list[str]


@app.post(
    "/items/",
    openapi_extra={
        "requestBody": {
            "content": {"application/x-yaml": {"schema": Item.model_json_schema()}},
            "required": True,
        },
    },
)
async def create_item(request: Request):
    raw_body = await request.body()
    try:
        data = yaml.safe_load(raw_body)
    except yaml.YAMLError:
        raise HTTPException(status_code=422, detail="Invalid YAML")
    try:
        item = Item.model_validate(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False))
    return item
```

## Other decorator parameters

For completeness, decorators also take `response_model` and its `response_model_*` options ([Response Models](../models/response-model.md)), `response_class` ([Custom Responses](../responses/custom-responses.md)), `dependencies` ([Dependencies in Decorators](../dependencies/decorator-and-global-dependencies.md)), `callbacks` ([Extending OpenAPI](../openapi/extending-openapi.md)) and `name`.
