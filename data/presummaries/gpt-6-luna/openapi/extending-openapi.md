- **Additional responses (`responses=`)**
  - Path operation decorators, `APIRouter`, and `include_router` accept `responses`: a dict mapping status codes (or e.g. `"default"`) to OpenAPI Response Object dicts. It accepts OpenAPI fields such as `description`, `headers`, `content`, and `links`, plus FastAPI’s special `model` key.
  - These responses are **documentation only**. To send one, return a `Response` (e.g. `JSONResponse` or `FileResponse`) with the appropriate status and content.
  - `model` is not OpenAPI: FastAPI creates its JSON Schema under `components/schemas` and references it at `content → application/json → schema`.
  - `responses={404: {"model": Message}}` documents a model for 404; the handler must still return a response such as `JSONResponse(status_code=404, content=...)`.
  - `responses={200: {"content": {"image/png": {}}, "description": ...}}` adds PNG alongside JSON derived from `response_model`. If a custom response class has `media_type=None`, FastAPI uses `application/json` for additional responses with a model.
  - FastAPI merges `responses` with details derived from `response_model` and `status_code`. Response entries can include `description` and examples under `content → application/json → example`. Predefined response dicts can be reused and expanded (e.g. `{**responses, 200: ...}`); router-level `responses` merge into each operation.

- **Overriding the whole schema**
  - `app.openapi()` generates the schema once and caches it in `app.openapi_schema`. Replace it with a function calling `fastapi.openapi.utils.get_openapi`; return the cache when present, save the generated schema to `app.openapi_schema`, and return it.
  - `get_openapi()` arguments: `title`, `version`, `openapi_version` (default `"3.1.0"`), `summary`, `description`, `routes`, `webhooks`, `tags`, `servers`, `terms_of_service`, `contact`, `license_info`, `separate_input_output_schemas`, `external_docs`. The example adds ReDoc’s `x-logo` extension to `openapi_schema["info"]`.
  - FastAPI warns about duplicate operation IDs (`Duplicate Operation ID ... for function ...`); fix them for clean client generation. Prefer `openapi_extra` for per-operation tweaks and `FastAPI(title=..., openapi_tags=...)` for metadata.

- **OpenAPI callbacks**
  - A callback is a request your API sends to an external API built by your API’s user. Document its endpoint with an `APIRouter` and pass `callbacks=invoices_callback_router.routes` to the path operation. The callback router is documentation only: it is never included in the app and its function is never executed.
  - Callback paths can use OpenAPI runtime expressions: `{$callback_url}` refers to the original request’s `callback_url` query parameter; `{$request.body.id}` refers to `id` in its body. The docs UI shows “Callbacks”. Sending the callback is your code’s responsibility (e.g. `httpx.post(...)`).

- **Webhooks**
  - Webhooks are not tied to a specific request: users register a URL and the app sends events to it. OpenAPI 3.1 supports documenting webhooks; FastAPI support requires ≥ 0.99.0. Use `app.webhooks`, which works like a router (e.g. `@app.webhooks.post("new-subscription")`).
  - The webhook name is an identifier, not a URL path; the URL is whatever the user registers. Webhooks appear in OpenAPI (`webhooks`) and the docs UI. Registering URLs and sending requests are your code’s responsibility.
