---
Type: guide
title: Custom responses and Returning responses Directly
description: Return Response objects directly, choose Response classes (JSONResponse, HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse, FileResponse) with response_class or default_response_class, write a custom Response subclass, and understand JSON performance and the deprecated ORJSONResponse/UJSONResponse.
tags: [responses, response_class, JSONResponse, HTMLResponse, RedirectResponse, FileResponse, StreamingResponse, default_response_class]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-c6a3b927a5b8ad24f873613c
    resource: repo://docs_src/custom_response/tutorial002_py310.py
  - id: openwiki-source-7eb058c6f5a7bdc244406ef4
    resource: repo://docs_src/custom_response/tutorial006b_py310.py
  - id: openwiki-source-ba8376ff7c7dc5c7135f3878
    resource: repo://docs_src/custom_response/tutorial009b_py310.py
  - id: openwiki-source-424afaf5d76185f840bc73d0
    resource: repo://docs_src/custom_response/tutorial009c_py310.py
  - id: openwiki-source-2efc19b1027a5823104316e7
    resource: repo://docs_src/custom_response/tutorial010_py310.py
  - id: openwiki-source-cc84216e9a97bdb96850505d
    resource: repo://docs_src/response_directly/tutorial001_py310.py
  - id: openwiki-source-dd715a8bda39f15c790f4edf
    resource: repo://docs/en/docs/advanced/custom-response.md
  - id: openwiki-source-6cd3cf9a04dba542dc04fb1e
    resource: repo://fastapi/responses.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Custom responses and Returning responses Directly

DEFAULT: FASTAPI TAKES RETURN VALUE, CONVERTS TO JSON VIA Response MODEL
OR `jsonable_encoder`, THEN SENDS AS `application/json`.
ALTERNATIVE: RETURN `Response` YOURSELF OR CHOOSE DIFFERENT Response CLASS.

`fastapi.responses` RE-EXPORTS STARLETTE'S `Response`, `JSONResponse`,
`HTMLResponse`, `PlainTextResponse`, `RedirectResponse`, `StreamingResponse`,
AND `FileResponse`; ALSO FASTAPI'S `EventSourceResponse`.
SEE [STREAMING AND SSE](streaming-and-sse.md).
`Response` ALSO IMPORTABLE FROM `fastapi`.

H2: Returning a `Response` directly

ANY `Response` INSTANCE OR SUBCLASS SENDS **AS IS**:
NO VALIDATION, Response-MODEL FILTERING, OR CONVERSION
(`docs_src/response_directly/tutorial001_py310.py`):

```python
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Item(BaseModel):
    title: str
    timestamp: datetime
    description: str | None = None


app = FastAPI()


@app.put("/items/{id}")
def update_item(id: str, item: Item):
    json_compatible_item_data = jsonable_encoder(item)
    return JSONResponse(content=json_compatible_item_data)
```

NO AUTOMATIC CONVERSION; ENSURE CONTENT IS SERIALIZABLE.
HERE, `jsonable_encoder` FIRST CONVERTS `datetime` TO STRING.

ANY CONTENT Type WORKS, e.g. XML (`tutorial002_py310.py`):

```python
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/legacy/")
def get_legacy_data():
    data = """<?xml version="1.0"?>
    <shampoo>
    <Header>
        Apply shampoo here.
    </Header>
    <Body>
        You'll have to use soap here.
    </Body>
    </shampoo>
    """
    return Response(content=data, media_type="application/xml")
```

`Response(content, status_code=200, headers=None, media_type=None)`:
FASTAPI/STARLETTE ADD `Content-Length`; FOR text TYPES, ADD CHARSET TO
`Content-Type`.

USE DIRECT responses FOR CUSTOM STATUS CODES
([Response STATUS CODES](status-codes.md)), headers/COOKIES
([Response headers AND COOKIES](Response-headers-and-cookies.md)), OR
NON-JSON CONTENT.
NOTE: DIRECT `Response` RETURN MEANS OpenAPI DOES NOT KNOW ITS SHAPE.
DOCUMENT WITH `response_class` AND/OR `responses=`
([EXTENDING OpenAPI](../OpenAPI/extending-openapi.md)).

H2: `response_class`

DECORATOR'S `response_class` SPECIFIES CLASS FOR RETURNED CONTENT AND
DOCUMENTS MEDIA Type IN OpenAPI:

```python
from fastapi.responses import HTMLResponse


@app.get("/items/", response_class=HTMLResponse)
async def read_items():
    return """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Look ma! HTML!</h1>
        </body>
    </html>
    """
```

(`docs_src/custom_response/tutorial002_py310.py`.)
ALTERNATIVE: RETURN `HTMLResponse(...)` INSTANCE DIRECTLY (`tutorial003`).
IT WORKS, BUT OpenAPI SHOWS JSON.
COMBINE `response_class=HTMLResponse` WITH Response RETURNED FROM HELPER
(`tutorial004`) FOR CORRECT DOCS AND FULL CONTROL.

H2: Available Response classes

