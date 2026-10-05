---
type: guide
title: Streaming Data, JSON Lines and Server-Sent Events
description: Stream responses from generator path operations — JSON Lines (application/jsonl) with validated AsyncIterable[Item] items, raw strings/bytes with response_class=StreamingResponse (and custom media types), and Server-Sent Events with EventSourceResponse and ServerSentEvent, including keep-alive pings and Last-Event-ID resumption.
tags: [streaming, json-lines, jsonl, streamingresponse, sse, server-sent-events, eventsourceresponse, generators]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-7ef5e225e94efa405ccd4998
    resource: repo://docs_src/server_sent_events/tutorial002_py310.py
  - id: openwiki-source-d0a7169137b7575f04fe8310
    resource: repo://docs_src/server_sent_events/tutorial003_py310.py
  - id: openwiki-source-03c7eeed9cd7bc878db02f6d
    resource: repo://docs_src/server_sent_events/tutorial004_py310.py
  - id: openwiki-source-1e32b4cd71cd15a21451ab9d
    resource: repo://docs_src/server_sent_events/tutorial005_py310.py
  - id: openwiki-source-481390bf0862e75b1d4c72d0
    resource: repo://docs_src/stream_data/tutorial002_py310.py
  - id: openwiki-source-fca106e55b1d7cb389fb5404
    resource: repo://docs_src/stream_json_lines/tutorial001_py310.py
  - id: openwiki-source-592c13219fc35822c44debb9
    resource: repo://docs/en/docs/advanced/stream-data.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-5f184d86bf5894d37c0be2ca
    resource: repo://fastapi/sse.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Streaming Data, JSON Lines and Server-Sent Events

Streaming sends data to the client **as it's produced**, without waiting for the full result — useful for AI/LLM output, logs, progress updates, large files, or long lists. In FastAPI you stream by writing the path operation as a **generator**: use `yield` instead of `return`. The `response_class` and the return annotation decide the format.

| Format | How | Content type |
|--------|-----|--------------|
| JSON Lines | generator, default response class | `application/jsonl` |
| Raw text/bytes | generator + `response_class=StreamingResponse` (or a subclass) | none by default / subclass `media_type` |
| Server-Sent Events | generator + `response_class=EventSourceResponse` | `text/event-stream` |

Both `async def` (annotate `AsyncIterable[T]`) and plain `def` generators (annotate `Iterable[T]`) work; sync generators are iterated in a threadpool.

## JSON Lines

JSON Lines is one JSON object per line, separated by newlines — like a JSON array without `[` `]` and commas, so clients can process each line as it arrives:

```
{"name": "Plumbus", "description": "A multi-purpose household device."}
{"name": "Portal Gun", "description": "A portal opening device."}
```

`docs_src/stream_json_lines/tutorial001_py310.py`:

```python
from collections.abc import AsyncIterable, Iterable

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None


items = [
    Item(name="Plumbus", description="A multi-purpose household device."),
    Item(name="Portal Gun", description="A portal opening device."),
    Item(name="Meeseeks Box", description="A box that summons a Meeseeks."),
]


@app.get("/items/stream")
async def stream_items() -> AsyncIterable[Item]:
    for item in items:
        yield item


@app.get("/items/stream-no-async")
def stream_items_no_async() -> Iterable[Item]:
    for item in items:
        yield item
```

With an item type in the annotation (`AsyncIterable[Item]` / `Iterable[Item]`), FastAPI extracts `Item` as the **stream item type** and, for each yielded value, **validates**, **filters** and **serializes** it with Pydantic (in Rust — fast), honoring `response_model_*` options; a bad item raises `ResponseValidationError`. The item schema is documented in OpenAPI. Without an annotation, items are converted with `jsonable_encoder` + `json.dumps` instead (slower, no validation). The response is a `StreamingResponse` with `media_type="application/jsonl"`; headers set on an injected `Response` parameter are copied to it.

## Raw strings and bytes: `StreamingResponse`

To stream non-JSON content, set `response_class=StreamingResponse`; each yielded chunk is passed through **as is** (`docs_src/stream_data/tutorial001_py310.py`):

```python
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.get("/story/stream", response_class=StreamingResponse)
async def stream_story() -> AsyncIterable[str]:
    for line in message.splitlines():
        yield line


@app.get("/story/stream-bytes", response_class=StreamingResponse)
async def stream_story_bytes() -> AsyncIterable[bytes]:
    for line in message.splitlines():
        yield line.encode("utf-8")
```

