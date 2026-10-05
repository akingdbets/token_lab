---
type: guide
title: Extra Data Types, Schema Examples and Base64 Bytes
description: Use UUID, datetime, date, time, timedelta, frozenset, bytes, Decimal and other Pydantic types in parameters and bodies; declare request examples with json_schema_extra, Field(examples), Body(examples) and openapi_examples; send binary data in JSON as base64 with val_json_bytes / ser_json_bytes.
tags: [data-types, uuid, datetime, decimal, examples, openapi_examples, json_schema_extra, base64, bytes]
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
    resource: repo://docs/en/docs/advanced/json-base64-bytes.md
  - id: openwiki-source-b9633307ba09f9f9d701465c
    resource: repo://docs/en/docs/tutorial/extra-data-types.md
  - id: openwiki-source-106f497dd08938cd7251aaf0
    resource: repo://docs/en/docs/tutorial/schema-extra-example.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Extra Data Types, Schema Examples and Base64 Bytes

## Extra data types

Beyond `int`, `float`, `str` and `bool`, any Pydantic-supported type works in path/query/header/cookie parameters, bodies and responses — with the same conversion, validation and documentation.

| Python type | JSON representation |
|-------------|---------------------|
| `uuid.UUID` | `str` |
| `datetime.datetime` | ISO 8601 `str`, e.g. `2008-09-15T15:53:00+05:00` |
| `datetime.date` | ISO 8601 `str`, e.g. `2008-09-15` |
| `datetime.time` | ISO 8601 `str`, e.g. `14:23:55.003` |
| `datetime.timedelta` | `float` of total seconds (Pydantic can also use ISO 8601 durations) |
| `frozenset` / `set` | request: a list, de-duplicated; response: a list; schema has `uniqueItems` |
| `bytes` | `str` (schema format `binary`) |
| `decimal.Decimal` | handled like `float` |

See Pydantic's types documentation for the full list (e.g. `EmailStr`, `HttpUrl`, constrained types).

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

Inside the function the values are real Python objects (you can do datetime arithmetic); in the response they're converted back to JSON (see `jsonable_encoder` in [Extra Models](../models/extra-models-and-updates.md)).

## Declaring request examples

Examples appear in the docs UI and help clients. There are two different mechanisms.

### 1. JSON Schema `examples` (inside the model's schema)

**In the model config** (`docs_src/schema_extra_example/tutorial001_py310.py`):

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

`json_schema_extra` can add any extra JSON Schema info (e.g. metadata for a frontend).

**Per field** with `Field(examples=[...])` (`tutorial002_py310.py`):

```python
from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str = Field(examples=["Foo"])
    description: str | None = Field(default=None, examples=["A very nice Item"])
    price: float = Field(examples=[35.4])
    tax: float | None = Field(default=None, examples=[3.2])
```

**Per parameter** — `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` and `File()` accept `examples=[...]` (`tutorial003_an_py310.py`):

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

You can pass several examples (`tutorial004_an_py310.py`), but Swagger UI currently shows only one example from JSON Schema `examples`.

`examples` (a list) is the JSON Schema standard keyword, supported since OpenAPI 3.1.0 (FastAPI ≥ 0.99.0). The single `example` keyword still works but is deprecated — migrate to `examples`.

### 2. OpenAPI-specific `openapi_examples` (per path operation)

To show **multiple named examples** in Swagger UI, use `openapi_examples` on `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` or `File()` (`tutorial005_an_py310.py`):

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

Keys identify each example; each value may have `summary`, `description` (Markdown), `value`, or `externalValue` (a URL; less widely supported). These go into the OpenAPI operation's media-type `examples`, not the JSON Schema, and Swagger UI shows them in a dropdown.

**Rule of thumb:** use `Field(examples=...)` / `json_schema_extra` to document *models*; use `openapi_examples` when you want selectable examples in the docs UI for a specific endpoint.

## Binary data in JSON: base64

JSON can only contain text, so raw bytes can't be sent directly. If you **must** include binary data in JSON, encode it as base64 — otherwise prefer [file uploads](forms-and-files.md) and `FileResponse` ([Custom Responses](../responses/custom-responses.md)), which are more efficient.

Configure `bytes` fields with Pydantic model config (`docs_src/json_base64_bytes/tutorial001_py310.py`):

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

- `val_json_bytes="base64"` — *validation*: decode base64 strings from input JSON into `bytes`. Sending `{"description": "Some data", "data": "aGVsbG8="}` yields `b"hello"`.
- `ser_json_bytes="base64"` — *serialization*: encode `bytes` as base64 in JSON output.
- The docs show that `data` expects base64-encoded bytes.

## Related

- [Request Body, Body Fields and Nested Models](request-body.md)
- [Query Parameters](query-parameters.md)
- [Extending OpenAPI](../openapi/extending-openapi.md) — examples for responses
