---
type: guide
title: "Extending OpenAPI: Additional responses, callbacks and webhooks"
description: DOCUMENT EXTRA Response STATUS CODES, MODELS, MEDIA TYPES AND EXAMPLES WITH responses=; CUSTOMIZE THE WHOLE schema BY OVERRIDING app.openapi WITH get_openapi; DOCUMENT OUTGOING callbacks AND webhooks.
tags: [OpenAPI, additional-responses, responses, get_openapi, callbacks, webhooks, schema]
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
    resource: repo://docs/en/docs/advanced/OpenAPI-callbacks.md
  - id: openwiki-source-6be36cbacef48d41c20c7a17
    resource: repo://docs/en/docs/advanced/OpenAPI-webhooks.md
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://FastAPI/OpenAPI/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Extending OpenAPI: Additional responses, callbacks and webhooks

FastAPI GENERATES OpenAPI AUTOMATICALLY.
THIS PAGE COVERS DOCUMENTING WHAT IT CANNOT INFER ∧ CUSTOMIZING THE RESULT.

H2: Additional responses (`responses=`)

PATH Operation DECORATORS (AND `APIRouter` / `include_router`) ACCEPT `responses`:
DICT MAPPING STATUS CODES (OR e.g. `"default"`) TO OpenAPI Response OBJECT DICTS.
ANY VALID OpenAPI Response OBJECT content IS ALLOWED:
`description`, `headers`, `content`, `links`; ALSO FastAPI'S SPECIAL `model` KEY.

> THESE responses ARE DOCUMENTED ONLY.
> TO SEND THEM, RETURN A `Response` (e.g. `JSONResponse` OR `FileResponse`)
> DIRECTLY, WITH THE RIGHT STATUS AND content.

H3: With a model

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

(`docs_src/additional_responses/tutorial001_py310.py`.)
`model` IS NOT OpenAPI; FastAPI TURNS IT INTO JSON schema UNDER
`components/schemas` AND REFERENCES IT FROM
`content → application/json → schema`.

H3: Additional media types for the main Response

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

(`tutorial002_py310.py`.)
THE 200 Response IS DOCUMENTED AS JSON (FROM `response_model`) AND PNG.
IF A CUSTOM Response CLASS HAS `media_type=None`, FastAPI USES
`application/json` for ADDITIONAL responses WITH A model.

H3: Combining information

FastAPI MERGES `responses` WITH INFORMATION DERIVED FROM `response_model`
AND `status_code` (`tutorial003_py310.py`):

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

H3: Reusable predefined responses

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

(`tutorial004_py310.py`.)
ROUTER-LEVEL `responses` ARE MERGED INTO EACH Operation
(SEE [BIGGER APPLICATIONS](../app-structure/bigger-applications.md)).

H2: Overriding the whole schema

`app.openapi()` GENERATES THE schema ONCE AND CACHES IT IN
`app.openapi_schema`.
TO CUSTOMIZE, REPLACE THE METHOD WITH YOUR function, CALLING
`fastapi.openapi.utils.get_openapi`
(`docs_src/extending_openapi/tutorial001_py310.py`):

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

`get_openapi()` KEYWORD ARGUMENTS:
`title`, `version`, `openapi_version` (default `"3.1.0"`), `summary`,
`description`, `routes`, `webhooks`, `tags`, `servers`,
`terms_of_service`, `contact`, `license_info`,
`separate_input_output_schemas`, `external_docs`.
CACHING IN `app.openapi_schema` AVOIDS REGENERATION ON EVERY REQUEST.
HERE, THE ReDoc-SPECIFIC `x-logo` EXTENSION IS ADDED.

DURING GENERATION, FastAPI WARNS ABOUT Duplicate Operation IDs
(`Duplicate Operation ID ... for function ...`).
FIX THESE for CLEAN CLIENT GENERATION.

for PER-Operation TWEAKS, PREFER `openapi_extra`
([PATH Operation CONFIGURATION](../app-structure/path-Operation-configuration.md));
for METADATA, USE `FastAPI(title=..., openapi_tags=...)`
([API METADATA AND DOCS UIs](metadata-and-docs-ui.md)).

H2: OpenAPI callbacks

A CALLBACK IS A REQUEST YOUR API SENDS TO AN EXTERNAL API
(BUILT BY YOUR API'S USER), e.g. "Invoice paid" NOTIFICATIONS.
DOCUMENT THE REQUIRED SHAPE OF THAT EXTERNAL ENDPOINT
(`docs_src/openapi_callbacks/tutorial001_py310.py`):

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
- CALLBACK ROUTER IS DOCUMENTATION-ONLY: NEVER INCLUDED IN APP; function NEVER EXECUTES (`pass` BODY).
- PATH IS OpenAPI RUNTIME EXPRESSION: `{$callback_url}` REFERS TO ORIGINAL REQUEST'S `callback_url` QUERY PARAMETER; `{$request.body.id}` REFERS TO BODY'S `id`.
- pass `callbacks=invoices_callback_router.routes` TO PATH Operation; DOCS UI SHOWS "callbacks" SECTION.
- SENDING CALLBACK IS YOUR RESPONSIBILITY; e.g. `httpx.post(callback_url, json={"description": "Invoice paid", "paid": True})`.

H2: webhooks

webhooks ARE SIMILAR, BUT NOT TIED TO A SPECIFIC REQUEST: USER REGISTERS URL (e.g. IN DASHBOARD); APP SENDS EVENTS TO IT. OpenAPI 3.1 SUPPORTS DOCUMENTING webhooks (FastAPI ≥ 0.99.0). USE `app.webhooks`, WHICH WORKS LIKE A ROUTER (`docs_src/openapi_webhooks/tutorial001_py310.py`):

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

NAME ("new-subscription") IS AN IDENTIFIER, NOT A URL PATH; URL IS WHATEVER USER REGISTERS. webhooks APPEAR IN OpenAPI (`webhooks`) AND DOCS UI. REGISTERING URLs AND SENDING REQUESTS IS YOUR CODE'S JOB.

H2: Related

- [API METADATA AND DOCS UIs](metadata-and-docs-ui.md)
- [GENERATING SDK CLIENTS](generating-clients.md)
- [CUSTOM responses](../responses/custom-responses.md)
