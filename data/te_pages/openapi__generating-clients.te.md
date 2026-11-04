---
type: guide
title: Generating SDK Clients
description: Generate typed client SDKs (e.g. TypeScript with hey API, or many languages with OpenAPI Generator) from FastAPI's OpenAPI 3.1 schema, organize them with tags, and get clean method names via generate_unique_id_function and OpenAPI preprocessing.
tags: [openapi, SDK, client-generation, TypeScript, hey-api, operation_id, generate_unique_id_function, tags]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - ID: openwiki-source-59a7865e2278cee3747d1fc0
    resource: repo://docs_src/generate_clients/tutorial002_py310.py
  - ID: openwiki-source-a46bf4ffd2de64654d40232b
    resource: repo://docs_src/generate_clients/tutorial003_py310.py
  - ID: openwiki-source-2b3a6ecf8322c7cd69b79190
    resource: repo://docs_src/generate_clients/tutorial004_py310.py
  - ID: openwiki-source-87af7584e524afec4b61cf9d
    resource: repo://docs_src/generate_clients/tutorial004.js
  - ID: openwiki-source-4546be900a921da774341d65
    resource: repo://docs/en/docs/advanced/generate-clients.md
  - ID: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://FastAPI/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Generating SDK Clients

EVERY FastAPI APP PUBLISHES AN **OPENAPI** SCHEMA ⇒ GENERATE CLIENT LIBRARIES (SDKs) THAT STAY IN SYNC WITH THE BACKEND; GET AUTOCOMPLETION FOR METHODS, REQUEST PAYLOADS, AND RESPONSES, PLUS BUILD-TIME ERRORS WHEN THE API CHANGES.

H2: Generators

- **OpenAPI Generator** — MANY LANGUAGES.
- **hey API** (`@hey-api/openapi-ts`) — BUILT FOR TypeScript.
- MORE ON OpenAPI.Tools (SDK GENERATORS CATEGORY).

FastAPI EMITS **OPENAPI 3.1**; TOOL MUST SUPPORT 3.1.

H2: Make the schema client-friendly

DECLARE REQUEST BODIES AND RESPONSES WITH MODELS, SO THE GENERATOR KNOWS THE TYPES (`docs_src/generate_clients/tutorial001_py310.py`):

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

BOTH `Item` AND `ResponseMessage` APPEAR AS SCHEMAS IN `/openapi.json` AND BECOME CLIENT TYPES.

H2: Generate a TypeScript client

WITH THE APP RUNNING:

```bash
npx @hey-api/openapi-ts -i http://localhost:8000/openapi.json -o src/client
```

H2: Group with tags

TAGS LET GENERATORS SPLIT THE CLIENT INTO SERVICES (`tutorial002_py310.py`):

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

CLIENT THEN HAS, e.g., `ItemsService` AND `UsersService`.

H2: Clean method names

GENERATORS name METHODS AFTER EACH OPERATION'S **OPERATION ID**. FastAPI'S DEFAULT ID COMBINES FUNCTION name, PATH, AND METHOD TO GUARANTEE UNIQUENESS (e.g. `create_item_items__post`), PRODUCING NAMES LIKE:

```typescript
ItemsService.createItemItemsPost({name: "Plumbus", price: 5})
```

H3: Custom `generate_unique_id_function`

FastAPI USES ONE **UNIQUE ID** PER PATH OPERATION FOR THE OPERATION ID AND GENERATED REQUEST/RESPONSE MODEL NAMES. CUSTOMIZE IT WITH A FUNCTION THAT TAKES AN `APIRoute` AND RETURNS A STRING (`tutorial003_py310.py`):

```python
from fastapi import FastAPI
from fastapi.routing import APIRoute


def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

NOW IDs LOOK LIKE `items-create_item`. GUARANTEE UNIQUENESS YOURSELF: EVERY OPERATION NEEDS AT LEAST ONE TAG (OTHERWISE `route.tags[0]` FAILS), AND FUNCTION NAMES MUST BE UNIQUE PER TAG. THE PARAMETER CAN ALSO BE SET ON AN `APIRouter` OR IN `include_router()`; AN EXPLICIT `operation_id=` ON A DECORATOR OVERRIDES IT. SEE [PATH OPERATION CONFIGURATION](../app-structure/path-operation-configuration.md).

H3: Preprocess the schema for the generator

CLIENT ALREADY GROUPS METHODS BY TAG, SO THE `items-` PREFIX IS REDUNDANT (`ItemsService.itemsCreateItem`). DOWNLOAD `openapi.json` AND STRIP THE TAG PREFIX BEFORE GENERATING (`tutorial004_py310.py`):

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

(JavaScript VERSION: `docs_src/generate_clients/tutorial004.js`.) THEN:

```bash
npx @hey-api/openapi-ts -i ./openapi.json -o src/client
```

RESULT: `ItemsService.createItem({name: "Plumbus", price: 5})`.

H2: Tips

- REGENERATE THE CLIENT WHENEVER THE BACKEND CHANGES (e.g. IN CI OR A PACKAGE SCRIPT); TYPE ERRORS THEN REVEAL MISMATCHES EARLY.
- EXISTING CLIENTS THAT BREAK BECAUSE OF `Item-Input` / `Item-Output` SCHEMAS: SEE `separate_input_output_schemas` IN [DATACLASSES, SEPARATE OPENAPI SCHEMAS AND PYDANTIC v1 TO v2](../models/dataclasses-and-pydantic-versions.md).
- THE FULL STACK FastAPI TEMPLATE INCLUDES AN AUTOMATICALLY GENERATED FRONTEND CLIENT.

H2: Related

- [EXTENDING OPENAPI](extending-openapi.md)
- [API METADATA AND DOCS UIs](metadata-and-docs-ui.md)
