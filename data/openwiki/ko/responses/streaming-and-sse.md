---
type: guide
title: 스트리밍, JSON Lines, Server-Sent Events
description: 경로 작업 함수에서 yield로 응답을 스트리밍하는 세 가지 방식—기본 JSON Lines(application/jsonl, AsyncIterable[Item] 반환 타입으로 검증·문서화), response_class=EventSourceResponse와 ServerSentEvent(data/raw_data/event/id/retry/comment)로 SSE, response_class=StreamingResponse로 원시 바이트/텍스트 스트림—과 Last-Event-ID 재개, POST SSE, keep-alive ping, 취소, 파일과 스레드풀을 설명한다.
tags: [streaming, json-lines, sse, server-sent-events, eventsourceresponse, streamingresponse]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-631f0a521279264c2caccf6d
    resource: repo://docs_src/server_sent_events/tutorial001_py310.py
  - id: openwiki-source-7ef5e225e94efa405ccd4998
    resource: repo://docs_src/server_sent_events/tutorial002_py310.py
  - id: openwiki-source-d0a7169137b7575f04fe8310
    resource: repo://docs_src/server_sent_events/tutorial003_py310.py
  - id: openwiki-source-03c7eeed9cd7bc878db02f6d
    resource: repo://docs_src/server_sent_events/tutorial004_py310.py
  - id: openwiki-source-1e32b4cd71cd15a21451ab9d
    resource: repo://docs_src/server_sent_events/tutorial005_py310.py
  - id: openwiki-source-efb72c0e6b6e9872345503e7
    resource: repo://docs_src/stream_data/tutorial001_py310.py
  - id: openwiki-source-481390bf0862e75b1d4c72d0
    resource: repo://docs_src/stream_data/tutorial002_py310.py
  - id: openwiki-source-fca106e55b1d7cb389fb5404
    resource: repo://docs_src/stream_json_lines/tutorial001_py310.py
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://fastapi/openapi/utils.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-5f184d86bf5894d37c0be2ca
    resource: repo://fastapi/sse.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 스트리밍, JSON Lines, Server-Sent Events

경로 작업 함수가 `return` 대신 **`yield`**를 쓰면(제너레이터), FastAPI는 응답을 스트리밍한다. 어떤 형식으로 스트리밍할지는 `response_class`로 정한다.

| `response_class` | 형식 | 데이터 처리 | 추가 버전 |
| --- | --- | --- | --- |
| 지정 안 함(기본) | **JSON Lines** (`application/jsonl`) | 각 항목을 JSON으로 직렬화(반환 타입 있으면 Pydantic 검증) | FastAPI 0.134.0 |
| `EventSourceResponse` | **Server-Sent Events** (`text/event-stream`) | 각 항목을 SSE 이벤트로 인코딩 | FastAPI 0.135.0 |
| `StreamingResponse`(또는 하위 클래스) | 원시 스트림 | 변환 없이 그대로 전송 | FastAPI 0.134.0 |

## 스트림이란

전체 응답이 준비되기 전에 데이터를 조금씩 보내기 시작하는 것이다. 첫 데이터를 보내면 클라이언트가 받아 처리하기 시작하고, 서버는 계속 다음 데이터를 만든다. 무한 스트림도 가능하다. 사용 사례: AI LLM 응답 스트리밍, 로그·관측 데이터 스트리밍, 진행 상황 전송 등.

## JSON Lines 스트리밍

JSON Lines는 한 줄에 하나의 JSON 객체를 보내는 형식이다(콘텐츠 타입 `application/jsonl`).

```
{"name": "Plumbus", "description": "A multi-purpose household device."}
{"name": "Portal Gun", "description": "A portal opening device."}
{"name": "Meeseeks Box", "description": "A box that summons a Meeseeks."}
```

```Python
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


@app.get("/items/stream-no-annotation")
async def stream_items_no_annotation():
    for item in items:
        yield item
```

