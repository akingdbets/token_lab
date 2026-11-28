- **Using the `Request` directly**
  - Normally declare needed path, query, and body parameters; FastAPI validates, converts, and documents them. For raw request data, declare a parameter typed `Request`:
    ```python
    from fastapi import FastAPI, Request
    ```
  - `fastapi.Request` is Starlette's `Request`; `fastapi/requests.py` also re-exports `HTTPConnection`, the common base of `Request` and `WebSocket`.
  - Other parameters, such as `item_id`, remain validated and documented. Data read directly (`await request.body()`, `await request.json()`, `request.query_params`) is not validated, converted, or documented.
  - Useful attributes: `request.method`, `request.url`, `request.headers`, `request.query_params`, `request.path_params`, `request.cookies`, `request.client` (`host`, `port`), `request.state`, `request.app`, `request.scope`, and `await request.body()` / `json()` / `form()` / `stream()`. `Request` can be injected in dependencies and is passed to middleware and exception handlers.

- **Strict `Content-Type` checking**
  - Since FastAPI **0.132.0**, JSON bodies are parsed only with `Content-Type: application/json` or `application/*+json`. Without `Content-Type`, JSON parsing does not occur and a model body fails validation.
  - This protects against browser cross-origin POSTs without CORS preflight: scripts can send requests without `Content-Type` (e.g. `fetch()` with a `Blob` body) and without credentials. The described risk is an unauthenticated local AI agent API trusting the local network. This matters mainly for `localhost` or internal-network apps protected only by network trust; privileged endpoints on the open internet must authenticate anyway.
  - To accept omitted headers, use `FastAPI(strict_content_type=False)` or `APIRouter(...)` with the flag. Omitted `Content-Type` bodies are then parsed as JSON (pre-0.132 behavior); the flag is stored on each `APIRoute`. A non-JSON `Content-Type`, e.g. `text/plain`, is never parsed as JSON, regardless of the flag.

- **Custom `Request` and `APIRoute` classes**
  - Override `APIRoute.get_route_handler()` to wrap the original handler while retaining FastAPI validation; set the class on the app router or an `APIRouter`. Use this only for things not achievable with dependencies or middleware.
  - For gzip bodies, `GzipRequest(Request).body()` checks `"gzip" in self.headers.getlist("Content-Encoding")`, decompresses with `gzip.decompress(body)`, and caches once in `_body`. A `Request` uses the ASGI `scope` dict and `receive` callable. `app.router.route_class = GzipRoute` applies to routes declared afterwards.
  - On validation failure, `ValidationErrorLoggingRoute` can catch `RequestValidationError`, read `await request.body()`, and raise `HTTPException(status_code=422, detail={"errors": exc.errors(), "body": body.decode()})`. A simpler alternative for most apps is a `RequestValidationError` exception handler using `exc.body`.
  - Set `APIRouter(route_class=TimedRoute)` for per-router timing: the handler measures `time.time()` around the original handler and sets `response.headers["X-Response-Time"] = str(duration)`. Only `/timed` gets that header. Unlike middleware, this runs inside the route, after routing, with access to FastAPI's handler.
