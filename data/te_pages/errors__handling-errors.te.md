---
type: guide
title: HANDLING ERRORS AND EXCEPTION HANDLERS
description: RETURN CLIENT ERRORS WITH HTTPException (`detail`, `headers`); REGISTER CUSTOM HANDLERS; OVERRIDE OR REUSE DEFAULT HTTPException AND RequestValidationError HANDLERS; UNDERSTAND ResponseValidationError; REVERT SECURITY ERRORS TO 403.
tags:
  - errors
  - HTTPException
  - exception-handlers
  - RequestValidationError
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

H1: HANDLING ERRORS AND EXCEPTION HANDLERS

H2: `HTTPException`: RETURNING CLIENT ERRORS

RAISE `HTTPException` WHEN CLIENT MAKES AN ERROR (MISSING Item, NO PERMISSION, INVALID INPUT) (`docs_src/handling_errors/tutorial001_py310.py`):

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

- RAISING, not RETURNING, STOPS Request IMMEDIATELY—even INSIDE DEEP UTILITY FUNCTION OR [DEPENDENCY](../dependencies/dependency-injection-basics.md).
- CLIENT RECEIVES STATUS `404` AND JSON BODY `{"detail": "Item not found"}`.
- `detail` ACCEPTS ANY JSON-SERIALIZABLE VALUE (`str`, `dict`, `list`, …).

H3: CUSTOM headers

```python
raise HTTPException(
    status_code=404,
    detail="Item not found",
    headers={"X-Error": "There goes my error"},
)
```

USEFUL FOR SECURITY; e.g. `WWW-Authenticate` ON `401` RESPONSES.

`fastapi.HTTPException` SUBCLASSES STARLETTE'S `HTTPException`; DIFFERENCE: FASTAPI'S ACCEPTS ANY JSON-ABLE `detail` AND `headers`. RAISE FASTAPI'S IN YOUR CODE; REGISTER HANDLERS FOR STARLETTE'S (`from starlette.exceptions import HTTPException as StarletteHTTPException`) TO ALSO CATCH STARLETTE'S INTERNAL ERRORS (e.g. 404 FOR UNKNOWN ROUTES, 405).

`WebSocketException` ALSO SERVES WebSocket ENDPOINTS (SEE [WebSockets](../integrations/websockets.md)).

H2: CUSTOM EXCEPTION HANDLERS

REGISTER handler FOR YOUR EXCEPTION type WITH `@app.exception_handler(...)` (`tutorial003_py310.py`):

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

handler RECEIVES `Request` AND EXCEPTION; RETURNS `Response`. ALTERNATIVELY, PASS `exception_handlers={ExcType: handler}` TO `FastAPI(...)` OR CALL `app.add_exception_handler()`. HANDLERS CAN ALSO USE STATUS CODES as KEYS (e.g. `404`).

H2: DEFAULT HANDLERS

`FastAPI` INSTALLS THREE DEFAULTS WITH `setdefault`; YOUR HANDLERS TAKE PRECEDENCE. IMPLEMENTED IN `fastapi/exception_handlers.py`:

| EXCEPTION | DEFAULT handler | Response |
|---|---|---|
| STARLETTE `HTTPException` | `http_exception_handler` | `{"detail": exc.detail}` WITH `exc.status_code` AND `exc.headers`; NO BODY FOR STATUSES THAT FORBID ONE (e.g. 204, 304) |
| `RequestValidationError` | `request_validation_exception_handler` | `422` WITH `{"detail": [...errors...]}` |
| `WebSocketRequestValidationError` | `websocket_request_validation_exception_handler` | CLOSES SOCKET WITH CODE `1008` (POLICY VIOLATION) |

`RequestValidationError` OCCURS WHEN Request DATA (PATH, QUERY, headers, COOKIES, BODY) FAILS VALIDATION. IT IS PYDANTIC-BASED: `exc.errors()` RETURNS ERROR list (`loc`, `msg`, `type`, …); `exc.body` HOLDS RECEIVED BODY.

H2: OVERRIDING DEFAULT HANDLERS

`tutorial004_py310.py` RETURNS PLAIN TEXT INSTEAD OF JSON:

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

INCLUDE INVALID BODY IN Response—USEFUL DURING DEVELOPMENT (`tutorial005_py310.py`):

```python
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )
```

H3: REUSING FASTAPI'S DEFAULT HANDLERS

DO EXTRA WORK (e.g. LOG), THEN DELEGATE (`tutorial006_py310.py`):

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

H2: `ResponseValidationError` — YOUR BUG, not THE CLIENT'S
ENDPOINT DATA≠`response_model` / RETURN type ⇒ FastAPI RAISES
`ResponseValidationError`.
NO DEFAULT handler ∴ CLIENT GETS 500 INTERNAL SERVER ERROR; ERROR LOGGED.
VALIDATION EXCEPTIONS CARRY ENDPOINT CONTEXT:
`endpoint_function`, `endpoint_path`, `endpoint_file`, `endpoint_line`.
`str(exc)` INCLUDES FILE/LINE OF OFFENDING ENDPOINT ∴ ERRORS EASY TO LOCATE.
SEE [Response MODELS](../models/Response-model.md).

UNHANDLED EXCEPTIONS GENERALLY PRODUCE 500 from STARLETTE'S
`ServerErrorMiddleware`.

H2: EXCEPTIONS AND DEPENDENCIES WITH `yield`

ENDPOINT EXCEPTIONS ARE THROWN INTO `yield` DEPENDENCIES.
CATCH THERE TO CONVERT THEM INTO `HTTPException`s;
ALWAYS RE-RAISE EXCEPTIONS YOU DON'T HANDLE.
SEE [DEPENDENCIES WITH yield](../dependencies/dependencies-with-yield.md).

H2: AUTHENTICATION ERRORS: 401 VS 403

SINCE FastAPI 0.122.0, BUILT-IN SECURITY CLASSES RESPOND TO
MISSING/INVALID CREDENTIALS WITH `401 Unauthorized` PLUS SUITABLE
`WWW-Authenticate` HEADER; PREVIOUSLY `403 Forbidden`.
TO RESTORE 403 FOR CLIENTS THAT DEPEND ON IT, OVERRIDE
`make_not_authenticated_error` (`docs_src/authentication_error_status_code/tutorial001_an_py310.py`):

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

METHOD RETURNS THE EXCEPTION; SECURITY CLASS RAISES IT.
SEE [HTTP BASIC, BEARER, API KEYS](../security/HTTP-basic-and-API-keys.md).

H2: RELATED

- [Response STATUS CODES](../responses/status-codes.md)
- [MIDDLEWARE](../middleware/middleware.md) — EXCEPTION HANDLERS RUN INSIDE
  THE MIDDLEWARE STACK