- 반환 타입 `AsyncIterable[Item]`(또는 일반 `def`면 `Iterable[Item]`)을 선언하면 FastAPI가 각 항목을 **검증**하고, OpenAPI에 **문서화**(`application/jsonl`의 `itemSchema`)하고, **필터링**하며, Pydantic(Rust)으로 **직렬화**해 성능이 훨씬 좋다.
- 반환 타입을 생략하면 [`jsonable_encoder`](../models/body-updates-and-encoder.md)로 변환해 보낸다.
- 일반 `def` 제너레이터도 쓸 수 있다(FastAPI가 스레드풀에서 순회).
- async 제너레이터는 각 항목 뒤에 이벤트 루프에 제어를 넘겨(`anyio.sleep(0)`) 클라이언트 연결 종료 시 취소가 동작하게 한다.

## Server-Sent Events (SSE)

SSE는 브라우저 표준 `EventSource` API로 서버가 클라이언트에 이벤트를 푸시하는 방식이다. 각 이벤트는 `data`, `event`, `id`, `retry` 같은 "필드"를 가진 작은 텍스트 블록이며 빈 줄로 구분된다. 단방향 푸시라면 [WebSocket](../integrations/websockets.md)보다 단순하다.

```Python
from collections.abc import AsyncIterable, Iterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None


items = [...]


@app.get("/items/stream", response_class=EventSourceResponse)
async def sse_items() -> AsyncIterable[Item]:
    for item in items:
        yield item
```

- `EventSourceResponse`(`fastapi.sse`, `fastapi.responses`에서도 임포트 가능)는 `StreamingResponse`의 하위 클래스로 `media_type="text/event-stream"`을 설정하는 **표시(marker)** 역할을 하며, 실제 인코딩은 FastAPI 라우팅 계층이 한다.
- 반환 타입 `AsyncIterable[Item]`이 있으면 검증·문서화·Pydantic 직렬화가 적용된다. 일반 `def`(`Iterable[Item]`)나 반환 타입 생략도 가능하다.
- 일반 객체(dict, Pydantic 모델 등)를 yield하면 JSON으로 인코딩되어 `data:` 필드로 전송된다.

### ServerSentEvent로 필드 지정

`event`, `id`, `retry`, `comment`가 필요하면 `ServerSentEvent` 객체를 yield한다.

```Python
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


items = [
    Item(name="Plumbus", price=32.99),
    Item(name="Portal Gun", price=999.99),
    Item(name="Meeseeks Box", price=49.99),
]


@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")
    for i, item in enumerate(items):
        yield ServerSentEvent(data=item, event="item_update", id=str(i + 1), retry=5000)
```

| 필드 | 설명 |
| --- | --- |
| `data` | 이벤트 내용. Pydantic 모델·dict·list·문자열·숫자 등 JSON 직렬화 가능한 값이며 **항상 JSON으로 직렬화**된다(문자열 `"hello"`는 `data: "hello"`로 따옴표 포함) |
| `raw_data` | JSON 인코딩 **없이** 그대로 보낼 문자열. `data`와 **상호 배타** |
| `event` | 이벤트 타입 이름(한 줄이어야 함) |
| `id` | 이벤트 ID(한 줄, null 문자 불가) |
| `retry` | 재연결 대기 시간(밀리초, 0 이상) |
| `comment` | `:`로 시작하는 주석 줄 |

`event`/`id`에 줄바꿈이 있거나 `id`에 null 문자가 있으면 검증 오류가 난다. `ServerSentEvent`는 전송용 래퍼이므로 응답 데이터 모델 스키마에는 사용되지 않는다.

### raw_data: JSON 인코딩 없이 보내기

```Python
@app.get("/logs/stream", response_class=EventSourceResponse)
async def stream_logs() -> AsyncIterable[ServerSentEvent]:
    logs = [
        "2025-01-01 INFO  Application started",
        "2025-01-01 DEBUG Connected to database",
        "2025-01-01 WARN  High memory usage detected",
    ]
    for log_line in logs:
        yield ServerSentEvent(raw_data=log_line)
```

### Last-Event-ID로 재개

브라우저는 연결이 끊긴 뒤 재연결할 때 마지막으로 받은 `id`를 `Last-Event-ID` 헤더로 보낸다. 일반 헤더 파라미터로 읽어 이어서 보낸다.

```Python
from typing import Annotated

from fastapi import FastAPI, Header


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

`Header`의 밑줄→하이픈 변환으로 `last_event_id`가 `last-event-id` 헤더를 읽는다([헤더와 쿠키](../request/headers-and-cookies.md)).

### POST로 SSE

`EventSourceResponse`는 **모든 HTTP 메서드**에서 동작한다. [MCP](https://modelcontextprotocol.io)처럼 `POST`로 SSE를 스트리밍하는 프로토콜에 유용하다.

```Python
class Prompt(BaseModel):
    text: str