Here the annotation is only for your editor — FastAPI doesn't convert or validate the chunks. You're responsible for encoding (and for adding newlines if the client expects them). For async generators, FastAPI yields control between chunks (`anyio.sleep(0)`) so client disconnects can cancel the stream.

### Setting the content type

Plain `StreamingResponse` sends no `Content-Type`. Subclass it with a `media_type` (`docs_src/stream_data/tutorial002_py310.py`):

```python
from collections.abc import AsyncIterable, Iterable
from io import BytesIO

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


class PNGStreamingResponse(StreamingResponse):
    media_type = "image/png"


@app.get("/image/stream", response_class=PNGStreamingResponse)
async def stream_image() -> AsyncIterable[bytes]:
    with read_image() as image_file:
        for chunk in image_file:
            yield chunk


@app.get("/image/stream-no-async-yield-from", response_class=PNGStreamingResponse)
def stream_image_no_async_yield_from() -> Iterable[bytes]:
    with read_image() as image_file:
        yield from image_file
```

The `with` block closes the file after the generator finishes. Regular file objects are blocking, so a plain `def` generator (run in a threadpool) is often the right choice for files; for whole files on disk, `FileResponse` is simpler ([Custom Responses](custom-responses.md)). You can also still *return* a `StreamingResponse(generator, media_type=...)` instance.

## Server-Sent Events (SSE)

SSE uses the `text/event-stream` format, supported natively by browsers through the `EventSource` API (automatic reconnection included). Each event is a small text block with fields `data`, `event`, `id`, `retry`, separated by blank lines.

### Basic SSE

Import from `fastapi.sse` (`docs_src/server_sent_events/tutorial001_py310.py`):

```python
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None


@app.get("/items/stream", response_class=EventSourceResponse)
async def sse_items() -> AsyncIterable[Item]:
    for item in items:
        yield item
```

Each yielded item becomes an event whose `data` is the item's JSON (validated against `Item` when annotated). `def` + `Iterable[Item]` and unannotated variants work too.

### Controlling event fields: `ServerSentEvent`

Yield `ServerSentEvent` objects to set fields (`tutorial002_py310.py`):

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent


@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")
    for i, item in enumerate(items):
        yield ServerSentEvent(data=item, event="item_update", id=str(i + 1), retry=5000)
```

`ServerSentEvent` fields:

| Field | Meaning |
|-------|---------|
| `data` | Payload, JSON-encoded (Pydantic models via `model_dump_json()`) |
| `raw_data` | Payload sent as-is, without JSON encoding (mutually exclusive with `data`) |
| `event` | Event type name (client listens with `addEventListener(name, ...)`); single line |
| `id` | Event ID, sent back by the browser as `Last-Event-ID` on reconnect |
| `retry` | Reconnection delay in milliseconds |
| `comment` | A `:` comment line, ignored by `EventSource` (e.g. pings) |

Items that are `ServerSentEvent` skip stream-item validation, so you can mix payload types.

Raw text, e.g. log lines (`tutorial003_py310.py`):

```python
yield ServerSentEvent(raw_data=log_line)
```

### Resuming with `Last-Event-ID`

On reconnect the browser sends the last received `id` in the `Last-Event-ID` header; read it as a normal header parameter and resume (`tutorial004_py310.py`):

```python
@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items(
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    start = last_event_id + 1 if last_event_id is not None else 0
    for i, item in enumerate(items):
        if i < start:
            continue
        yield ServerSentEvent(data=item, id=str(i))
```

### SSE over POST

Any method works — useful for protocols like MCP, or chat-style streaming with a request body (`tutorial005_py310.py`):

```python
class Prompt(BaseModel):
    text: str


@app.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    words = prompt.text.split()
    for word in words:
        yield ServerSentEvent(data=word, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")
```

(The browser `EventSource` API only does `GET`; use `fetch()` streaming or an SSE client library for `POST`.)

### What FastAPI handles for you

- Sends a keep-alive `: ping` comment every **15 seconds** when the generator is idle, so proxies don't close the connection.
- Sets `Cache-Control: no-cache` to prevent caching of the stream.
- Sets `X-Accel-Buffering: no` to prevent buffering in proxies like Nginx.

## Streaming, dependencies and background tasks

`yield` dependencies with the default request scope are torn down **after** the stream finishes, so a DB session can be used while streaming. If a dependency only needed the resource briefly, close it early or use `Depends(scope="function")` ([Advanced Dependencies](../dependencies/advanced-dependencies.md)).

## Related

- [Custom Responses](custom-responses.md) — `StreamingResponse`, `FileResponse`
- [WebSockets](../integrations/websockets.md) — bidirectional real-time communication
- [Response Models](../models/response-model.md)
