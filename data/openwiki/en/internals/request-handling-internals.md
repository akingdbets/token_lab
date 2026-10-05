---
type: architecture
title: How FastAPI Handles a Request (Internals for Users)
description: The user-relevant internals of a FastAPI request — the middleware stack, route matching, body parsing and Content-Type checks, dependency resolution with caching and overrides, threadpool vs event loop execution, response validation and serialization, streaming paths, and exit stacks for yield dependencies.
tags: [internals, request-lifecycle, middleware-stack, dependencies, serialization, response_model, exit-stack]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-338938fe8c8c2e10895f46fa
    resource: repo://fastapi/middleware/asyncexitstack.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# How FastAPI Handles a Request (Internals for Users)

You don't need this page to use FastAPI, but it explains *why* things behave as they do — error codes, the order of middleware and handlers, when dependencies close, and what affects performance. Sources: `fastapi/applications.py`, `fastapi/routing.py`, `fastapi/dependencies/utils.py`.

## 1. At startup: building routes

Each path operation decorator creates an `APIRoute` (a Starlette `Route` subclass). When the route is built, FastAPI:

- Inspects the endpoint's signature (`get_dependant`) and classifies every parameter: path, query, header, cookie, body, form/file, a dependency (`Depends`/`Security`), or a special object (`Request`, `WebSocket`, `Response`, `BackgroundTasks`, `SecurityScopes`). The result is a tree of `Dependant` objects (`fastapi/dependencies/models.py`).
- Determines the response field from `response_model` or the return annotation.
- Fills metadata such as `description` from the docstring and `unique_id` (operation ID).
- Checks configuration errors early, e.g. `DependencyScopeError` for invalid `yield` scope combinations, or a status code that forbids a body combined with a response model.

The OpenAPI schema is generated from these routes on demand and cached (`app.openapi()`).

## 2. The middleware stack

`FastAPI.build_middleware_stack()` wraps the router like this (outermost first):

```
ServerErrorMiddleware        ← unhandled exceptions → 500 (your handler for 500/Exception goes here)
ExceptionTelemetryMiddleware ← OpenTelemetry exception recording
<your middleware>            ← add_middleware / @app.middleware("http"), last added = outermost
ExceptionMiddleware          ← your exception handlers (HTTPException, RequestValidationError, custom…)
AsyncExitStackMiddleware     ← closes uploaded files after the request
Router                       ← route matching → APIRoute
```

Consequences:

- Exception handlers run **inside** your middleware, so middleware sees the handler's response (e.g. a 422 or 404).
- Exceptions not handled by any handler reach `ServerErrorMiddleware` → 500. (`debug=True` shows tracebacks.)
- A handler registered for `500` or `Exception` becomes the `ServerErrorMiddleware` handler.

See [Middleware](../middleware/middleware.md) and [Handling Errors](../errors/handling-errors.md).

## 3. Matching the route

The router matches the path and method. Path operations take priority over frontend routes (`app.frontend()`), and routes from included routers are resolved "live" through `_IncludedRouter` entries (see [Bigger Applications](../app-structure/bigger-applications.md)). No match → 404; path matches but method doesn't → 405.

## 4. Per-request exit stacks

`request_response()` opens two `AsyncExitStack`s around the call:

- a **request** stack (`fastapi_inner_astack`) — closed **after the response is sent**;
- a **function** stack (`fastapi_function_astack`) — closed right after the endpoint returns, before sending.

`yield` dependencies are entered on one of these depending on `Depends(scope=...)`. If the response was never sent because an exception was swallowed in a `yield` dependency's `except`, FastAPI raises a `FastAPIError` explaining that likely cause. See [Dependencies with yield](../dependencies/dependencies-with-yield.md).

## 5. Reading the body

Only if the endpoint has body parameters:

- **Form/File** parameters → `await request.form()`; the form (and its files) is closed via `AsyncExitStackMiddleware` at the end.
- Otherwise, the raw body is read; it's parsed as **JSON only when** `Content-Type` is `application/json` or `application/*+json`. With **no** Content-Type, JSON is parsed only if `strict_content_type=False`. Any other content type leaves the raw bytes, which then fail validation for model bodies. See [Using the Request Object, Strict Content-Type](../request/using-request-directly.md).
- Invalid JSON → `RequestValidationError` with type `json_invalid` (→ 422). Other parsing failures → `HTTPException(400, "There was an error parsing the body")`.

## 6. Solving dependencies and validating parameters

`solve_dependencies()` walks the `Dependant` tree depth-first:

- Applies `app.dependency_overrides` (replacing a dependency callable with its override).
- For each sub-dependency: returns a cached value if the same `(callable, security scopes, scope)` was already solved in this request and `use_cache=True`; otherwise calls it — generators via the exit stacks, `async def` awaited, plain `def` run in the threadpool.
- Extracts path/query/header/cookie values and the body, and validates them with Pydantic. **All** errors are collected; if any, a single `RequestValidationError` (→ 422 with all errors) is raised after resolution.
- Injects special objects: the `Request`, a temporary `Response` (for headers/cookies/status you set), the shared `BackgroundTasks`, `SecurityScopes`.

## 7. Running the endpoint

`run_endpoint_function()` awaits `async def` endpoints directly on the event loop and runs plain `def` endpoints with `run_in_threadpool`. See [Python Types and async/await](../getting-started/python-types-and-async.md).

Generator endpoints take streaming paths instead:

- `response_class=EventSourceResponse` → Server-Sent Events.
- A generator with JSON Lines semantics → `StreamingResponse` with `media_type="application/jsonl"`, each item validated/serialized individually.
- A generator with an explicit `response_class` (e.g. `StreamingResponse`) → chunks passed through.

See [Streaming Data, JSON Lines and Server-Sent Events](../responses/streaming-and-sse.md).

## 8. Building the response

- If the endpoint returned a `Response` instance, it is used **as is** (no validation, no serialization); collected background tasks are attached if the response has none.
- Otherwise `serialize_response()`:
  - With a response field (from `response_model` or the return type), the value is **validated** against it (a failure raises `ResponseValidationError` → 500) and serialized with Pydantic honoring `response_model_include/exclude/by_alias/exclude_unset/exclude_defaults/exclude_none`.
  - Without one, the value is converted with `jsonable_encoder`.
  - Fast path: with a response field **and** the default response class, Pydantic serializes **directly to JSON bytes** (skipping the intermediate dict + `json.dumps`) and FastAPI returns `Response(media_type="application/json")`. That's a reason to declare response models/return types — it's faster, not just safer.
  - Otherwise the content is passed to the route's `response_class` (default `JSONResponse`).
- Status code: the decorator's `status_code`, or one set on the injected `Response` parameter. For statuses that forbid a body (e.g. 204, 304), the body is emptied.
- Headers and cookies set on the injected `Response` are copied onto the final response.

See [Response Models](../models/response-model.md) and [Custom Responses](../responses/custom-responses.md).

## 9. After the response

In `request_response()` the order is:

1. The function stack closes when the endpoint (and response building) finishes — teardown of `scope="function"` `yield` dependencies.
2. `await response(scope, receive, send)` sends the response; Starlette runs the response's background tasks as part of this call, after the body is sent.
3. The request stack closes — teardown of request-scoped (default) `yield` dependencies.
4. Further out, `AsyncExitStackMiddleware` closes uploaded files.

Even so, don't rely on objects from `yield` dependencies inside background tasks; create their own resources (see [Background Tasks](../integrations/background-tasks.md)).

## Related

- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
- [Advanced Dependencies](../dependencies/advanced-dependencies.md)
