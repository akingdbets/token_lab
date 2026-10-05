---
type: guide
title: Generating SDK Clients
description: Generate typed client SDKs (e.g. TypeScript with Hey API, or many languages with OpenAPI Generator) from FastAPI's OpenAPI 3.1 schema, organize them with tags, and get clean method names via generate_unique_id_function and OpenAPI preprocessing.
tags: [openapi, sdk, client-generation, typescript, hey-api, operation_id, generate_unique_id_function, tags]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-59a7865e2278cee3747d1fc0
    resource: repo://docs_src/generate_clients/tutorial002_py310.py
  - id: openwiki-source-a46bf4ffd2de64654d40232b
    resource: repo://docs_src/generate_clients/tutorial003_py310.py
  - id: openwiki-source-2b3a6ecf8322c7cd69b79190
    resource: repo://docs_src/generate_clients/tutorial004_py310.py
  - id: openwiki-source-87af7584e524afec4b61cf9d
    resource: repo://docs_src/generate_clients/tutorial004.js
  - id: openwiki-source-4546be900a921da774341d65
    resource: repo://docs/en/docs/advanced/generate-clients.md
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Generating SDK Clients

Because every FastAPI app publishes an **OpenAPI** schema, you can generate client libraries (SDKs) that stay in sync with your backend — with autocompletion for methods, request payloads and responses, and build-time errors when the API changes.

## Generators

- **OpenAPI Generator** — many languages.
- **Hey API** (`@hey-api/openapi-ts`) — purpose-built for TypeScript.
- More on OpenAPI.Tools (SDK generators category).

FastAPI emits **OpenAPI 3.1**, so the tool must support 3.1.

## Make the schema client-friendly

Declare request bodies and responses with models so the generator knows the types (`docs_src/generate_clients/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


class ResponseMessage(BaseModel):
    message: str


@app.post("/items/", response_model=ResponseMessage)
async def create_item(item: Item):
    return {"message": "item received"}


@app.get("/items/", response_model=list[Item])
async def get_items():
    return [
        {"name": "Plumbus", "price": 3},
        {"name": "Portal Gun", "price": 9001},
    ]
```

Both `Item` and `ResponseMessage` appear as schemas in `/openapi.json` and become client types.

## Generate a TypeScript client

With the app running:

```bash
npx @hey-api/openapi-ts -i http://localhost:8000/openapi.json -o src/client
```

## Group with tags

Tags let generators split the client into services (`tutorial002_py310.py`):

```python
@app.post("/items/", response_model=ResponseMessage, tags=["items"])
async def create_item(item: Item):
    return {"message": "Item received"}


@app.get("/items/", response_model=list[Item], tags=["items"])
async def get_items():
    ...


@app.post("/users/", response_model=ResponseMessage, tags=["users"])
async def create_user(user: User):
    return {"message": "User received"}
```

The client then has e.g. `ItemsService` and `UsersService`.

## Clean method names

Generators name methods after each operation's **operation ID**. FastAPI's default ID combines function name, path and method to guarantee uniqueness (e.g. `create_item_items__post`), producing names like:

```typescript
ItemsService.createItemItemsPost({name: "Plumbus", price: 5})
```

### Custom `generate_unique_id_function`

FastAPI uses one **unique ID** per path operation for the operation ID and for names of generated request/response models. Customize it with a function taking an `APIRoute` and returning a string (`tutorial003_py310.py`):

```python
from fastapi import FastAPI
from fastapi.routing import APIRoute


def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

Now IDs look like `items-create_item`. You must guarantee uniqueness yourself — here every operation needs at least one tag (otherwise `route.tags[0]` fails) and function names must be unique per tag. The parameter can also be set on an `APIRouter` or in `include_router()`; an explicit `operation_id=` on a decorator overrides it. See [Path Operation Configuration](../app-structure/path-operation-configuration.md).

### Preprocess the schema for the generator

Since the client already groups methods by tag, the `items-` prefix is redundant (`ItemsService.itemsCreateItem`). Download `openapi.json` and strip the tag prefix before generating (`tutorial004_py310.py`):

```python
import json
from pathlib import Path

file_path = Path("./openapi.json")
openapi_content = json.loads(file_path.read_text())

for path_data in openapi_content["paths"].values():
    for operation in path_data.values():
        tag = operation["tags"][0]
        operation_id = operation["operationId"]
        to_remove = f"{tag}-"
        new_operation_id = operation_id[len(to_remove) :]
        operation["operationId"] = new_operation_id

file_path.write_text(json.dumps(openapi_content))
```

(A JavaScript version is in `docs_src/generate_clients/tutorial004.js`.) Then:

```bash
npx @hey-api/openapi-ts -i ./openapi.json -o src/client
```

Result: `ItemsService.createItem({name: "Plumbus", price: 5})`.

## Tips

- Regenerate the client whenever the backend changes (e.g. in CI or a package script); type errors then reveal mismatches early.
- If you have existing clients that break because of `Item-Input` / `Item-Output` schemas, see `separate_input_output_schemas` in [Dataclasses, Separate OpenAPI Schemas and Pydantic v1 to v2](../models/dataclasses-and-pydantic-versions.md).
- The Full Stack FastAPI Template includes an automatically generated frontend client.

## Related

- [Extending OpenAPI](extending-openapi.md)
- [API Metadata and Docs UIs](metadata-and-docs-ui.md)
