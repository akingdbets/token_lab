---
type: guide
title: "Extending OpenAPI: Additional Responses, Callbacks and Webhooks"
description: Document extra response status codes, models, media types and examples with responses=, customize the whole schema by overriding app.openapi with get_openapi, and document outgoing callbacks and webhooks.
tags: [openapi, additional-responses, responses, get_openapi, callbacks, webhooks, schema]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-7cc48311268aa0d38d19fddb
    resource: repo://docs_src/additional_responses/tutorial001_py310.py
  - id: openwiki-source-519b9f75ea66441d1eec4826
    resource: repo://docs_src/additional_responses/tutorial002_py310.py
  - id: openwiki-source-60dfdf714574820fae613649
    resource: repo://docs_src/additional_responses/tutorial003_py310.py
  - id: openwiki-source-27218b8fe711ff478446fffa
    resource: repo://docs_src/extending_openapi/tutorial001_py310.py
  - id: openwiki-source-888d96f6fc5d92d8169decac
    resource: repo://docs_src/openapi_callbacks/tutorial001_py310.py
  - id: openwiki-source-38d361bd8ca97b84b5de187d
    resource: repo://docs_src/openapi_webhooks/tutorial001_py310.py
  - id: openwiki-source-724e759f2e2841d6ad6ccb8b
    resource: repo://docs/en/docs/advanced/additional-responses.md
  - id: openwiki-source-425df282d44c2c18b97b213e
    resource: repo://docs/en/docs/advanced/openapi-callbacks.md
  - id: openwiki-source-6be36cbacef48d41c20c7a17
    resource: repo://docs/en/docs/advanced/openapi-webhooks.md
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://fastapi/openapi/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Extending OpenAPI: Additional Responses, Callbacks and Webhooks

FastAPI generates OpenAPI automatically. This page covers documenting what it can't infer, and customizing the result.

## Additional responses (`responses=`)

Path operation decorators (and `APIRouter` / `include_router`) accept `responses`: a dict mapping status codes (or e.g. `"default"`) to OpenAPI Response Object dicts. Anything valid in an OpenAPI Response Object can go there (`description`, `headers`, `content`, `links`), plus FastAPI's special `model` key.

> These only **document** responses. To actually send them, return a `Response` (like `JSONResponse` or `FileResponse`) directly with the right status and content.

### With a model

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Item(BaseModel):
    id: str
    value: str


class Message(BaseModel):
    message: str


app = FastAPI()


@app.get("/items/{item_id}", response_model=Item, responses={404: {"model": Message}})
async def read_item(item_id: str):
    if item_id == "foo":
        return {"id": "foo", "value": "there goes my hero"}
    return JSONResponse(status_code=404, content={"message": "Item not found"})
```

(`docs_src/additional_responses/tutorial001_py310.py`.) `model` is not OpenAPI; FastAPI turns it into a JSON Schema placed under `components/schemas` and references it from `content → application/json → schema`.

### Additional media types for the main response

```python
@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Return the JSON item or an image.",
        }
    },
)
async def read_item(item_id: str, img: bool | None = None):
    if img:
        return FileResponse("image.png", media_type="image/png")
    else:
        return {"id": "foo", "value": "there goes my hero"}
```

(`tutorial002_py310.py`.) The 200 response is documented as both JSON (from `response_model`) and PNG. If a custom response class has `media_type=None`, FastAPI uses `application/json` for additional responses with a model.

### Combining information

FastAPI merges `responses` with what it derives from `response_model` and `status_code` (`tutorial003_py310.py`):

```python
@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={
        404: {"model": Message, "description": "The item was not found"},
        200: {
            "description": "Item requested by ID",
            "content": {
                "application/json": {
                    "example": {"id": "bar", "value": "The bar tenders"}
                }
            },
        },
    },
)
```

### Reusable predefined responses

```python
responses = {
    404: {"description": "Item not found"},
    302: {"description": "The item was moved"},
    403: {"description": "Not enough privileges"},
}


