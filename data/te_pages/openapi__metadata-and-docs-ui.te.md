---
type: reference
title: API metadata and docs UIs
description: Set API metadata (`title`, `summary`, `description`, `version`, `terms_of_service`, `contact`, `license_info`); describe tags with `openapi_tags`; change or disable `openapi_url`, `docs_url`, and `redoc_url`; configure swagger UI with `swagger_ui_parameters`; self-host docs assets; disable docs conditionally.
tags: [OpenAPI, metadata, swagger-ui, redoc, docs_url, openapi_tags, swagger_ui_parameters, conditional-OpenAPI]
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
    resource: repo://FastAPI/applications.py
  - id: openwiki-source-71c560a9294248da86954ddc
    resource: repo://FastAPI/OpenAPI/docs.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: API metadata and docs UIs

H2: API metadata

`FastAPI(...)` PARAMETERS POPULATE OpenAPI `info` SECTION AT TOP OF docs
SOURCE: `docs_src/metadata/tutorial001_py310.py`

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
| `title` | `str` | DEFAULT `"FastAPI"` |
| `summary` | `str` | SHORT summary; OpenAPI 3.1 |
| `description` | `str` | SUPPORTS MARKDOWN |
| `version` | `str` | YOUR API version; DEFAULT `"0.1.0"`; NOT FastAPI OR OpenAPI version |
| `terms_of_service` | `str` | URL |
| `contact` | `dict` | `name`, `url`, `email` |
| `license_info` | `dict` | REQUIRED `name` + EITHER `url` OR SPDX `identifier`, e.g. `"Apache-2.0"`; SOURCE `tutorial001_1_py310.py` |

RELATED PARAMETERS: `openapi_version` (DEFAULT `"3.1.0"`), `servers`, `root_path` (SEE [Sub-applications, Proxies](../app-structure/sub-applications-proxy-and-wsgi.md)), `openapi_external_docs`, `separate_input_output_schemas`.

H2: Tag metadata (`openapi_tags`)

DESCRIBE PATH-OPERATION tags; LIST ORDER = ORDER IN docs; SOURCE `tutorial004_py310.py`

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

EACH ENTRY: REQUIRED `name` (SAME STRING AS IN `tags=[...]`); `description` (MARKDOWN); `externalDocs` (`description`, `url`). DESCRIBING EVERY TAG NOT REQUIRED.

H2: URLs of the schema and docs

| Parameter | Default | Set to `None` to |
|-----------|---------|------------------|
| `openapi_url` | `"/openapi.json"` | DISABLE SCHEMA and BOTH docs UIs |
| `docs_url` | `"/docs"` | DISABLE swagger UI |
| `redoc_url` | `"/redoc"` | DISABLE REDOC |
| `swagger_ui_oauth2_redirect_url` | `"/docs/oauth2-redirect"` | DISABLE OAUTH2 redirect PAGE |

```python
app = FastAPI(openapi_url="/api/v1/openapi.json")          # tutorial002
app = FastAPI(docs_url="/documentation", redoc_url=None)   # tutorial003
```

docs ROUTES ADDED ONLY if `openapi_url` IS SET (e.g. `if self.openapi_url and self.docs_url`); REGISTERED WITH `include_in_schema=False`. BEHIND A PROXY, docs PREPEND REQUEST `root_path` TO `openapi_url`.

H2: Configuring swagger UI

PASS swagger UI OPTIONS WITH `swagger_ui_parameters`; OPTIONS MERGE OVER FastAPI DEFAULTS (`swagger_ui_default_parameters` IN `fastapi.openapi.docs`: `dom_id="#swagger-ui"`, `layout="BaseLayout"`, `deepLinking=True`, `showExtensions=True`, `showCommonExtensions=True`).

```python
# Disable syntax highlighting (tutorial001)
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": False})

# Change the highlight theme (tutorial002)
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": {"theme": "obsidian"}})

# Disable deep linking (tutorial003)
app = FastAPI(swagger_ui_parameters={"deepLinking": False})
```

ANY JSON-SERIALIZABLE swagger UI CONFIGURATION WORKS. JavaScript-ONLY SETTINGS (FUNCTIONS) CANNOT PASS THIS WAY; BUILD A CUSTOM docs PAGE INSTEAD (BELOW). `swagger_ui_init_oauth` PASSES OAUTH2 INIT SETTINGS (e.g. `clientId`) TO swagger UI.

H2: Custom docs pages and self-hosted assets

DEFAULT docs LOAD JS/CSS FROM CDN (`cdn.jsdelivr.net`, `swagger-ui-dist@5`, `redoc@2`). TO USE ANOTHER CDN OR SERVE FILES YOURSELF (e.g. OFFLINE OR INTRANET), DISABLE AUTOMATIC PAGES and ADD YOUR OWN WITH `fastapi.openapi.docs` HELPERS; SOURCE `docs_src/custom_docs_ui/tutorial002_py310.py`:

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
- DOWNLOAD `swagger-ui-bundle.js`, `swagger-ui.css` and `redoc.standalone.js` INTO `static/`; `tutorial001_py310.py` SHOWS SAME WITH ALTERNATIVE CDN LIKE unpkg
- KEEP OAUTH2 redirect ROUTE if USING OAUTH2 IN swagger UI'S "Authorize" DIALOG
- OTHER HELPER PARAMETERS: `swagger_favicon_url`, `swagger_ui_parameters`, `init_oauth`; `get_redoc_html` ACCEPTS `redoc_favicon_url` and `with_google_fonts`

H2: Conditional OpenAPI

HIDING docs ≠ SECURITY MEASURE; ENDPOINTS REMAIN REACHABLE (SECURITY THROUGH OBSCURITY)
SECURE API WITH REAL AUTHENTICATION ([Security](../security/oauth2-password-flow.md))
if docs SHOULD BE OFF IN SOME ENVIRONMENTS, DRIVE `openapi_url` FROM SETTINGS (`docs_src/conditional_openapi/tutorial001_py310.py`):

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

EMPTY `openapi_url` DISABLES SCHEMA and docs UIs; REQUESTS TO `/openapi.json`, `/docs`, `/redoc` RETURN 404
SEE [Settings](../app-structure/settings.md)

H2: Related

- [Path Operation Configuration](../app-structure/path-operation-configuration.md) — PER-OPERATION summary, description, tags, DEPRECATED
- [Extending OpenAPI](extending-openapi.md)
- [First Steps](../getting-started/first-steps.md)