@app.post("/chat/stream", response_class=EventSourceResponse)
async def stream_chat(prompt: Prompt) -> AsyncIterable[ServerSentEvent]:
    words = prompt.text.split()
    for word in words:
        yield ServerSentEvent(data=word, event="token")
    yield ServerSentEvent(raw_data="[DONE]", event="done")
```

### SSE 기술적 세부

FastAPI는 SSE 스트림에 대해 자동으로:

- 메시지가 없을 때 **15초마다** keep-alive `ping` 주석(`: ping`)을 보내 일부 프록시가 연결을 끊지 않게 한다(HTML 명세 권장).
- `Cache-Control: no-cache` 헤더로 스트림 캐싱을 막는다.
- `X-Accel-Buffering: no` 헤더로 Nginx 같은 프록시의 버퍼링을 막는다.

일반 `def` 제너레이터는 스레드풀에서 순회된다.

## 원시 데이터 스트리밍: StreamingResponse + yield

`response_class=StreamingResponse`를 선언하면 `yield`로 각 데이터 조각을 보낼 수 있다. FastAPI는 각 조각을 **그대로** `StreamingResponse`에 넘기며 JSON 등으로 변환하지 않는다.

```Python
from collections.abc import AsyncIterable, Iterable

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

message = """
Rick: (stumbles in drunkenly, and turns on the lights) Morty! You gotta come on...
Morty: (rubs his eyes) What, Rick? What's going on?
"""


@app.get("/story/stream", response_class=StreamingResponse)
async def stream_story() -> AsyncIterable[str]:
    for line in message.splitlines():
        yield line


@app.get("/story/stream-bytes", response_class=StreamingResponse)
async def stream_story_bytes() -> AsyncIterable[bytes]:
    for line in message.splitlines():
        yield line.encode("utf-8")
```

- 데이터를 변환·직렬화하지 않으므로 타입 주석은 에디터와 도구용일 뿐 FastAPI는 사용하지 않는다. 바이트를 정확히 원하는 대로 만들어 보낼 **자유와 책임**이 있다.
- 일반 `def` 함수, 타입 주석 생략, `str`/`bytes` 모두 가능하다.

### 사용자 정의 StreamingResponse: 콘텐츠 타입 지정

```Python
import base64
from collections.abc import AsyncIterable, Iterable
from io import BytesIO

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

image_base64 = "iVBORw0KGgo..."  # 작은 PNG
binary_image = base64.b64decode(image_base64)


def read_image() -> BytesIO:
    return BytesIO(binary_image)


app = FastAPI()


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

- `media_type` 속성으로 `Content-Type`을 정한다.
- `BytesIO`는 메모리 안의 파일 같은 객체로, 파일처럼 순회할 수 있다(실제 파일을 대신해 예시로 사용).
- **파일과 async**: 일반 파일 I/O는 블로킹이므로 `async def` 안에서 직접 읽으면 이벤트 루프를 막는다. 경로 작업 함수를 일반 `def`로 선언하면 FastAPI가 스레드풀 워커에서 실행해 메인 루프를 막지 않는다. 일반 `def`에서는 `yield from`으로 간단히 쓸 수 있다.

직접 `StreamingResponse(...)`를 만들어 반환하는 방식도 여전히 가능하지만, 위의 `yield` 방식이 더 편리하고 취소를 알아서 처리한다([커스텀 응답](./custom-responses.md)).

## 의존성과 스트리밍

스트리밍 응답에서 기본(`scope="request"`) yield 의존성의 종료 코드는 **스트림이 끝난 뒤** 실행된다. 스트리밍 중에도 DB 세션 등을 쓸 수 있지만, 필요 없다면 일찍 닫는 것이 좋다([고급 의존성](../dependencies/advanced-dependencies.md), [yield 의존성](../dependencies/dependencies-with-yield.md)).

## 관련 페이지

- [응답 직접 반환과 커스텀 응답](./custom-responses.md)
- [WebSocket](../integrations/websockets.md)
- [요청 처리 흐름](../internals/request-lifecycle.md)
