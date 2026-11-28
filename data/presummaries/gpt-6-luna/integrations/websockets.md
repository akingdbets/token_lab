- **WebSockets**
  - Keep a bidirectional connection open for messages at any time (e.g. chats, dashboards, notifications). Install a server implementation: `uv add websockets`.
  - `fastapi.WebSocket`, `WebSocketDisconnect` and `fastapi.websockets.WebSocketState` are re-exports from Starlette.

- **A basic endpoint**
  - `@app.websocket(path)` (or `@router.websocket(...)`) declares an endpoint, which must be `async def`. Call `await websocket.accept()` before exchanging messages.
  - Use `receive_text()` / `send_text()`, `receive_bytes()` / `send_bytes()`, `receive_json()` / `send_json()`, `iter_text()`, `iter_json()`, and `close(code=...)`. All messages use the same connection.
  - The example browser connects with `new WebSocket("ws://localhost:8000/ws")`; production clients may use a frontend framework or another client.

- **Parameters and dependencies**
  - WebSocket endpoints support `Depends`, `Security`, `Cookie`, `Header`, `Path` and `Query`, as in HTTP path operations. Dependencies can receive `WebSocket`; router- and app-level `dependencies=[...]` apply too.
  - Example signature: `@app.websocket("/items/{item_id}/ws")`; parameters include `item_id: str`, `q: int | None = None`, and `cookie_or_token: Annotated[str, Depends(get_cookie_or_token)]`. `get_cookie_or_token` accepts optional `session: Annotated[str | None, Cookie()] = None` and `token: Annotated[str | None, Query()] = None`; if both are `None`, it raises `WebSocketException(code=status.WS_1008_POLICY_VIOLATION)`.
  - `HTTPException` doesn't make sense here; raise `WebSocketException` with an RFC 6455 close code, e.g. `status.WS_1008_POLICY_VIOLATION`.
  - Invalid parameters raise `WebSocketRequestValidationError`; its default handler closes with code `1008` and errors as the reason. Browsers cannot set custom WebSocket headers, so auth tokens are commonly passed as query parameters or cookies.

- **Disconnects and multiple clients**
  - On client disconnect, `receive_*()` raises `WebSocketDisconnect`; catch it for cleanup. `ConnectionManager` can track `active_connections`, send personal messages and broadcast.
  - The in-memory list works only within one running process. With multiple workers or servers, use a shared backend such as `encode/broadcaster` (Redis, PostgreSQL, …).

- **Telemetry**
  - Each connection produces an OpenTelemetry span like `WS /ws/{room}`; normal closes (`1000`, `1001`) don't produce error logs.

- **Testing and related**
  - Test with `TestClient.websocket_connect()`.
  - Related: one-directional server push over plain HTTP: Streaming Data, JSON Lines and Server-Sent Events; also Dependency Injection Basics.
