---
type: guide
title: sub-applications, Running Behind a proxy and WSGI
description: Mount independent FastAPI sub-applications, run behind proxies with Forwarded headers and stripped path prefixes using root_path, control OpenAPI servers, and mount Flask/Django apps with WSGIMiddleware from a2wsgi.
tags: [mount, sub-application, proxy, root_path, Forwarded-headers, servers, wsgi, flask]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-effe94f8043a35d0186d780a
    resource: repo://docs_src/behind_a_proxy/tutorial004_py310.py
  - id: openwiki-source-88f50dcab11ba0d187804a87
    resource: repo://docs_src/sub_applications/tutorial001_py310.py
  - id: openwiki-source-21bf9277556b9d32e99e0116
    resource: repo://docs_src/wsgi/tutorial001_py310.py
  - id: openwiki-source-d03ec1ead9cc2906107417f9
    resource: repo://docs/en/docs/advanced/behind-a-proxy.md
  - id: openwiki-source-b21ef06672269e7ba87c1e95
    resource: repo://docs/en/docs/advanced/sub-applications.md
  - id: openwiki-source-a260e848c29a17323d5b58da
    resource: repo://docs/en/docs/advanced/wsgi.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://FastAPI/applications.py
  - id: openwiki-source-8d245b8dfa52fb051edbd6f7
    resource: repo://FastAPI/middleware/wsgi.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: sub-applications, Running Behind a proxy and WSGI

scope: Mount ASGI apps under paths; configure FastAPI For reverse proxies;
embed legacy WSGI apps.

H2: Mounting a sub-application

MOUNTED app IS INDEPENDENT: OWN PATH OPERATIONS, OpenAPI SCHEMA, docs UI.
VS `APIRouter`: OPERATIONS JOIN MAIN app; SEE [BIGGER APPLICATIONS](bigger-applications.md).

`docs_src/sub_applications/tutorial001_py310.py`:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/app")
def read_main():
    return {"message": "Hello World from main app"}


subapi = FastAPI()


@subapi.get("/sub")
def read_sub():
    return {"message": "Hello World from sub API"}


app.mount("/subapi", subapi)
```

- `GET /app` → `app`; `GET /subapi/sub` → `subapi`.
- `/docs` shows only `app` operations; `/subapi/docs` shows only
  `subapi` operations, with correct `/subapi` URLs.
- Mounting passes mount path via ASGI `root_path`;
  nested mounts and docs UIs keep working.
- Lifespan events run only For main app, not mounted apps
  ([LIFESPAN EVENTS](lifespan-events.md)).
- Main-app dependencies do not apply to mounted apps.

`app.mount()` supports any ASGI app: `StaticFiles`
([STATIC FILES](static-files-templates-and-frontend.md)), GraphQL apps,
WSGI wrappers.

H2: Behind a proxy: Forwarded headers

proxy (TRAEFIK, NGINX, CLOUD LOAD BALANCER) TYPICALLY TERMINATES HTTPS;
FORWARDS PLAIN HTTP TO SERVER; ADDS:

- `X-Forwarded-For`: original client IP.
- `X-Forwarded-Proto`: original scheme (`https`).
- `X-Forwarded-Host`: original Host.

SECURITY: SERVER IGNORES headers UNLESS proxy IS TRUSTED.
FastAPI CLI (UVICORN):

```bash
fastapi run --forwarded-allow-ips="*"
```

`"*"` trusts every client IP; use only if nothing but the proxy can reach
the server.
EFFECT: AUTOMATIC REDIRECTS (e.g. `/items` → `/items/` For
`@app.get("/items/")`); `url_for()` builds
`https://mysuperapp.com/items/` instead of `http://localhost:8000/items/`.

H2: Behind a proxy with a stripped path prefix: `root_path`

proxy MAY EXPOSE app AT `https://example.com/api/v1/...` BUT FORWARD
WITHOUT prefix (`/app`, NOT `/api/v1/app`).
app NEEDS prefix: docs UI FETCHES `/api/v1/openapi.json`; GENERATED URLs
ARE CORRECT.
ASGI NAME For prefix: `root_path`.

SET VIA COMMAND LINE:

```bash
fastapi run main.py --forwarded-allow-ips="*" --root-path /api/v1
```

OR SET IN CODE IF CLI OPTIONS CANNOT BE PASSED
(`docs_src/behind_a_proxy/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Request

app = FastAPI(root_path="/api/v1")


@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}
```

IF `root_path` IS SET ON app, `FastAPI.__call__` WRITES IT INTO EVERY
REQUEST'S `scope["root_path"]`.
EITHER WAY, SERVER SERVES PATH WITHOUT prefix
(`http://127.0.0.1:8000/app`); ADDING `/api/v1` IS proxy'S JOB.
docs ENDPOINTS prefix `openapi_url` AND OAuth2 REDIRECT URL WITH CURRENT
`root_path`.

IF proxy DOES NOT STRIP prefix (FORWARDS `/api/v1/app` AS-IS),
`root_path` IS UNNECESSARY.
INSTEAD, PUT prefix IN ROUTES, e.g. `include_router(prefix="/api/v1")`.
H2: OpenAPI `servers`

IF request has non-empty `root_path`, `/openapi.json` inserts
`{"url": root_path}` at start of `servers`, unless identical URL exists.
add servers For docs UI targeting multiple environments
(`docs_src/behind_a_proxy/tutorial003_py310.py`):

```python
app = FastAPI(
    servers=[
        {"url": "https://stag.example.com", "description": "Staging environment"},
        {"url": "https://prod.example.com", "description": "Production environment"},
    ],
    root_path="/api/v1",
)
```

RESULT: `servers: [{"url": "/api/v1"}, {"url": "https://stag..."}, {"url": "https://prod..."}]`.
IF no `servers` are given AND `root_path` is `/`,
omit `servers` key entirely.

DISABLE automatic `root_path` server: pass `root_path_in_servers=False`
(`tutorial004_py310.py`).

`openapi_prefix` is deprecated; use `root_path`.

Mounting sub-apps behind a proxy with `root_path` works as expected;
FastAPI combines paths.

H2: INCLUDING WSGI APPS (Flask, Django, …)

Wrap WSGI app with `WSGIMiddleware` and mount it.
Use `a2wsgi` package (`uv add a2wsgi`);
`fastapi.middleware.wsgi.WSGIMiddleware` (re-export of Starlette's) is deprecated.

`docs_src/wsgi/tutorial001_py310.py`:

```python
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from flask import Flask, request
from markupsafe import escape

flask_app = Flask(__name__)


@flask_app.route("/")
def flask_main():
    name = request.args.get("name", "World")
    return f"Hello, {escape(name)} from Flask!"


app = FastAPI()


@app.get("/v2")
def read_main():
    return {"message": "Hello World"}


app.mount("/v1", WSGIMiddleware(flask_app))
```

Requests under `/v1/` go to Flask; all others go to FastAPI.
COMMON: migrate app incrementally.

H2: RELATED

- [HTTPS, TLS TERMINATION AND CLOUD PROVIDERS](../deployment/https-and-cloud.md)
- [DEPLOYING WITH DOCKER](../deployment/docker.md) — `--proxy-headers` in containers
- [API METADATA AND docs UIs](../OpenAPI/metadata-and-docs-ui.md)