| Class | Use | Example |
|-------|-----|---------|
| `Response` | BASE CLASS; ANY CONTENT AND `media_type` | XML ABOVE |
| `JSONResponse` | JSON (`json` STDLIB); CLASSIC DEFAULT | `JSONResponse(content={...}, status_code=201)` |
| `HTMLResponse` | `text/html` | ABOVE |
| `PlainTextResponse` | `text/plain` | `@app.get("/", response_class=PlainTextResponse)` RETURNING `"Hello World"` (`tutorial005`) |
| `RedirectResponse` | HTTP REDIRECT; DEFAULT **307** | BELOW |
| `StreamingResponse` | STREAM FROM (ASYNC) ITERATOR | BELOW |
| `FileResponse` | STREAM FILE ASYNCHRONOUSLY | BELOW |
| `EventSourceResponse` | SERVER-SENT EVENTS | [STREAMING AND SSE](streaming-and-sse.md) |

H3: `RedirectResponse`

```python
@app.get("/typer")
async def redirect_typer():
    return RedirectResponse("https://typer.tiangolo.com")


@app.get("/fastapi", response_class=RedirectResponse)
async def redirect_fastapi():
    return "https://fastapi.tiangolo.com"


@app.get("/pydantic", response_class=RedirectResponse, status_code=302)
async def redirect_pydantic():
    return "https://docs.pydantic.dev/"
```

(`tutorial006`, `006b`, `006c`.)
WITH `response_class=RedirectResponse`, RETURN URL ALONE;
`status_code` OVERRIDES DEFAULT 307.

H3: `StreamingResponse`

```python
import anyio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


async def fake_video_streamer():
    for i in range(10):
        yield b"some fake video bytes"
        await anyio.sleep(0)


@app.get("/")
async def main():
    return StreamingResponse(fake_video_streamer())
```

(`tutorial007`.)
STREAM FILE-LIKE OBJECT WITH SYNC GENERATOR (`tutorial008`):

```python
@app.get("/")
def main():
    def iterfile():
        with open(some_file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="video/mp4")
```
MORE STREAMING PATTERNS (INCLUDING GENERATOR ENDPOINTS AND JSON LINES):
SEE [STREAMING DATA, JSON LINES AND SERVER-SENT EVENTS](streaming-and-sse.md).
H3: `FileResponse`
```python
from fastapi.responses import FileResponse

some_file_path = "large-video-file.mp4"


@app.get("/")
async def main():
    return FileResponse(some_file_path)


@app.get("/", response_class=FileResponse)   # tutorial009b: return just the path
async def main():
    return some_file_path
```
ARGUMENTS: `path`, `headers`, `media_type` (GUESSED FROM filename IF OMITTED),
`filename` (SETS `Content-Disposition` SO BROWSERS DOWNLOAD FILE).
SETS `Content-Length`, `Last-Modified` ∧ `ETag`.
H2: CUSTOM Response CLASSES
SUBCLASS `Response`; IMPLEMENT `render(content) -> bytes` (`tutorial009c_py310.py`):
```python
from typing import Any

import orjson
from fastapi import FastAPI, Response

app = FastAPI()


class CustomORJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        assert orjson is not None, "orjson must be installed"
        return orjson.dumps(content, option=orjson.OPT_INDENT_2)


@app.get("/", response_class=CustomORJSONResponse)
async def main():
    return {"message": "Hello World"}
```
H2: DEFAULT Response CLASS
SET CLASS FOR EVERY path OPERATION WITH `default_response_class`
(ALSO ON `APIRouter` / `include_router`) (`tutorial010_py310.py`):
```python
app = FastAPI(default_response_class=HTMLResponse)


@app.get("/items/")
async def read_items():
    return "<h1>Items</h1><p>This is a list of items.</p>"
```
INDIVIDUAL OPERATIONS CAN STILL OVERRIDE WITH `response_class`.
H2: JSON PERFORMANCE
- WITH A **Response MODEL / RETURN Type AND NO `response_class`**:
  FASTAPI VALIDATES WITH PYDANTIC ∧ SERIALIZES DIRECTLY TO JSON bytes
  (PYDANTIC'S RUST CORE); RETURNS `application/json` Response WITHOUT
  INTERMEDIATE `jsonable_encoder` + `json.dumps` STEPS. FASTEST OPTION.
- WITH `response_class=JSONResponse` (OR ANOTHER JSON CLASS):
  Response MODEL STILL FILTERS DATA; THEN `jsonable_encoder` CONVERTS IT
  ∧ THAT CLASS SERIALIZES IT. SLOWER.
∴ `ORJSONResponse` ∧ `UJSONResponse` ARE **DEPRECATED**
(THEY EMIT A `FastAPIDeprecationWarning`): Response MODEL GIVES SAME
RUST-LEVEL SPEED WITHOUT EXTRA PACKAGES.
EXISTING CODE USING THEM STILL WORKS IF `orjson` / `ujson` IS INSTALLED
(`tutorial001`, `tutorial001b`).
H2: RELATED
- [Response MODELS AND RETURN TYPES](../models/Response-model.md)
- [STATIC FILES, TEMPLATES AND FRONTENDS](../app-structure/static-files-templates-and-frontend.md)
  — `TemplateResponse`
- [BACKGROUND TASKS](../integrations/background-tasks.md)
  — TASKS ATTACHED TO RETURNED responses
