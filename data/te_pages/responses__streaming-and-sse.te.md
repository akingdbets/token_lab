---
Type: guide
title: Streaming data, JSON Lines and Server-Sent Events
description: stream responses from generator path operations — JSON Lines (application/jsonl) with validated AsyncIterable[Item] items, raw strings/bytes with response_class=StreamingResponse (and custom media types), and Server-Sent Events with EventSourceResponse and ServerSentEvent, including keep-alive pings and Last-Event-ID resumption.
tags: [streaming, JSON-lines, jsonl, StreamingResponse, SSE, server-sent-events, EventSourceResponse, generators]
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
    resource: repo://FastAPI/routing.py
  - id: openwiki-source-5f184d86bf5894d37c0be2ca
    resource: repo://FastAPI/sse.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: STREAMING data, JSON LINES AND SERVER-SENT EVENTS

stream data TO CLIENT AS PRODUCED; no WAIT FOR FULL RESULT.
USE CASES: AI/LLM OUTPUT, LOGS, PROGRESS UPDATES, LARGE FILES, LONG LISTS.
FastAPI STREAMING: WRITE PATH OPERATION AS generator; USE `yield`, NOT `return`.
FORMAT Depends ON `response_class` AND return ANNOTATION.

| FORMAT | METHOD | Content Type |
|---|---|---|
| JSON LINES | generator; DEFAULT Response CLASS | `application/jsonl` |
| RAW text/BYTES | generator + `response_class=StreamingResponse` OR SUBCLASS | NONE BY DEFAULT; SUBCLASS `media_type` |
| SERVER-SENT EVENTS | generator + `response_class=EventSourceResponse` | `text/event-stream` |

BOTH `async def` GENERATORS (ANNOTATE `AsyncIterable[T]`) AND PLAIN `def`
GENERATORS (ANNOTATE `Iterable[T]`) WORK.
SYNC GENERATORS ARE ITERATED IN A THREADPOOL.

H2: JSON LINES

JSON LINES: ONE JSON OBJECT PER LINE, SEPARATED BY NEWLINES.
LIKE JSON ARRAY WITHOUT `[` `]` OR COMMAS; CLIENTS PROCESS EACH LINE AS IT ARRIVES:

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

with Item Type IN ANNOTATION (`AsyncIterable[Item]` / `Iterable[Item]`),
FastAPI EXTRACTS `Item` AS stream Item Type.
FOR EACH YIELDED VALUE, FastAPI VALIDATES, FILTERS AND SERIALIZES with PYDANTIC
(IN RUST — FAST); HONORS `response_model_*` OPTIONS.
BAD Item → `ResponseValidationError`.
Item SCHEMA DOCUMENTED IN OpenAPI.

WITHOUT ANNOTATION, ITEMS USE `jsonable_encoder` + `json.dumps` INSTEAD:
SLOWER; no VALIDATION.
Response: `StreamingResponse` with `media_type="application/jsonl"`.
HEADERS SET ON INJECTED `Response` PARAMETER ARE COPIED TO IT.

H2: RAW STRINGS AND BYTES: `StreamingResponse`

FOR NON-JSON Content, SET `response_class=StreamingResponse`.
EACH YIELDED CHUNK PASSES THROUGH AS IS
(`docs_src/stream_data/tutorial001_py310.py`):

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

ANNOTATION IS FOR YOUR EDITOR ONLY; FastAPI DOES NOT CONVERT OR VALIDATE
CHUNKS.
YOU HANDLE ENCODING AND ADD NEWLINES IF CLIENT EXPECTS THEM.
async GENERATORS yield Control BETWEEN CHUNKS (`anyio.sleep(0)`),
ALLOWING CLIENT DISCONNECTS TO CANCEL THE stream.

H3: SETTING THE Content Type

PLAIN `StreamingResponse` SENDS no `Content-Type`.
SUBCLASS IT with A `media_type`
(`docs_src/stream_data/tutorial002_py310.py`):

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

`with` BLOCK CLOSES FILE AFTER generator FINISHES.
REGULAR FILE OBJECTS BLOCK; PLAIN `def` generator (RUN IN THREADPOOL)
OFTEN SUITS FILES.
FOR WHOLE FILES ON DISK, `FileResponse` IS SIMPLER
([Custom Responses](custom-responses.md)).
YOU CAN ALSO `return` A `StreamingResponse(generator, media_type=...)` INSTANCE.

