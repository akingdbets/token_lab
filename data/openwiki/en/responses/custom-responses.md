---
type: guide
title: Custom Responses and Returning Responses Directly
description: Return Response objects directly, choose response classes (JSONResponse, HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse, FileResponse) with response_class or default_response_class, write a custom Response subclass, and understand JSON performance and the deprecated ORJSONResponse/UJSONResponse.
tags: [responses, response_class, jsonresponse, htmlresponse, redirectresponse, fileresponse, streamingresponse, default_response_class]
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

# Custom Responses and Returning Responses Directly

By default FastAPI takes whatever you return, converts it to JSON (via your response model, or `jsonable_encoder`) and sends it as `application/json`. You can instead return a `Response` yourself or pick a different response class.

`fastapi.responses` re-exports Starlette's `Response`, `JSONResponse`, `HTMLResponse`, `PlainTextResponse`, `RedirectResponse`, `StreamingResponse` and `FileResponse`, plus FastAPI's own `EventSourceResponse` (see [Streaming and SSE](streaming-and-sse.md)). `Response` is also importable from `fastapi`.

## Returning a `Response` directly

Any instance of `Response` (or a subclass) is sent **as is** — no validation, no response-model filtering, no conversion (`docs_src/response_directly/tutorial001_py310.py`):

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

Because nothing is converted for you, make sure the content is serializable — here `jsonable_encoder` turns the `datetime` into a string first.

Any content type works, e.g. XML (`tutorial002_py310.py`):

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

`Response(content, status_code=200, headers=None, media_type=None)` — FastAPI/Starlette add `Content-Length` and, for text types, the charset in `Content-Type`.

Use direct responses for custom status codes ([Response Status Codes](status-codes.md)), headers/cookies ([Response Headers and Cookies](response-headers-and-cookies.md)), or non-JSON content. Note: if you return a `Response` directly, the OpenAPI docs won't know its shape — document it with `response_class` and/or `responses=` ([Extending OpenAPI](../openapi/extending-openapi.md)).

## `response_class`

`response_class` on the decorator tells FastAPI which class to use for the returned content **and** documents the media type in OpenAPI:

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

(`docs_src/custom_response/tutorial002_py310.py`.) If you return an `HTMLResponse(...)` instance directly instead (`tutorial003`), it works but OpenAPI shows JSON; combining both — `response_class=HTMLResponse` plus returning a response from a helper (`tutorial004`) — gives correct docs and full control.

## Available response classes

| Class | Use | Example |
|-------|-----|---------|
| `Response` | Base class; any content and `media_type` | XML above |
| `JSONResponse` | JSON (stdlib `json`); the classic default | `JSONResponse(content={...}, status_code=201)` |
| `HTMLResponse` | `text/html` | above |
| `PlainTextResponse` | `text/plain` | `@app.get("/", response_class=PlainTextResponse)` returning `"Hello World"` (`tutorial005`) |
| `RedirectResponse` | HTTP redirect, default **307** | see below |
| `StreamingResponse` | Stream from an (async) iterator | see below |
| `FileResponse` | Stream a file asynchronously | see below |
| `EventSourceResponse` | Server-Sent Events | [Streaming and SSE](streaming-and-sse.md) |

### `RedirectResponse`

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

(`tutorial006`, `006b`, `006c`.) With `response_class=RedirectResponse` you can return just the URL; `status_code` overrides the default 307.

### `StreamingResponse`

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

(`tutorial007`.) Streaming a file-like object with a sync generator (`tutorial008`):

```python
@app.get("/")
def main():
    def iterfile():
        with open(some_file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="video/mp4")
```

For more streaming patterns (including generator endpoints and JSON Lines) see [Streaming Data, JSON Lines and Server-Sent Events](streaming-and-sse.md).

### `FileResponse`

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

Arguments: `path`, `headers`, `media_type` (guessed from the filename if omitted), `filename` (sets `Content-Disposition` so browsers download it). It sets `Content-Length`, `Last-Modified` and `ETag`.

## Custom response classes

Subclass `Response` and implement `render(content) -> bytes` (`tutorial009c_py310.py`):

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

## Default response class

Set the class for every path operation with `default_response_class` (also on `APIRouter` / `include_router`) (`tutorial010_py310.py`):

```python
app = FastAPI(default_response_class=HTMLResponse)


@app.get("/items/")
async def read_items():
    return "<h1>Items</h1><p>This is a list of items.</p>"
```

Individual operations can still override it with `response_class`.

## JSON performance

- With a **response model / return type and no `response_class`**, FastAPI validates with Pydantic and serializes **directly to JSON bytes** (Pydantic's Rust core), returning an `application/json` response without the intermediate `jsonable_encoder` + `json.dumps` steps. This is the fastest option.
- With `response_class=JSONResponse` (or another JSON class), the data is still filtered by the response model, but then converted with `jsonable_encoder` and serialized by that class — slower.

Consequently, `ORJSONResponse` and `UJSONResponse` are **deprecated** (they emit a `FastAPIDeprecationWarning`): a response model gives the same Rust-level speed without extra packages. Existing code using them still works if `orjson`/`ujson` is installed (`tutorial001`, `tutorial001b`).

## Related

- [Response Models and Return Types](../models/response-model.md)
- [Static Files, Templates and Frontends](../app-structure/static-files-templates-and-frontend.md) — `TemplateResponse`
- [Background Tasks](../integrations/background-tasks.md) — tasks attached to returned responses
