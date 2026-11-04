---
type: guide
title: EXTRA data TYPES, SCHEMA examples AND Base64 bytes
description: USE UUID, DATETIME, DATE, TIME, TIMEDELTA, frozenset, bytes, Decimal AND OTHER PYDANTIC TYPES IN PARAMETERS AND BODIES; DECLARE REQUEST examples WITH json_schema_extra, Field(examples), Body(examples) AND openapi_examples; SEND binary data IN JSON AS BASE64 WITH val_json_bytes / ser_json_bytes.
tags: [data-types, UUID, datetime, decimal, examples, openapi_examples, json_schema_extra, base64, bytes]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-83976647ebab5c40786b8b7d
    resource: repo://docs_src/extra_data_types/tutorial001_an_py310.py
  - id: openwiki-source-2bda54f1ef92ef644bcaf7ce
    resource: repo://docs_src/json_base64_bytes/tutorial001_py310.py
  - id: openwiki-source-f850ad8b6b3141eeb84cde3c
    resource: repo://docs_src/schema_extra_example/tutorial001_py310.py
  - id: openwiki-source-dc5000a0b05c97d273f8f89c
    resource: repo://docs_src/schema_extra_example/tutorial002_py310.py
  - id: openwiki-source-85aa3d959afff18201e713bf
    resource: repo://docs_src/schema_extra_example/tutorial004_an_py310.py
  - id: openwiki-source-71a4977d3025dd530ef71572
    resource: repo://docs_src/schema_extra_example/tutorial005_an_py310.py
  - id: openwiki-source-cba9b46e921902a6e86b1318
    resource: repo://docs/en/docs/advanced/JSON-base64-bytes.md
  - id: openwiki-source-b9633307ba09f9f9d701465c
    resource: repo://docs/en/docs/tutorial/extra-data-types.md
  - id: openwiki-source-106f497dd08938cd7251aaf0
    resource: repo://docs/en/docs/tutorial/schema-extra-example.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: EXTRA data TYPES, SCHEMA examples AND Base64 bytes

H2: EXTRA data TYPES

BEYOND `int`, `float`, `str` AND `bool`, ANY PYDANTIC-SUPPORTED TYPE WORKS IN Path/Query/Header/Cookie PARAMETERS, BODIES AND RESPONSES; CONVERSION, VALIDATION AND DOCUMENTATION REMAIN THE SAME.

| PYTHON TYPE | JSON REPRESENTATION |
|-------------|---------------------|
| `uuid.UUID` | `str` |
| `datetime.datetime` | ISO 8601 `str`, e.g. `2008-09-15T15:53:00+05:00` |
| `datetime.date` | ISO 8601 `str`, e.g. `2008-09-15` |
| `datetime.time` | ISO 8601 `str`, e.g. `14:23:55.003` |
| `datetime.timedelta` | `float` OF TOTAL SECONDS; PYDANTIC CAN ALSO USE ISO 8601 DURATIONS |
| `frozenset` / `set` | REQUEST: LIST, DE-DUPLICATED; RESPONSE: LIST; SCHEMA HAS `uniqueItems` |
| `bytes` | `str` (SCHEMA FORMAT `binary`) |
| `decimal.Decimal` | HANDLED LIKE `float` |

SEE PYDANTIC'S TYPES DOCUMENTATION FOR FULL LIST, e.g. `EmailStr`, `HttpUrl`, CONSTRAINED TYPES.

`docs_src/extra_data_types/tutorial001_an_py310.py`:

```python
from datetime import datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Body, FastAPI

app = FastAPI()


@app.put("/items/{item_id}")
async def read_items(
    item_id: UUID,
    start_datetime: Annotated[datetime, Body()],
    end_datetime: Annotated[datetime, Body()],
    process_after: Annotated[timedelta, Body()],
    repeat_at: Annotated[time | None, Body()] = None,
):
    start_process = start_datetime + process_after
    duration = end_datetime - start_process
    return {
        "item_id": item_id,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "process_after": process_after,
        "repeat_at": repeat_at,
        "start_process": start_process,
        "duration": duration,
    }
```

INSIDE FUNCTION, VALUES ARE REAL PYTHON OBJECTS (e.g. DATETIME ARITHMETIC IS POSSIBLE); RESPONSE CONVERTS THEM BACK TO JSON. SEE `jsonable_encoder` IN [EXTRA MODELS](../models/extra-models-and-updates.md).

H2: DECLARING REQUEST examples

examples APPEAR IN DOCS UI AND HELP CLIENTS; TWO DISTINCT MECHANISMS.

H3: 1. JSON SCHEMA `examples` (INSIDE MODEL SCHEMA)

IN MODEL CONFIG (`docs_src/schema_extra_example/tutorial001_py310.py`):

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 3.2,
                }
            ]
        }
    }
