---
type: guide
title: Handling Errors and Exception Handlers
description: Return client errors with HTTPException (detail, headers), register custom exception handlers, override the default HTTPException and RequestValidationError handlers or reuse them, understand ResponseValidationError, and revert security errors to 403.
tags:
  - errors
  - httpexception
  - exception-handlers
  - requestvalidationerror
  - validation
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-1f323bb4ecac55ff65656129
    resource: repo://docs_src/authentication_error_status_code/tutorial001_an_py310.py
  - id: openwiki-source-4f6197b295ea942c9f3bcda4
    resource: repo://docs_src/handling_errors/tutorial001_py310.py
  - id: openwiki-source-c6692ba17e0231ff71f6685a
    resource: repo://docs_src/handling_errors/tutorial002_py310.py
  - id: openwiki-source-dd0a6c93867083961dd90798
    resource: repo://docs_src/handling_errors/tutorial003_py310.py
  - id: openwiki-source-19ed87b7838e67ed44f19919
    resource: repo://docs_src/handling_errors/tutorial006_py310.py
  - id: openwiki-source-8d2ff8a21cb507065344f93b
    resource: repo://docs/en/docs/how-to/authentication-error-status-code.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-cd7d32cb20717b70ce7fd8ca
    resource: repo://fastapi/exception_handlers.py
  - id: openwiki-source-6960ae62409012c9993d0ec2
    resource: repo://fastapi/exceptions.py
  - id: openwiki-source-c3a2665619211e35f840a799
    resource: repo://fastapi/security/http.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Handling Errors and Exception Handlers

## `HTTPException`: returning client errors

To tell the client it did something wrong (missing item, no permission, invalid input), **raise** `HTTPException` (`docs_src/handling_errors/tutorial001_py310.py`):

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

items = {"foo": "The Foo Wrestlers"}


@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```

- Because it is **raised**, not returned, it stops the request immediately — even from deep inside a utility function or a [dependency](../dependencies/dependency-injection-basics.md).
- The client receives status `404` and the JSON body `{"detail": "Item not found"}`.
- `detail` can be any JSON-serializable value (`str`, `dict`, `list`, …).

### Custom headers

```python
raise HTTPException(
    status_code=404,
    detail="Item not found",
    headers={"X-Error": "There goes my error"},
)
```

Useful for security, e.g. `WWW-Authenticate` on `401` responses.

`fastapi.HTTPException` subclasses Starlette's `HTTPException`; the only difference is that FastAPI's accepts any JSON-able `detail` and `headers`. Raise FastAPI's in your code, but **register handlers for Starlette's** (`from starlette.exceptions import HTTPException as StarletteHTTPException`), so they also catch errors Starlette raises internally (e.g. 404 for unknown routes, 405).

There is also `WebSocketException` for WebSocket endpoints (see [WebSockets](../integrations/websockets.md)).

## Custom exception handlers

Register a handler for your own exception type with `@app.exception_handler(...)` (`tutorial003_py310.py`):

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class UnicornException(Exception):
    def __init__(self, name: str):
        self.name = name


app = FastAPI()


@app.exception_handler(UnicornException)
async def unicorn_exception_handler(request: Request, exc: UnicornException):
    return JSONResponse(
        status_code=418,
        content={"message": f"Oops! {exc.name} did something. There goes a rainbow..."},
    )


@app.get("/unicorns/{name}")
async def read_unicorn(name: str):
    if name == "yolo":
        raise UnicornException(name=name)
    return {"unicorn_name": name}
```

A handler receives the `Request` and the exception and returns a `Response`. You can also pass `exception_handlers={ExcType: handler}` to `FastAPI(...)` or call `app.add_exception_handler()`. Handlers can also be keyed by status code (e.g. `404`).

## Default handlers

`FastAPI` installs three defaults (with `setdefault`, so yours take precedence), implemented in `fastapi/exception_handlers.py`:

| Exception | Default handler | Response |
|-----------|-----------------|----------|
| Starlette `HTTPException` | `http_exception_handler` | `{"detail": exc.detail}` with `exc.status_code` and `exc.headers`; no body for statuses that forbid one (e.g. 204, 304) |
| `RequestValidationError` | `request_validation_exception_handler` | `422` with `{"detail": [...errors...]}` |
| `WebSocketRequestValidationError` | `websocket_request_validation_exception_handler` | closes the socket with code `1008` (policy violation) |

`RequestValidationError` is raised when request data (path, query, headers, cookies, body) fails validation. It is a Pydantic-based error: `exc.errors()` returns the list of errors (`loc`, `msg`, `type`, …) and `exc.body` holds the received body.

## Overriding the default handlers

`tutorial004_py310.py` returns plain text instead of JSON:

```python
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    message = "Validation errors:"
    for error in exc.errors():
        message += f"\nField: {error['loc']}, Error: {error['msg']}"
    return PlainTextResponse(message, status_code=400)
```

Including the invalid body in the response, handy during development (`tutorial005_py310.py`):

```python
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )
```

### Reusing FastAPI's default handlers

Do something extra (e.g. log) and then delegate (`tutorial006_py310.py`):

```python
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    print(f"OMG! An HTTP error!: {repr(exc)}")
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"OMG! The client sent invalid data!: {exc}")
    return await request_validation_exception_handler(request, exc)
```

## `ResponseValidationError` — your bug, not the client's

If your endpoint returns data that does not match its `response_model` / return type, FastAPI raises `ResponseValidationError`. There's no default handler, so the client gets a **500 Internal Server Error** and the error is logged. Validation exceptions carry endpoint context (`endpoint_function`, `endpoint_path`, `endpoint_file`, `endpoint_line`), and `str(exc)` includes the file/line of the offending endpoint, which makes these errors easy to locate. See [Response Models](../models/response-model.md).

Unhandled exceptions in general produce a `500` from Starlette's `ServerErrorMiddleware`.

## Exceptions and dependencies with `yield`

Exceptions raised in the endpoint are thrown into `yield` dependencies; catch them there to convert them into `HTTPException`s, and always re-raise what you don't handle. See [Dependencies with yield](../dependencies/dependencies-with-yield.md).

## Authentication errors: 401 vs 403

Since FastAPI **0.122.0**, the built-in security classes respond to missing/invalid credentials with **`401 Unauthorized`** plus a suitable `WWW-Authenticate` header (previously `403 Forbidden`). To restore 403 for clients that depend on it, override `make_not_authenticated_error` (`docs_src/authentication_error_status_code/tutorial001_an_py310.py`):

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI()


class HTTPBearer403(HTTPBearer):
    def make_not_authenticated_error(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated"
        )


CredentialsDep = Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer403())]


@app.get("/me")
def read_me(credentials: CredentialsDep):
    return {"message": "You are authenticated", "token": credentials.credentials}
```

The method **returns** the exception; the security class raises it. See [HTTP Basic, Bearer, API Keys](../security/http-basic-and-api-keys.md).

## Related

- [Response Status Codes](../responses/status-codes.md)
- [Middleware](../middleware/middleware.md) — exception handlers run inside the middleware stack
