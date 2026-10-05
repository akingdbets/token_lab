---
type: reference
title: API Metadata and Docs UIs
description: Set API metadata (title, summary, description, version, terms_of_service, contact, license_info), describe tags with openapi_tags, change or disable openapi_url, docs_url and redoc_url, configure Swagger UI with swagger_ui_parameters, self-host docs assets, and disable docs conditionally.
tags: [openapi, metadata, swagger-ui, redoc, docs_url, openapi_tags, swagger_ui_parameters, conditional-openapi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-d522d5ea7409258d151bf874
    resource: repo://docs_src/conditional_openapi/tutorial001_py310.py
  - id: openwiki-source-8a34a13a0fe026887f8f1736
    resource: repo://docs_src/configure_swagger_ui/tutorial001_py310.py
  - id: openwiki-source-cbc675db4a850eabbf8ae464
    resource: repo://docs_src/custom_docs_ui/tutorial002_py310.py
  - id: openwiki-source-ebb59a8a93678406cad02490
    resource: repo://docs_src/metadata/tutorial001_1_py310.py
  - id: openwiki-source-5dc155895c2b4b1a0942a04e
    resource: repo://docs_src/metadata/tutorial001_py310.py
  - id: openwiki-source-4a9ed6fb9cecfaac688c0d72
    resource: repo://docs_src/metadata/tutorial004_py310.py
  - id: openwiki-source-62bed36ab9995da06c43fe2e
    resource: repo://docs/en/docs/how-to/conditional-openapi.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-71c560a9294248da86954ddc
    resource: repo://fastapi/openapi/docs.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# API Metadata and Docs UIs

## API metadata

`FastAPI(...)` parameters fill the OpenAPI `info` section shown at the top of the docs (`docs_src/metadata/tutorial001_py310.py`):

```python
from fastapi import FastAPI

description = """
ChimichangApp API helps you do awesome stuff. 🚀

## Items

You can **read items**.

## Users

You will be able to:

* **Create users** (_not implemented_).
* **Read users** (_not implemented_).
"""

app = FastAPI(
    title="ChimichangApp",
    description=description,
    summary="Deadpool's favorite app. Nuff said.",
    version="0.0.1",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Deadpoolio the Amazing",
        "url": "http://x-force.example.com/contact/",
        "email": "dp@x-force.example.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)
```

| Parameter | Type | Notes |
|-----------|------|-------|
| `title` | `str` | Default `"FastAPI"` |
| `summary` | `str` | Short summary (OpenAPI 3.1) |
| `description` | `str` | Markdown supported |
| `version` | `str` | **Your API's** version, default `"0.1.0"` (not FastAPI's or OpenAPI's) |
| `terms_of_service` | `str` | URL |
| `contact` | `dict` | `name`, `url`, `email` |
| `license_info` | `dict` | `name` (required) plus **either** `url` **or** an SPDX `identifier` such as `"Apache-2.0"` (`tutorial001_1_py310.py`) |

Other related parameters: `openapi_version` (default `"3.1.0"`), `servers` and `root_path` (see [Sub-applications, Proxies](../app-structure/sub-applications-proxy-and-wsgi.md)), `openapi_external_docs`, and `separate_input_output_schemas`.

## Tag metadata (`openapi_tags`)

Describe the tags used by your path operations; the list order is the order in the docs (`tutorial004_py310.py`):

```python
tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. The **login** logic is also here.",
    },
    {
        "name": "items",
        "description": "Manage items. So _fancy_ they have their own docs.",
        "externalDocs": {
            "description": "Items external docs",
            "url": "https://fastapi.tiangolo.com/",
        },
    },
]

app = FastAPI(openapi_tags=tags_metadata)


@app.get("/users/", tags=["users"])
async def get_users():
    return [{"name": "Harry"}, {"name": "Ron"}]
```

Each entry: `name` (required, same string as in `tags=[...]`), `description` (Markdown), `externalDocs` (`description`, `url`). You don't have to describe every tag you use.

## URLs of the schema and docs

| Parameter | Default | Set to `None` to |
|-----------|---------|------------------|
| `openapi_url` | `"/openapi.json"` | disable the schema **and** both docs UIs |
| `docs_url` | `"/docs"` | disable Swagger UI |
| `redoc_url` | `"/redoc"` | disable ReDoc |
| `swagger_ui_oauth2_redirect_url` | `"/docs/oauth2-redirect"` | disable the OAuth2 redirect page |

```python
app = FastAPI(openapi_url="/api/v1/openapi.json")          # tutorial002
app = FastAPI(docs_url="/documentation", redoc_url=None)   # tutorial003
```

The docs routes are only added when `openapi_url` is set (e.g. `if self.openapi_url and self.docs_url`), and they're registered with `include_in_schema=False`. Behind a proxy, the docs prepend the request's `root_path` to `openapi_url`.

## Configuring Swagger UI

Pass Swagger UI options with `swagger_ui_parameters`; they're merged over FastAPI's defaults (`swagger_ui_default_parameters` in `fastapi.openapi.docs`: `dom_id="#swagger-ui"`, `layout="BaseLayout"`, `deepLinking=True`, `showExtensions=True`, `showCommonExtensions=True`).

```python
# Disable syntax highlighting (tutorial001)
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": False})

# Change the highlight theme (tutorial002)
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": {"theme": "obsidian"}})

# Disable deep linking (tutorial003)
app = FastAPI(swagger_ui_parameters={"deepLinking": False})
```

Any JSON-serializable Swagger UI configuration works. JavaScript-only settings (functions) can't be passed this way — for those, build a custom docs page (below). `swagger_ui_init_oauth` passes OAuth2 init settings (e.g. `clientId`) to Swagger UI.

## Custom docs pages and self-hosted assets

By default the docs load JS/CSS from a CDN (`cdn.jsdelivr.net`, `swagger-ui-dist@5`, `redoc@2`). To use another CDN, or serve files yourself (e.g. offline or intranet), disable the automatic pages and add your own using `fastapi.openapi.docs` helpers (`docs_src/custom_docs_ui/tutorial002_py310.py`):

```python
from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles

app = FastAPI(docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )
```

- Download `swagger-ui-bundle.js`, `swagger-ui.css` and `redoc.standalone.js` into `static/` (`tutorial001_py310.py` shows the same with an alternative CDN like unpkg).
- Keep the OAuth2 redirect route if you use OAuth2 in Swagger UI's "Authorize" dialog.
- Other helper parameters include `swagger_favicon_url`, `swagger_ui_parameters` and `init_oauth`; `get_redoc_html` accepts `redoc_favicon_url` and `with_google_fonts`.

## Conditional OpenAPI

Hiding docs is **not** a security measure — endpoints remain reachable (security through obscurity). Secure your API with real authentication ([Security](../security/oauth2-password-flow.md)). If you still want docs off in some environments, drive `openapi_url` from settings (`docs_src/conditional_openapi/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openapi_url: str = "/openapi.json"


settings = Settings()

app = FastAPI(openapi_url=settings.openapi_url)
```

```bash
OPENAPI_URL= uvicorn main:app
```

An empty `openapi_url` disables the schema and the docs UIs (requests to `/openapi.json`, `/docs`, `/redoc` return 404). See [Settings](../app-structure/settings.md).

## Related

- [Path Operation Configuration](../app-structure/path-operation-configuration.md) — per-operation summary, description, tags, deprecated
- [Extending OpenAPI](extending-openapi.md)
- [First Steps](../getting-started/first-steps.md)
