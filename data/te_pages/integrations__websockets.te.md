---
type: guide
title: WebSockets
description: Build WebSocket endpoints with @app.websocket and the WebSocket class, send and receive text/bytes/JSON, use Depends, Query, Cookie and other parameters, reject connections with WebSocketException, handle WebSocketDisconnect and broadcast to multiple clients.
tags: [WebSockets, WebSocket, realtime, WebSocketDisconnect, WebSocketException, dependencies]
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
    resource: repo://FastAPI/exception_handlers.py
  - id: openwiki-source-e4b00136116c0a84db1e2736
    resource: repo://FastAPI/websockets.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: WebSockets

WebSockets KEEP BIDIRECTIONAL CONNECTION OPEN; CLIENT AND SERVER SEND MESSAGES ANYTIME: CHATS, LIVE DASHBOARDS, NOTIFICATIONS.

INSTALL SERVER WebSocket IMPLEMENTATION:

⟦code-0⟧

`fastapi.WebSocket`, `WebSocketDisconnect` AND `fastapi.websockets.WebSocketState` ARE RE-EXPORTS FROM STARLETTE.

H2: A basic endpoint

`docs_src/websockets_/tutorial001_py310.py` (HTML/JS TEST PAGE OMITTED):

⟦code-1⟧

- `@app.websocket(path)` (OR `@router.websocket(...)`) DECLARES ENDPOINT; MUST BE `async def`.
- CALL `await websocket.accept()` BEFORE EXCHANGING MESSAGES.
- MESSAGES: `receive_text()` / `send_text()`, `receive_bytes()` / `send_bytes()`, `receive_json()` / `send_json()`; ALSO `iter_text()`, `iter_json()`, AND `close(code=...)`.
- ALL MESSAGES TRAVEL OVER SAME CONNECTION.

EXAMPLE PAGE CONNECTS FROM BROWSER WITH `new WebSocket("ws://localhost:8000/ws")`. IN PRODUCTION, USE FRONTEND FRAMEWORK OR ANOTHER CLIENT.

H2: Parameters and dependencies

WebSocket ENDPOINTS SUPPORT `Depends`, `Security`, `Cookie`, `Header`, `Path` AND `Query`; WORK SAME AS FOR HTTP PATH OPERATIONS (`tutorial002_an_py310.py`):

⟦code-2⟧

- dependencies CAN RECEIVE `WebSocket` ITSELF.
- `HTTPException` DOESN'T APPLY HERE; RAISE **`WebSocketException`** WITH close code FROM RFC 6455, e.g. `status.WS_1008_POLICY_VIOLATION`.
- IF PARAMETERS FAIL VALIDATION, FastAPI RAISES `WebSocketRequestValidationError`; DEFAULT HANDLER CLOSES CONNECTION WITH code `1008` AND ERRORS AS REASON. SEE [HANDLING ERRORS](../errors/handling-errors.md).
- BROWSERS CAN'T SET CUSTOM HEADERS ON WebSocket CONNECTIONS; AUTH TOKENS COMMONLY USE Query PARAMETER OR Cookie, AS HERE.

ROUTER- AND APP-LEVEL `dependencies=[...]` ALSO APPLY TO WebSocket ROUTES.

H2: Disconnects and multiple clients

CLIENT DISCONNECT → `receive_*()` RAISES `WebSocketDisconnect`; CATCH TO CLEAN UP (`tutorial003_py310.py`):

⟦code-3⟧

IN-MEMORY LIST WORKS ONLY WITHIN **ONE PROCESS** WHILE IT RUNS. WITH MULTIPLE WORKERS OR SERVERS, USE SHARED BACKEND, e.g. `encode/broadcaster` (REDIS, PostgreSQL, …).

H2: Telemetry

EACH CONNECTION PRODUCES OpenTelemetry SPAN LIKE `WS /ws/{room}`; NORMAL CLOSES (`1000`, `1001`) PRODUCE NO ERROR LOGS. SEE [GraphQL AND OpenTelemetry](GraphQL-and-opentelemetry.md).

H2: Testing

USE `TestClient.websocket_connect()`; SEE [TESTING dependencies, LIFESPAN EVENTS AND WebSockets](../testing/testing-dependencies-events-websockets.md).

H2: Related

- [STREAMING DATA, JSON LINES AND SERVER-SENT EVENTS](../responses/streaming-and-sse.md) — ONE-DIRECTIONAL SERVER PUSH OVER PLAIN HTTP
- [DEPENDENCY INJECTION BASICS](../dependencies/dependency-injection-basics.md)
```bash
uv add websockets
```
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
