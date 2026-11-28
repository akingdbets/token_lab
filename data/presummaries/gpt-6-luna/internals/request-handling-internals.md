## 1. At startup: building routes
- Each path operation decorator creates an `APIRoute` (a Starlette `Route` subclass). FastAPI inspects the endpoint with `get_dependant`, classifies parameters, and builds a `Dependant` tree (`fastapi/dependencies/models.py`); determines the response field from `response_model` or return annotation; fills `description` and `unique_id`; and checks configuration errors early (including invalid `yield` scopes and body-forbidden status codes combined with a response model).
- `app.openapi()` generates the OpenAPI schema on demand and caches it.

## 2. The middleware stack
- `FastAPI.build_middleware_stack()` order, outermost first: `ServerErrorMiddleware` → `ExceptionTelemetryMiddleware` → user middleware (`add_middleware` / `@app.middleware("http")`; last added is outermost) → `ExceptionMiddleware` → `AsyncExitStackMiddleware` → Router.
- Exception handlers run inside user middleware, whose middleware sees their responses. Unhandled exceptions reach `ServerErrorMiddleware` → 500; `debug=True` shows tracebacks. A handler for `500` or `Exception` becomes its handler.

## 3. Matching the route
- Router matches path and method. Path operations take priority over `app.frontend()`; included routers resolve live through `_IncludedRouter`. No match → 404; path match with wrong method → 405.

## 4. Per-request exit stacks
- `request_response()` opens `fastapi_inner_astack` (request; closes after response sent) and `fastapi_function_astack` (function; closes after endpoint returns, before sending). `yield` dependencies use a stack according to `Depends(scope=...)`. If an exception is swallowed in a `yield` dependency’s `except` and the response is never sent, FastAPI raises `FastAPIError`.

## 5. Reading the body
- Only endpoints with body parameters read it. Form/File uses `await request.form()`; `AsyncExitStackMiddleware` closes the form/files at the end. Otherwise raw body is read; JSON parsing occurs only for `Content-Type: application/json` or `application/*+json`, or with no Content-Type when `strict_content_type=False`. Other types remain raw bytes and fail model-body validation. Invalid JSON → `RequestValidationError` type `json_invalid` (422); other parsing failures → `HTTPException(400, "There was an error parsing the body")`.

## 6. Solving dependencies and validating parameters
- `solve_dependencies()` traverses the `Dependant` tree depth-first, applies `app.dependency_overrides`, and caches per request by `(callable, security scopes, scope)` when `use_cache=True`. Otherwise it calls dependencies: generators via exit stacks, `async def` awaited, plain `def` in threadpool.
- Extracts and Pydantic-validates path/query/header/cookie/body values; collects **all** errors, then raises one `RequestValidationError` (422). Injects `Request`, temporary `Response`, shared `BackgroundTasks`, and `SecurityScopes`.

## 7. Running the endpoint
- `run_endpoint_function()` awaits `async def` on the event loop; plain `def` uses `run_in_threadpool`.
- Generator streaming: `response_class=EventSourceResponse` → Server-Sent Events; JSON Lines semantics → `StreamingResponse`, `media_type="application/jsonl"`, validating/serializing each item; explicit `response_class` (e.g. `StreamingResponse`) passes chunks through.

## 8. Building the response
- Returned `Response` is used as is, without validation/serialization; collected background tasks attach only if it has none. Otherwise `serialize_response()` validates against a response field (failure: `ResponseValidationError` → 500) and serializes with Pydantic options `response_model_include/exclude/by_alias/exclude_unset/exclude_defaults/exclude_none`; without a field, uses `jsonable_encoder`.
- With a response field and default response class, Pydantic serializes directly to JSON bytes, skipping intermediate dict + `json.dumps`; FastAPI returns `Response(media_type="application/json")`. Otherwise content goes to route `response_class` (default `JSONResponse`).
- Status is decorator `status_code` or injected `Response` status; body-forbidden statuses (e.g. 204, 304) have empty bodies. Injected `Response` headers/cookies are copied to final response.

## 9. After the response
- Order: function stack closes (function-scoped `yield` teardown); `await response(scope, receive, send)` sends body and runs background tasks after it; request stack closes (default request-scoped teardown); then `AsyncExitStackMiddleware` closes uploaded files. Don’t rely on `yield` dependency objects in background tasks; create their own resources.