H2: SERVER-SENT EVENTS (SSE)
SSE USES `text/event-stream`; BROWSERS NATIVELY SUPPORT IT VIA `EventSource`
API, INCLUDING AUTOMATIC RECONNECTION.
EACH EVENT: SMALL text BLOCK; FIELDS `data`, `event`, `id`, `retry`
SEPARATED BY BLANK LINES.

H3: Basic SSE

IMPORT FROM `fastapi.sse` (`docs_src/server_sent_events/tutorial001_py310.py`):

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

EACH YIELDED Item BECOMES EVENT; `data` = Item JSON
(VALIDATED AGAINST `Item` WHEN ANNOTATED).
`def` + `Iterable[Item]` AND UNANNOTATED VARIANTS ALSO WORK.

H3: Controlling event fields: `ServerSentEvent`

yield `ServerSentEvent` OBJECTS TO SET FIELDS
(`tutorial002_py310.py`):

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent


@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")
    for i, item in enumerate(items):
        yield ServerSentEvent(data=item, event="item_update", id=str(i + 1), retry=5000)
```

`ServerSentEvent` FIELDS:

| FIELD | MEANING |
|-------|---------|
| `data` | PAYLOAD, JSON-ENCODED (PYDANTIC MODELS VIA `model_dump_json()`) |
| `raw_data` | PAYLOAD SENT AS-IS, WITHOUT JSON ENCODING; MUTUALLY EXCLUSIVE with `data` |
| `event` | EVENT Type name; CLIENT LISTENS VIA `addEventListener(name, ...)`; SINGLE LINE |
| `id` | EVENT ID; BROWSER SENDS IT BACK AS `Last-Event-ID` ON RECONNECT |
| `retry` | RECONNECTION DELAY IN MILLISECONDS |
| `comment` | `:` comment LINE; `EventSource` IGNORES IT (e.g. PINGS) |

`ServerSentEvent` ITEMS SKIP stream-Item VALIDATION; PAYLOAD TYPES
CAN BE MIXED.

RAW text, e.g. LOG LINES (`tutorial003_py310.py`):

```python
yield ServerSentEvent(raw_data=log_line)
```

H3: Resuming with `Last-Event-ID`

ON RECONNECT, BROWSER SENDS Last-RECEIVED `id` IN `Last-Event-ID`
HEADER; READ AS NORMAL HEADER PARAMETER AND RESUME
(`tutorial004_py310.py`):

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

H3: SSE over POST

ANY METHOD WORKS; USEFUL FOR PROTOCOLS LIKE MCP OR CHAT-STYLE
STREAMING with REQUEST BODY (`tutorial005_py310.py`):

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

BROWSER `EventSource` API ONLY USES `GET`; FOR `POST`, USE
`fetch()` STREAMING OR SSE CLIENT LIBRARY.

H3: What FastAPI handles for you

- SENDS KEEP-ALIVE `: ping` comment EVERY 15 seconds WHEN generator
  IDLE; PREVENTS PROXIES FROM CLOSING CONNECTION.
- SETS `Cache-Control: no-cache` TO PREVENT stream CACHING.
- SETS `X-Accel-Buffering: no` TO PREVENT Buffering IN PROXIES
  LIKE NGINX.

H2: Streaming, dependencies and background tasks

`yield` DEPENDENCIES with DEFAULT REQUEST scope ARE TORN DOWN AFTER
stream FINISHES; DB SESSION CAN BE USED WHILE STREAMING.
IF DEPENDENCY RESOURCE IS NEEDED ONLY BRIEFLY, CLOSE IT EARLY OR USE
`Depends(scope="function")`
([Advanced Dependencies](../dependencies/advanced-dependencies.md)).

H2: Related

- [CUSTOM RESPONSES](custom-responses.md) — `StreamingResponse`,
  `FileResponse`
- [WebSockets](../integrations/websockets.md) — BIDIRECTIONAL
  REAL-TIME COMMUNICATION
- [Response MODELS](../models/Response-model.md)
