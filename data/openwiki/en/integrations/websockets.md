---
type: guide
title: WebSockets
description: Build WebSocket endpoints with @app.websocket and the WebSocket class, send and receive text/bytes/JSON, use Depends, Query, Cookie and other parameters, reject connections with WebSocketException, handle WebSocketDisconnect and broadcast to multiple clients.
tags: [websockets, websocket, realtime, websocketdisconnect, websocketexception, dependencies]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-73c859b33be839276cbb1871
    resource: repo://docs_src/websockets_/tutorial001_py310.py
  - id: openwiki-source-cbecc08eab352f5375fcea34
    resource: repo://docs_src/websockets_/tutorial002_an_py310.py
  - id: openwiki-source-4bee90d37397371d9a4e0494
    resource: repo://docs_src/websockets_/tutorial003_py310.py
  - id: openwiki-source-1c53e08678276c3a6f86ce41
    resource: repo://docs/en/docs/advanced/websockets.md
  - id: openwiki-source-cd7d32cb20717b70ce7fd8ca
    resource: repo://fastapi/exception_handlers.py
  - id: openwiki-source-e4b00136116c0a84db1e2736
    resource: repo://fastapi/websockets.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# WebSockets

WebSockets keep a bidirectional connection open so client and server can send messages at any time — chats, live dashboards, notifications.

Install a WebSocket implementation for the server:

```bash
uv add websockets
```

`fastapi.WebSocket`, `WebSocketDisconnect` and `fastapi.websockets.WebSocketState` are re-exports from Starlette.

## A basic endpoint

`docs_src/websockets_/tutorial001_py310.py` (the HTML/JS test page is omitted):

```python
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

- `@app.websocket(path)` (or `@router.websocket(...)`) declares the endpoint; it must be `async def`.
- Call `await websocket.accept()` before exchanging messages.
- Messages: `receive_text()` / `send_text()`, `receive_bytes()` / `send_bytes()`, `receive_json()` / `send_json()`. Also `iter_text()`, `iter_json()`, and `close(code=...)`.
- All messages travel over the same connection.

The example page connects with `new WebSocket("ws://localhost:8000/ws")` from the browser. In production you'd use a frontend framework or another client.

## Parameters and dependencies

WebSocket endpoints support `Depends`, `Security`, `Cookie`, `Header`, `Path` and `Query`, working the same as for HTTP path operations (`tutorial002_an_py310.py`):

```python
from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Query,
    WebSocket,
    WebSocketException,
    status,
)

app = FastAPI()


async def get_cookie_or_token(
    websocket: WebSocket,
    session: Annotated[str | None, Cookie()] = None,
    token: Annotated[str | None, Query()] = None,
):
    if session is None and token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return session or token


@app.websocket("/items/{item_id}/ws")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
    item_id: str,
    q: int | None = None,
    cookie_or_token: Annotated[str, Depends(get_cookie_or_token)],
):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(
            f"Session cookie or query token value is: {cookie_or_token}"
        )
        if q is not None:
            await websocket.send_text(f"Query parameter q is: {q}")
        await websocket.send_text(f"Message text was: {data}, for item ID: {item_id}")
```

- Dependencies can receive the `WebSocket` itself.
- `HTTPException` doesn't make sense here; raise **`WebSocketException`** with a close code from RFC 6455, e.g. `status.WS_1008_POLICY_VIOLATION`.
- If parameters fail validation, FastAPI raises `WebSocketRequestValidationError`, whose default handler closes the connection with code `1008` and the errors as the reason (see [Handling Errors](../errors/handling-errors.md)).
- Browsers can't set custom headers on WebSocket connections, so auth tokens are commonly passed as a query parameter or cookie, as here.

Router- and app-level `dependencies=[...]` also apply to WebSocket routes.

## Disconnects and multiple clients

When the client disconnects, `receive_*()` raises `WebSocketDisconnect`. Catch it to clean up (`tutorial003_py310.py`):

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")
```

This in-memory list only works within **one process** while it runs. With multiple workers or servers, use a shared backend — e.g. `encode/broadcaster` (Redis, PostgreSQL, …).

## Telemetry

Each connection produces an OpenTelemetry span like `WS /ws/{room}`; normal closes (`1000`, `1001`) don't produce error logs. See [GraphQL and OpenTelemetry](graphql-and-opentelemetry.md).

## Testing

Use `TestClient.websocket_connect()`; see [Testing Dependencies, Lifespan Events and WebSockets](../testing/testing-dependencies-events-websockets.md).

## Related

- [Streaming Data, JSON Lines and Server-Sent Events](../responses/streaming-and-sse.md) — one-directional server push over plain HTTP
- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