@app.get(
    "/items/{item_id}",
    response_model=Item,
    responses={**responses, 200: {"content": {"image/png": {}}}},
)
```

(`tutorial004_py310.py`.) Router-level `responses` are merged into each operation (see [Bigger Applications](../app-structure/bigger-applications.md)).

## Overriding the whole schema

`app.openapi()` generates the schema once and caches it in `app.openapi_schema`. To customize, replace the method with your own function that calls `fastapi.openapi.utils.get_openapi` (`docs_src/extending_openapi/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI()


@app.get("/items/")
async def read_items():
    return [{"name": "Foo"}]


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Custom title",
        version="2.5.0",
        summary="This is a very custom OpenAPI schema",
        description="Here's a longer description of the custom **OpenAPI** schema",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
```

`get_openapi()` keyword arguments: `title`, `version`, `openapi_version` (default `"3.1.0"`), `summary`, `description`, `routes`, `webhooks`, `tags`, `servers`, `terms_of_service`, `contact`, `license_info`, `separate_input_output_schemas`, `external_docs`. Caching in `app.openapi_schema` avoids regenerating on every request. Here the ReDoc-specific `x-logo` extension is added.

While generating, FastAPI warns about duplicate operation IDs (`Duplicate Operation ID ... for function ...`) — fix those for clean client generation.

For per-operation tweaks prefer `openapi_extra` ([Path Operation Configuration](../app-structure/path-operation-configuration.md)); for metadata use `FastAPI(title=..., openapi_tags=...)` ([API Metadata and Docs UIs](metadata-and-docs-ui.md)).

## OpenAPI callbacks

A **callback** is a request *your* API sends to an *external* API (built by your API's user) — e.g. "invoice paid" notifications. You can document what that external endpoint must look like (`docs_src/openapi_callbacks/tutorial001_py310.py`):

```python
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, HttpUrl

app = FastAPI()


class Invoice(BaseModel):
    id: str
    title: str | None = None
    customer: str
    total: float


class InvoiceEvent(BaseModel):
    description: str
    paid: bool


class InvoiceEventReceived(BaseModel):
    ok: bool


invoices_callback_router = APIRouter()


@invoices_callback_router.post(
    "{$callback_url}/invoices/{$request.body.id}", response_model=InvoiceEventReceived
)
def invoice_notification(body: InvoiceEvent):
    pass


@app.post("/invoices/", callbacks=invoices_callback_router.routes)
def create_invoice(invoice: Invoice, callback_url: HttpUrl | None = None):
    # Send the invoice, collect the money, send the notification (the callback)
    return {"msg": "Invoice received"}
```

- The callback router is **documentation only**: it is never included in the app and its function is never executed (body is `pass`).
- The path is an OpenAPI **runtime expression**: `{$callback_url}` refers to the `callback_url` query parameter of the original request, `{$request.body.id}` to the `id` in its body.
- Pass `callbacks=invoices_callback_router.routes` to the path operation. The docs UI then shows a "Callbacks" section.
- Actually sending the callback is up to you, e.g. `httpx.post(callback_url, json={"description": "Invoice paid", "paid": True})`.

## Webhooks

Webhooks are similar, but not tied to a specific request: the user registers a URL (e.g. in your dashboard) and your app sends events to it. OpenAPI 3.1 supports documenting them (FastAPI ≥ 0.99.0). Use `app.webhooks`, which works like a router (`docs_src/openapi_webhooks/tutorial001_py310.py`):

```python
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Subscription(BaseModel):
    username: str
    monthly_fee: float
    start_date: datetime


@app.webhooks.post("new-subscription")
def new_subscription(body: Subscription):
    """
    When a new user subscribes to your service we'll send you a POST request with this
    data to the URL that you register for the event `new-subscription` in the dashboard.
    """
```

The name (`"new-subscription"`) is an identifier, not a URL path — the URL is whatever the user registers. Webhooks appear in OpenAPI (`webhooks`) and in the docs UI. Registering URLs and sending the requests is your code's job.

## Related

- [API Metadata and Docs UIs](metadata-and-docs-ui.md)
- [Generating SDK Clients](generating-clients.md)
- [Custom Responses](../responses/custom-responses.md)
