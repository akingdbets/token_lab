---
type: guide
title: Using the Request Object, Strict Content-Type and Custom Request Classes
description: Access Starlette's Request directly (client, headers, raw body), understand strict JSON Content-Type checking and strict_content_type=False, and customize request handling with custom Request subclasses and APIRoute.get_route_handler (gzip bodies, logging validation errors, timing).
tags: [request, starlette, content-type, csrf, strict_content_type, apiroute, route_class, gzip]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-6466f5371ff581d059ae3ba8
    resource: repo://docs_src/custom_request_and_route/tutorial001_py310.py
  - id: openwiki-source-6bd74c24f53cf74f8797f45e
    resource: repo://docs_src/custom_request_and_route/tutorial002_py310.py
  - id: openwiki-source-e79f261952e8647156880574
    resource: repo://docs_src/custom_request_and_route/tutorial003_py310.py
  - id: openwiki-source-c2610c12a0bb7697c1366728
    resource: repo://docs_src/strict_content_type/tutorial001_py310.py
  - id: openwiki-source-8782b090f58527cb09067138
    resource: repo://docs_src/using_request_directly/tutorial001_py310.py
  - id: openwiki-source-dca17208de257c294db55bc3
    resource: repo://docs/en/docs/advanced/strict-content-type.md
  - id: openwiki-source-1c4300918a70439b89cefc67
    resource: repo://docs/en/docs/advanced/using-request-directly.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-4f39b87de176905c9a9e93d3
    resource: repo://fastapi/requests.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Using the Request Object, Strict Content-Type and Custom Request Classes

## Using the `Request` directly

Normally you declare exactly what you need (path, query, body…) and FastAPI validates, converts and documents it. Sometimes you need the raw request — client IP, all headers, the raw body. Declare a parameter typed `Request` (`docs_src/using_request_directly/tutorial001_py310.py`):

```python
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/items/{item_id}")
def read_root(item_id: str, request: Request):
    client_host = request.client.host
    return {"client_host": client_host, "item_id": item_id}
```

- `fastapi.Request` is Starlette's `Request` (`fastapi/requests.py` also re-exports `HTTPConnection`, the common base of `Request` and `WebSocket`).
- Other parameters are still validated and documented (`item_id` here).
- Data you read from `Request` yourself (e.g. `await request.body()`, `await request.json()`, `request.query_params`) is **not** validated, converted or documented.

Useful attributes: `request.method`, `request.url`, `request.headers`, `request.query_params`, `request.path_params`, `request.cookies`, `request.client` (`host`, `port`), `request.state`, `request.app`, `request.scope`, and `await request.body()` / `json()` / `form()` / `stream()`.

`Request` can be injected in dependencies too, and is passed to middleware and exception handlers.

## Strict `Content-Type` checking

Since FastAPI **0.132.0**, JSON bodies are parsed only when the request has a JSON `Content-Type` (`application/json` or `application/*+json`). A request **without** `Content-Type` is not parsed as JSON, so a model body fails validation.

### Why: a CSRF protection

Browsers let scripts send cross-origin requests **without** a CORS preflight when there's no `Content-Type` (e.g. `fetch()` with a `Blob` body) and no credentials. Imagine an unauthenticated local AI agent API at `http://localhost:8000/v1/agents/multivac` that trusts the local network. A malicious website could POST to it from the user's browser; the browser wouldn't preflight because it doesn't think it's sending JSON. Strict checking makes such bodies fail.

This matters mainly for apps on `localhost` or internal networks whose only protection is "trust the network". Apps on the open internet must authenticate privileged endpoints anyway, so the attack doesn't apply there.

### Allowing requests without `Content-Type`

If you must support clients that omit the header (`docs_src/strict_content_type/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(strict_content_type=False)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items/")
async def create_item(item: Item):
    return item
```

Bodies without a `Content-Type` are then parsed as JSON (the pre-0.132 behavior). The flag is accepted by `FastAPI(...)` and `APIRouter(...)` (and stored on each `APIRoute`). A **non-JSON** `Content-Type` (e.g. `text/plain`) is never parsed as JSON, regardless of the flag.

## Custom `Request` and `APIRoute` classes

For advanced cases you can change how a route turns a request into a response, keeping all of FastAPI's validation. Every path operation is an `APIRoute`; override `get_route_handler()` to wrap the original handler, and set the class on the app's router or an `APIRouter`.

> Only use this for things you can't do with dependencies or middleware.

### Decompressing gzip request bodies

`docs_src/custom_request_and_route/tutorial001_py310.py`:

```python
import gzip
from collections.abc import Callable

from fastapi import Body, FastAPI, Request, Response
from fastapi.routing import APIRoute


class GzipRequest(Request):
    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = await super().body()
            if "gzip" in self.headers.getlist("Content-Encoding"):
                body = gzip.decompress(body)
            self._body = body
        return self._body


class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = GzipRequest(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler


app = FastAPI()
app.router.route_class = GzipRoute


@app.post("/sum")
async def sum_numbers(numbers: list[int] = Body()):
    return {"sum": sum(numbers)}
```

- A `Request` is built from the ASGI `scope` dict and `receive` callable, so you can wrap it in your subclass.
- `GzipRequest.body()` decompresses once and caches in `_body`; FastAPI's body parsing then sees plain JSON.
- `app.router.route_class = GzipRoute` applies it to routes declared afterwards.

### Accessing the body when validation fails

The request is still available if an exception happens, so you can include the raw body in the error (`tutorial002_py310.py`):

```python
class ValidationErrorLoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                body = await request.body()
                detail = {"errors": exc.errors(), "body": body.decode()}
                raise HTTPException(status_code=422, detail=detail)

        return custom_route_handler
```

(A simpler alternative for most apps: a `RequestValidationError` [exception handler](../errors/handling-errors.md) using `exc.body`.)

### Per-router route classes: timing

Set `route_class` on an `APIRouter` to affect only its routes (`tutorial003_py310.py`):

```python
class TimedRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            before = time.time()
            response: Response = await original_route_handler(request)
            duration = time.time() - before
            response.headers["X-Response-Time"] = str(duration)
            return response

        return custom_route_handler


app = FastAPI()
router = APIRouter(route_class=TimedRoute)


@app.get("/")
async def not_timed():
    return {"message": "Not timed"}


@router.get("/timed")
async def timed():
    return {"message": "It's the time of my life"}


app.include_router(router)
```

Only `/timed` gets the `X-Response-Time` header. Unlike middleware, this runs inside the route, after routing and with access to FastAPI's handler.

## Related

- [How FastAPI Handles a Request](../internals/request-handling-internals.md)
- [Middleware](../middleware/middleware.md)
- [CORS](../middleware/cors.md)
