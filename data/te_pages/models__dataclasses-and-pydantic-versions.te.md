---
type: guide
title: dataclasses, Separate OpenAPI Schemas and pydantic v1 to v2
description: Use standard or pydantic dataclasses as request bodies and response models, understand why pydantic v2 generates separate Item-Input/Item-Output schemas and how to disable it with separate_input_output_schemas=False, and migrate apps from pydantic v1 to v2.
tags: [dataclasses, pydantic, pydantic-v2, migration, OpenAPI, JSON-schema, separate_input_output_schemas]
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
    resource: repo://docs/en/docs/how-to/separate-OpenAPI-schemas.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://FastAPI/applications.py
  - id: openwiki-source-6960ae62409012c9993d0ec2
    resource: repo://FastAPI/exceptions.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://FastAPI/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: dataclasses, SEPARATE OpenAPI SCHEMAS AND pydantic v1 TO v2

H2: dataclasses

FastAPI ACCEPTS STANDARD-LIBRARY `dataclasses` WHEREVER IT ACCEPTS pydantic
MODELS: BODIES, `response_model`, RETURN TYPES.
pydantic CONVERTS THEM INTERNALLY TO pydantic dataclasses
→ VALIDATION, SERIALIZATION, DOCS (`docs_src/dataclasses_/tutorial001_py310.py`):

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

AS RESPONSE MODEL (`tutorial002_py310.py`):

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

dataclasses LACK SOME pydantic MODEL CAPABILITIES (e.g. ADVANCED VALIDATORS,
Config); `BaseModel` MAY STILL BE NEEDED.

H3: `pydantic.dataclasses` AS DROP-IN REPLACEMENT

IF ISSUES OCCUR (e.g. GENERATED DOCS FOR NESTED dataclasses),
SWAP IMPORT FOR pydantic VERSION (`tutorial003_py310.py`):

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

NOTES: `field` REMAINS FROM STDLIB; `list[Item]` Body ACCEPTED;
ENDPOINT RETURNS PLAIN DICTS, WHICH `response_model` CONVERTS.
dataclasses CAN BE COMBINED WITH, INHERIT FROM, AND BE NESTED IN
pydantic MODELS.

H2: SEPARATE Input AND Output SCHEMAS

WITH pydantic v2, MODEL MAY HAVE **TWO** JSON SCHEMAS IN OpenAPI.
EXAMPLE (`docs_src/separate_openapi_schemas/tutorial001_py310.py`):

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

- Input: `description` **NOT REQUIRED**; IT HAS A DEFAULT.
- Output: `description` **ALWAYS PRESENT** IN JSON (POSSIBLY `null`);
  THEREFORE MARKED **REQUIRED**.

∴ OpenAPI CONTAINS `Item-Input` AND `Item-Output`.
THIS IS MORE PRECISE AND PRODUCES BETTER GENERATED CLIENTS.

H3: USING ONE SCHEMA

IF ONE SCHEMA IS NEEDED (e.g. EXISTING GENERATED CLIENTS CANNOT YET
BE REGENERATED), DISABLE SEPARATE SCHEMAS:

```python
app = FastAPI(separate_input_output_schemas=False)
```

NOW ONLY `Item`; `description` NOT REQUIRED, AS IN pydantic v1-ERA Output.
FLAG PASSED TO OpenAPI GENERATION
(`get_openapi(..., separate_input_output_schemas=...)`).

H2: MIGRATING FROM pydantic v1 TO v2

CURRENT FastAPI REQUIRES **pydantic v2** (`pydantic>=2.9.0`).
SUPPORT TIMELINE:

| FastAPI | pydantic SUPPORT |
|---------|------------------|
| 0.100.0 | v1 **OR** v2 (WHICHEVER IS INSTALLED) |
| 0.119.0 | PARTIAL SUPPORT FOR `pydantic.v1` MODELS INSIDE pydantic v2, TO EASE MIGRATION |
| 0.126.0 | pydantic v1 DROPPED; `pydantic.v1` STILL TEMPORARILY SUPPORTED |
| 0.128.0 | `pydantic.v1` ALSO DROPPED — v2 ONLY |

IN CURRENT VERSIONS, `pydantic.v1` MODEL USE RAISES
`PydanticV1NotSupportedError` (e.g.
*"pydantic.v1 models are no longer supported by FastAPI. Please update the response model ..."*).
ALSO, pydantic TEAM DOES NOT SUPPORT v1 (INCLUDING `pydantic.v1`)
ON PYTHON 3.14+.

H3: HOW TO MIGRATE
1. HAVE TESTS; RUN IN CI ([Testing with TestClient](../testing/testing-basics.md))
2. READ pydantic OFFICIAL MIGRATION GUIDE: STRICTER, MORE CORRECT VALIDATION; RENAMED APIs
3. RUN `bump-pydantic` TO AUTOMATICALLY REWRITE MOST CODE
4. FIX REMAINING ISSUES; RUN TESTS

COMMON FastAPI CODE RENAMES:
`.dict()` → `.model_dump()`
`.json()` → `.model_dump_json()`
`.parse_obj()` → `.model_validate()`
`.copy(update=...)` → `.model_copy(update=...)`
`class Config` → `model_config = ConfigDict(...)`
OR `SettingsConfigDict` FOR SETTINGS
`schema_extra` → `json_schema_extra`
`orm_mode` → `from_attributes`

H3: GRADUAL MIGRATION ON OLDER FastAPI (0.119–0.127)

ONLY ON THOSE VERSIONS: UPGRADE TO pydantic v2; TEMPORARILY IMPORT OLD MODELS FROM `pydantic.v1`:

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

SEPARATE v1 AND v2 MODELS COULD COEXIST, EVEN IN ONE PATH OPERATION
(e.g. v1 Input WITH `response_model=ItemV2`);
v2 MODEL CANNOT CONTAIN v1 MODEL FIELDS, OR VICE VERSA.
FastAPI PARAMETER FUNCTIONS FOR v1 MODELS PROVIDED AS
`fastapi.temp_pydantic_v1_params` (`Body`, `Query`, `Form`, …).
NONE OF THIS EXISTS IN CURRENT VERSION;
FINISH MIGRATION BEFORE UPGRADING FastAPI PAST 0.127.

H2: RELATED

- [Response Models and Return Types](response-model.md)
- [Extra Models, jsonable_encoder and Body Updates](extra-models-and-updates.md)
- [Generating SDK Clients](../OpenAPI/generating-clients.md)
