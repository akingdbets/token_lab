## `HTTPException`: returning client errors
- **Raise**, rather than return, `HTTPException` to stop a request immediately, including from utility functions and dependencies. Example: `raise HTTPException(status_code=404, detail="Item not found")` returns `404` and `{"detail": "Item not found"}`.
- `detail` can be any JSON-serializable value (`str`, `dict`, `list`, …). `headers` can carry custom headers, useful for security, e.g. `WWW-Authenticate` on `401`.
- `fastapi.HTTPException` subclasses Starlette's `HTTPException`; FastAPI's accepts any JSON-able `detail` and `headers`. Raise FastAPI's, but register handlers for Starlette's (`from starlette.exceptions import HTTPException as StarletteHTTPException`) to catch errors raised internally, such as unknown-route `404` and `405`.
- `WebSocketException` is for WebSocket endpoints.

## Custom exception handlers
- Register with `@app.exception_handler(...)`, `exception_handlers={ExcType: handler}` in `FastAPI(...)`, or `app.add_exception_handler()`. A handler receives `Request` and the exception, and returns a `Response`; handlers can also be keyed by status code (e.g. `404`).

## Default handlers
- FastAPI installs three defaults with `setdefault`, so user handlers take precedence:
  - Starlette `HTTPException` → `http_exception_handler`: `{"detail": exc.detail}`, `exc.status_code`, and `exc.headers`; no body for statuses that forbid one (e.g. `204`, `304`).
  - `RequestValidationError` → `request_validation_exception_handler`: `422`, `{"detail": [...errors...]}`.
  - `WebSocketRequestValidationError` → `websocket_request_validation_exception_handler`: closes socket with code `1008` (policy violation).
- `RequestValidationError` means request path, query, headers, cookies, or body failed validation. `exc.errors()` gives errors (`loc`, `msg`, `type`, …); `exc.body` is the received body.

## Overriding the default handlers
- Register handlers for `StarletteHTTPException` and `RequestValidationError` to change responses (e.g. `PlainTextResponse`; custom validation handler can return `400`).
- During development, include invalid input with `JSONResponse(status_code=422, content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}))`.
- To add behavior such as logging and retain defaults, import `http_exception_handler` and `request_validation_exception_handler` from `fastapi.exception_handlers` and `await` the appropriate handler.

## `ResponseValidationError` — your bug, not the client's
- A return value that does not match `response_model` / return type raises `ResponseValidationError`. There is no default handler: client gets **500 Internal Server Error**, and error is logged.
- Validation exceptions include `endpoint_function`, `endpoint_path`, `endpoint_file`, `endpoint_line`; `str(exc)` includes offending endpoint file/line. Other unhandled exceptions produce `500` from Starlette's `ServerErrorMiddleware`.

## Exceptions and dependencies with `yield`
- Endpoint exceptions are thrown into `yield` dependencies. Catch them there to convert to `HTTPException`; always re-raise exceptions you do not handle.

## Authentication errors: 401 vs 403
- Since FastAPI **0.122.0**, built-in security classes respond to missing/invalid credentials with **`401 Unauthorized`** and a suitable `WWW-Authenticate` header (previously `403 Forbidden`).
- To restore `403`, override `make_not_authenticated_error` to return an `HTTPException` with `status_code=status.HTTP_403_FORBIDDEN`; the security class raises the returned exception.

## Related
- Exception handlers run inside the middleware stack. See Response Status Codes, Middleware, Response Models, Dependencies with yield, and HTTP Basic, Bearer, API Keys.
