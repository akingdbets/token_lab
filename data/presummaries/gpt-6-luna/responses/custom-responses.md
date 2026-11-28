- **Overview**
  - By default, FastAPI converts returned data to JSON using the response model or `jsonable_encoder`, and sends it as `application/json`. You can return a `Response` yourself or choose a response class.
  - `fastapi.responses` re-exports Starlette’s `Response`, `JSONResponse`, `HTMLResponse`, `PlainTextResponse`, `RedirectResponse`, `StreamingResponse`, and `FileResponse`, plus FastAPI’s `EventSourceResponse`. `Response` is also importable from `fastapi`.

- **Returning a `Response` directly**
  - Any `Response` instance or subclass is sent as is: no validation, response-model filtering, or conversion. Ensure content is serializable; `jsonable_encoder` can convert values such as `datetime` to strings.
  - Any content type is supported, e.g. `Response(content=data, media_type="application/xml")`.
  - `Response(content, status_code=200, headers=None, media_type=None)`; FastAPI/Starlette add `Content-Length` and, for text types, charset in `Content-Type`.
  - Useful for custom status codes, headers/cookies, or non-JSON content. Direct responses’ shape is not known to OpenAPI; document with `response_class` and/or `responses=`.

- **`response_class`**
  - On a decorator, selects the class used for returned content and documents its media type in OpenAPI. Returning `HTMLResponse(...)` directly works, but OpenAPI shows JSON; `response_class=HTMLResponse` plus returning a response from a helper provides correct docs and control.

- **Available response classes**
  - `Response`: base class, any content and `media_type`.
  - `JSONResponse`: stdlib `json`, classic default; e.g. `JSONResponse(content={...}, status_code=201)`.
  - `HTMLResponse`: `text/html`; `PlainTextResponse`: `text/plain`.
  - `RedirectResponse`: HTTP redirect, default **307**. With `response_class=RedirectResponse`, return just a URL; `status_code` overrides 307.
  - `StreamingResponse`: streams an (async) iterator or sync generator; file-like objects can be streamed with `yield from`. Supports streaming patterns including JSON Lines.
  - `FileResponse`: asynchronously streams a file; arguments `path`, `headers`, `media_type` (guessed from filename if omitted), `filename` (sets `Content-Disposition` for browser downloads). Sets `Content-Length`, `Last-Modified`, and `ETag`. With `response_class=FileResponse`, return just the path.
  - `EventSourceResponse`: Server-Sent Events.

- **Custom response classes**
  - Subclass `Response` and implement `render(content) -> bytes`. Example uses `CustomORJSONResponse(Response)` with `media_type = "application/json"` and `orjson.dumps(content, option=orjson.OPT_INDENT_2)`; asserts `orjson` is installed.

- **Default response class**
  - Set `default_response_class` on `FastAPI`, `APIRouter`, or `include_router`; individual operations can override it with `response_class`.

- **JSON performance**
  - With a response model/return type and no `response_class`, FastAPI validates with Pydantic and serializes directly to JSON bytes using Pydantic’s Rust core—no intermediate `jsonable_encoder` + `json.dumps`; this is fastest.
  - With `response_class=JSONResponse` or another JSON class, response-model filtering still occurs, then `jsonable_encoder` and that class serialize the data; this is slower.
  - `ORJSONResponse` and `UJSONResponse` are deprecated and emit `FastAPIDeprecationWarning`; response models provide the same Rust-level speed without extra packages. Existing use still works if `orjson`/`ujson` is installed.
