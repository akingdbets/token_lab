---
type: reference
title: PATH operation CONFIGURATION
description: DECORATOR PARAMETERS SHAPE PATH operation DOCUMENTATION AND OPENAPI ENTRY: `status_code`, `tags`, `summary`, `description` AND DOCSTRINGS, `response_description`, `deprecated`, `operation_id`, `generate_unique_id_function`, `include_in_schema` AND `openapi_extra`.
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

H1: PATH operation CONFIGURATION

EVERY PATH operation DECORATOR (`@app.get()`, `@app.post()`,
`@router.put()`, …) ACCEPTS PARAMETERS CONFIGURING ITS OPENAPI
AND DOCS UI APPEARANCE; PARAMETERS BELONG TO THE **DECORATOR**,
NOT YOUR FUNCTION.

H2: STATUS CODE

```python
from fastapi import FastAPI, status

@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(item: Item) -> Item:
    return item
```

`status_code` ACCEPTS AN `int` OR A CONSTANT FROM `fastapi.status`
(ALSO `http.HTTPStatus`; `IntEnum` VALUES NORMALIZE TO `int`).
SEE [Response STATUS CODES](../responses/status-codes.md).

H2: tags

`tags` GROUPS OPERATIONS IN THE DOCS UI
(`docs_src/path_operation_configuration/tutorial002_py310.py`):

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

LARGER APPS: USE AN `Enum` TO KEEP TAG NAMES CONSISTENT
(`tutorial002b_py310.py`):

```python
from enum import Enum


class Tags(Enum):
    items = "items"
    users = "users"


@app.get("/items/", tags=[Tags.items])
async def get_items():
    return ["Portal gun", "Plumbus"]
```

SET tags ALSO ON AN `APIRouter` OR IN `include_router()`
(SEE [BIGGER APPLICATIONS](bigger-applications.md)); DESCRIBE
THEM WITH APP `openapi_tags` (SEE
[API METADATA AND DOCS UIs](../openapi/metadata-and-docs-ui.md)).

H2: summary AND description

```python
@app.post(
    "/items/",
    summary="Create an item",
    description="Create an item with all the information, name, description, price, tax and a set of unique tags",
)
async def create_item(item: Item) -> Item:
    return item
```

OMIT `summary` ⇒ DOCS DERIVE TITLE FROM FUNCTION name.
OMIT `description` ⇒ FASTAPI USES FUNCTION **DOCSTRING**,
CLEANED WITH `inspect.cleandoc`; MARKDOWN SUPPORTED:

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

H3: TRUNCATING THE DOCSTRING WITH `\f`

KEEP INTERNAL NOTES (e.g. SPHINX `:param:` LINES) OUT OF OPENAPI:
PUT A FORM FEED `\f` IN THE DOCSTRING. FASTAPI KEEPS ONLY TEXT
BEFORE THE FIRST `\f` (`route.description.split("\f")[0]` IN
`fastapi/routing.py`):

```python
    """
    Create an item with all the information:
    ...
    - **tags**: a set of unique tag strings for this item
    \f
    :param item: User input.
    """
```

H2: Response description

`response_description` DESCRIBES THE MAIN Response; DEFAULT:
`"Successful Response"`.

```python
@app.post(
    "/items/",
    summary="Create an item",
    response_description="The created item",
)
```

H2: DEPRECATING AN operation

```python
@app.get("/elements/", tags=["items"], deprecated=True)
async def read_elements():
    return [{"item_id": "Foo"}]
```

operation STILL WORKS; DOCS MARK IT deprecated.
`deprecated=True` ALSO WORKS FOR A WHOLE ROUTER.
DEPRECATE INDIVIDUAL PARAMETERS WITH `Query(deprecated=True)`,
ETC. (SEE [Query PARAMETERS](../request/Query-parameters.md)).

H2: operation IDs

EVERY operation GETS A UNIQUE OPENAPI `operationId`.
DEFAULT: `fastapi.utils.generate_unique_id` PRODUCES ROUTE name
+ PATH, WITH NON-WORD CHARACTERS REPLACED BY `_`, PLUS
LOWERCASED HTTP METHOD (e.g. `read_items_items__get`).

SET IT EXPLICITLY WITH `operation_id`; KEEP IT UNIQUE:

```python
@app.get("/items/", operation_id="some_specific_id_you_define")
async def read_items():
    return [{"item_id": "Foo"}]
```

CHANGE THE STRATEGY FOR THE WHOLE APP (OR A ROUTER / INCLUDE)
WITH `generate_unique_id_function`; IT RECEIVES EACH `APIRoute`:

```python
from fastapi import FastAPI
from fastapi.routing import APIRoute


def custom_generate_unique_id(route: APIRoute) -> str:
    return route.name


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

EXPLICIT `operation_id` ALWAYS OVERRIDES THE FUNCTION.
IF USING FUNCTION name, EVERY PATH operation FUNCTION NEEDS
A UNIQUE name, INCLUDING ACROSS MODULES.
CLEAN IDs MATTER MOST WHEN [GENERATING CLIENT SDKs]
(../openapi/generating-clients.md).

H2: EXCLUDING FROM OPENAPI

```python
@app.get("/items/", include_in_schema=False)
async def read_items():
    return [{"item_id": "Foo"}]
```

ENDPOINT STILL WORKS, BUT DOES NOT APPEAR IN `/openapi.json`
OR DOCS. ALSO AVAILABLE ON ROUTERS AND IN `include_router()`.

H2: ADDITIONAL responses

`responses={...}` DOCUMENTS EXTRA STATUS CODES AND MODELS.
SEE [EXTENDING OPENAPI](../openapi/extending-openapi.md).

H2: `openapi_extra`: EDITING THE operation OBJECT

`openapi_extra` IS A DICT **DEEP-MERGED** INTO THE GENERATED
OPENAPI operation OBJECT
(`deep_dict_update(operation, route.openapi_extra)` IN
`fastapi/openapi/utils.py`).

OPENAPI EXTENSIONS (`x-...` KEYS):

```python
@app.get("/items/", openapi_extra={"x-aperture-labs-portal": "blue"})
async def read_items():
    return [{"item_id": "portal-gun"}]
```
MANUAL REQUEST-BODY PARSING (`tutorial006_py310.py`): FASTAPI DOES NOT READ OR
VALIDATE BODY; DOCS SHOW SCHEMA

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

NON-JSON CONTENT TYPE ACCEPTED; PYDANTIC MODEL REUSED FOR SCHEMA AND
VALIDATION (`tutorial007_py310.py`):

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

H2: Other decorator parameters

FOR COMPLETENESS, DECORATORS ALSO TAKE:
  response_model AND ITS response_model_* OPTIONS
  ([Response MODELS](../models/Response-model.md))
  response_class ([CUSTOM responses](../responses/custom-responses.md))
  dependencies ([dependencies IN DECORATORS](../dependencies/decorator-and-global-dependencies.md))
  callbacks ([EXTENDING OPENAPI](../openapi/extending-openapi.md))
  name