```

`json_schema_extra` CAN ADD ANY EXTRA JSON SCHEMA INFO, e.g. FRONTEND METADATA.

PER Field, USE `Field(examples=[...])` (`tutorial002_py310.py`):

```python
from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str = Field(examples=["Foo"])
    description: str | None = Field(default=None, examples=["A very nice Item"])
    price: float = Field(examples=[35.4])
    tax: float | None = Field(default=None, examples=[3.2])
```

PER PARAMETER, `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` AND `File()` ACCEPT `examples=[...]` (`tutorial003_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Annotated[
        Item,
        Body(
            examples=[
                {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 3.2,
                }
            ],
        ),
    ],
):
    ...
```

SEVERAL examples ARE SUPPORTED (`tutorial004_an_py310.py`); SWAGGER UI CURRENTLY SHOWS ONLY ONE example FROM JSON SCHEMA `examples`.

`examples` (A LIST) IS THE JSON SCHEMA STANDARD KEYWORD; SUPPORTED SINCE OpenAPI 3.1.0 (FastAPI ≥ 0.99.0). SINGLE `example` KEYWORD STILL WORKS, BUT IS DEPRECATED; MIGRATE TO `examples`.

H3: 2. OpenAPI-SPECIFIC `openapi_examples` (PER Path OPERATION)

TO SHOW MULTIPLE NAMED examples IN SWAGGER UI, USE `openapi_examples` ON `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` OR `File()` (`tutorial005_an_py310.py`):

```python
@app.put("/items/{item_id}")
async def update_item(
    *,
    item_id: int,
    item: Annotated[
        Item,
        Body(
            openapi_examples={
                "normal": {
                    "summary": "A normal example",
                    "description": "A **normal** item works correctly.",
                    "value": {
                        "name": "Foo",
                        "description": "A very nice Item",
                        "price": 35.4,
                        "tax": 3.2,
                    },
                },
                "converted": {
                    "summary": "An example with converted data",
                    "description": "FastAPI can convert price `strings` to actual `numbers` automatically",
                    "value": {
                        "name": "Bar",
                        "price": "35.4",
                    },
                },
                "invalid": {
                    "summary": "Invalid data is rejected with an error",
                    "value": {
                        "name": "Baz",
                        "price": "thirty five point four",
                    },
                },
            },
        ),
    ],
):
    ...
```

KEYS IDENTIFY examples; EACH value MAY CONTAIN `summary`, `description` (MARKDOWN), `value` OR `externalValue` (A URL; LESS WIDELY SUPPORTED). THESE GO IN OpenAPI OPERATION MEDIA-TYPE `examples`, NOT JSON SCHEMA; SWAGGER UI SHOWS THEM IN A DROPDOWN.

RULE OF THUMB: USE `Field(examples=...)` / `json_schema_extra` TO DOCUMENT MODELS; USE `openapi_examples` FOR SELECTABLE DOCS UI examples ON A SPECIFIC ENDPOINT.

H2: binary data IN JSON: BASE64
JSON CONTAINS TEXT ONLY; RAW bytes CANNOT BE SENT DIRECTLY.
IF binary data MUST BE INCLUDED IN JSON: BASE64-ENCODE IT.
OTHERWISE, PREFER [File UPLOADS](forms-and-files.md) AND `FileResponse`
([CUSTOM RESPONSES](../responses/custom-responses.md)); MORE EFFICIENT.

CONFIGURE `bytes` FIELDS WITH PYDANTIC MODEL CONFIG
(`docs_src/json_base64_bytes/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from pydantic import BaseModel


class DataInput(BaseModel):
    description: str
    data: bytes

    model_config = {"val_json_bytes": "base64"}


class DataOutput(BaseModel):
    description: str
    data: bytes

    model_config = {"ser_json_bytes": "base64"}


class DataInputOutput(BaseModel):
    description: str
    data: bytes

    model_config = {
        "val_json_bytes": "base64",
        "ser_json_bytes": "base64",
    }


app = FastAPI()


@app.post("/data")
def post_data(body: DataInput):
    content = body.data.decode("utf-8")
    return {"description": body.description, "content": content}


@app.get("/data")
def get_data() -> DataOutput:
    data = "hello".encode("utf-8")
    return DataOutput(description="A plumbus", data=data)


@app.post("/data-in-out")
def post_data_in_out(body: DataInputOutput) -> DataInputOutput:
    return body
```

- `val_json_bytes="base64"` — VALIDATION: DECODE BASE64 STRINGS FROM
  INPUT JSON INTO `bytes`. SENDING `{"description": "Some data", "data": "aGVsbG8="}`
  YIELDS `b"hello"`.
- `ser_json_bytes="base64"` — SERIALIZATION: ENCODE `bytes` AS BASE64
  IN JSON OUTPUT.
- DOCS SHOW `data` EXPECTS BASE64-ENCODED bytes.

H2: RELATED

- [REQUEST Body, Body FIELDS AND NESTED MODELS](request-body.md)
- [Query PARAMETERS](Query-parameters.md)
- [EXTENDING OpenAPI](../OpenAPI/extending-openapi.md) — RESPONSE examples
