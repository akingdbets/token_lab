---
type: guide
title: Middleware
description: Write HTTP middleware with @app.middleware("http") and call_next, add ASGI middleware with app.add_middleware, understand stacking order, and use the built-in HTTPSRedirectMiddleware, TrustedHostMiddleware and GZipMiddleware.
tags: [middleware, add_middleware, call_next, gzip, trustedhost, httpsredirect, asgi, ordering]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-539d8b9abc33736a7b2bf32d
    resource: repo://docs_src/advanced_middleware/tutorial002_py310.py
  - id: openwiki-source-babe0caa8e49e3e3763ac854
    resource: repo://docs_src/advanced_middleware/tutorial003_py310.py
  - id: openwiki-source-a1f421664c566814c997c663
    resource: repo://docs_src/middleware/tutorial001_py310.py
  - id: openwiki-source-871429548d01a3779623de44
    resource: repo://docs/en/docs/advanced/middleware.md
  - id: openwiki-source-8c4aeccd826b7d0f1407df40
    resource: repo://docs/en/docs/tutorial/middleware.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-6f0e71e6c0cd9014f0b87c22
    resource: repo://fastapi/middleware/gzip.py
  - id: openwiki-source-9c5ece77a13062dbdc022b7d
    resource: repo://fastapi/middleware/httpsredirect.py
  - id: openwiki-source-d43bfb6553e982c9eeac16e3
    resource: repo://fastapi/middleware/trustedhost.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Middleware

A **middleware** runs for **every request** before it reaches a path operation, and for every **response** before it's returned. Use it for cross-cutting concerns: timing, logging, compression, host checks, CORS, request IDs.

## Writing HTTP middleware

Decorate an `async` function with `@app.middleware("http")` (`docs_src/middleware/tutorial001_py310.py`):

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

The function receives:

- `request` — the `Request`;
- `call_next` — a function that passes the request to the rest of the app (inner middleware, then the path operation) and returns the `response`.

You can run code before `call_next` (inspect/modify the request, short-circuit by returning a response yourself) and after it (modify the response).

Notes:

- Custom headers conventionally use an `X-` prefix. For browser JS to read them cross-origin, list them in CORS `expose_headers` ([CORS](cors.md)).
- `time.perf_counter()` is more precise than `time.time()` for measuring durations.
- Exit code of `yield` dependencies runs *after* the middleware, and background tasks run after all middleware.
- `@app.middleware("http")` is built on Starlette's `BaseHTTPMiddleware`. For high-performance or streaming-sensitive middleware, write a pure ASGI middleware class instead.

## Adding ASGI middleware classes

Any ASGI middleware works — it doesn't need to be written for FastAPI. ASGI middlewares are classes taking the app as the first argument. Third-party docs usually show:

```python
from unicorn import UnicornMiddleware

app = SomeASGIApp()
new_app = UnicornMiddleware(app, some_config="rainbow")
```

In FastAPI, use `add_middleware()` instead, which keeps FastAPI's exception handling and middleware stack intact:

```python
from fastapi import FastAPI
from unicorn import UnicornMiddleware

app = FastAPI()

app.add_middleware(UnicornMiddleware, some_config="rainbow")
```

You can also pass `middleware=[Middleware(...)]` to `FastAPI(...)`.

## Execution order

Each added middleware wraps the app built so far. **The last one added is the outermost.**

```python
app.add_middleware(MiddlewareA)
app.add_middleware(MiddlewareB)
```

- Request: `MiddlewareB → MiddlewareA → route`
- Response: `route → MiddlewareA → MiddlewareB`

This applies to both `@app.middleware()` and `add_middleware()`. Your middleware sits **outside** FastAPI's exception handlers, so it sees the responses they produce (404, 422, your custom handlers), and **inside** `ServerErrorMiddleware`, which turns unhandled exceptions into 500 responses. See [How FastAPI Handles a Request](../internals/request-handling-internals.md) for the full stack.

## Built-in middleware

FastAPI re-exports common Starlette middleware in `fastapi.middleware` for convenience.

### `HTTPSRedirectMiddleware`

Redirects every `http` request to `https` (and `ws` to `wss`):

```python
from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

app.add_middleware(HTTPSRedirectMiddleware)
```

Behind a TLS termination proxy, make sure forwarded headers are trusted (`--forwarded-allow-ips` / `--proxy-headers`), or the app will think every request is `http` and redirect in a loop. Often the proxy handles this redirect instead. See [HTTPS and Cloud](../deployment/https-and-cloud.md).

### `TrustedHostMiddleware`

Rejects requests whose `Host` header isn't allowed — protects against HTTP Host header attacks:

```python
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()

app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["example.com", "*.example.com"]
)
```

- `allowed_hosts` — domain names allowed as hostnames; wildcards like `*.example.com` match subdomains. `["*"]` (or omitting the middleware) allows any.
- `www_redirect` — redirect non-www requests to the `www.` version of an allowed host (default `True`).

Invalid hosts get a `400` response.

### `GZipMiddleware`

Compresses responses for clients that send `gzip` in `Accept-Encoding`:

```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
```

- `minimum_size` — don't compress responses smaller than this many bytes (default `500`).
- `compresslevel` — 1 (fast, larger) to 9 (slow, smaller); default `9`.

### `CORSMiddleware`

See the dedicated page: [CORS](cors.md).

### Others

`fastapi.middleware.wsgi.WSGIMiddleware` (deprecated; use `a2wsgi`) — see [Sub-applications, Proxies and WSGI](../app-structure/sub-applications-proxy-and-wsgi.md). Third-party examples: Uvicorn's `ProxyHeadersMiddleware`, MessagePack (`msgpack-asgi`); see Starlette's middleware docs and the "awesome-asgi" list for more.

## Middleware vs dependencies

- Middleware applies to **every** request (including 404s, static files, docs) and works on raw requests/responses.
- [Dependencies](../dependencies/decorator-and-global-dependencies.md) apply to path operations, integrate with validation and OpenAPI, and can be scoped to a router or route.
- To customize request/response handling per route with full FastAPI integration, see [custom `APIRoute` classes](../request/using-request-directly.md).

## Related

- [CORS](cors.md)
- [Handling Errors](../errors/handling-errors.md)
- [GraphQL and OpenTelemetry](../integrations/graphql-and-opentelemetry.md) — built-in telemetry needs no middleware
