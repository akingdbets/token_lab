---
type: guide
title: Sub-applications, Running Behind a Proxy and WSGI
description: Mount independent FastAPI sub-applications, run behind proxies with forwarded headers and stripped path prefixes using root_path, control OpenAPI servers, and mount Flask/Django apps with WSGIMiddleware from a2wsgi.
tags: [mount, sub-application, proxy, root_path, forwarded-headers, servers, wsgi, flask]
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
    resource: repo://fastapi/applications.py
  - id: openwiki-source-8d245b8dfa52fb051edbd6f7
    resource: repo://fastapi/middleware/wsgi.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Sub-applications, Running Behind a Proxy and WSGI

This page covers three related deployment-shape topics: mounting another ASGI app under a path, telling FastAPI about a reverse proxy in front of it, and embedding legacy WSGI apps.

## Mounting a sub-application

A mounted app is **independent**: it has its own path operations, its own OpenAPI schema and its own docs UI. (Contrast with `APIRouter`, whose operations become part of the main app — see [Bigger Applications](bigger-applications.md).)

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

- `GET /app` is handled by `app`; `GET /subapi/sub` by `subapi`.
- `/docs` shows only `app`'s operations; `/subapi/docs` shows only `subapi`'s, with correct `/subapi` URLs.
- Mounting communicates the mount path via the ASGI `root_path`, so nested mounts and the docs UIs keep working.
- Lifespan events run only for the main app, not mounted ones ([Lifespan Events](lifespan-events.md)). Main-app dependencies do not apply to the mounted app.

`app.mount()` works with any ASGI app — `StaticFiles` ([Static Files](static-files-templates-and-frontend.md)), GraphQL apps, WSGI wrappers.

## Behind a proxy: forwarded headers

A proxy (Traefik, Nginx, a cloud load balancer) typically terminates HTTPS and forwards plain HTTP to your server, adding:

- `X-Forwarded-For` — original client IP
- `X-Forwarded-Proto` — original scheme (`https`)
- `X-Forwarded-Host` — original host

For security the server ignores these unless told the proxy is trusted. With the FastAPI CLI (Uvicorn):

```bash
fastapi run --forwarded-allow-ips="*"
```

`"*"` trusts every client IP — only appropriate when nothing but the proxy can reach the server. The visible effect: automatic redirects (e.g. `/items` → `/items/` for `@app.get("/items/")`) and `url_for()` build `https://mysuperapp.com/items/` instead of `http://localhost:8000/items/`.

## Behind a proxy with a stripped path prefix: `root_path`

Sometimes the proxy exposes your app at `https://example.com/api/v1/...` but forwards to your server **without** the prefix (`/app` instead of `/api/v1/app`). Your code needs to know the prefix so the docs UI fetches `/api/v1/openapi.json` and generated URLs are right. ASGI calls this prefix `root_path`.

Provide it on the command line:

```bash
fastapi run main.py --forwarded-allow-ips="*" --root-path /api/v1
```

or in code, if you cannot pass CLI options (`docs_src/behind_a_proxy/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Request

app = FastAPI(root_path="/api/v1")


@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}
```

When `root_path` is set on the app, `FastAPI.__call__` writes it into every request's `scope["root_path"]`. Either way the server still serves the path **without** the prefix (`http://127.0.0.1:8000/app`); adding `/api/v1` is the proxy's job. The docs endpoints prefix `openapi_url` (and the OAuth2 redirect URL) with the current `root_path`.

If your proxy does **not** strip the prefix (it forwards `/api/v1/app` as-is), you don't need `root_path`; put the prefix in your routes instead (e.g. via `include_router(prefix="/api/v1")`).

## OpenAPI `servers`

When a request arrives with a non-empty `root_path`, the `/openapi.json` endpoint inserts `{"url": root_path}` at the start of the `servers` list (unless an identical URL is already there). You can add more servers so the docs UI can target several environments (`docs_src/behind_a_proxy/tutorial003_py310.py`):

```python
app = FastAPI(
    servers=[
        {"url": "https://stag.example.com", "description": "Staging environment"},
        {"url": "https://prod.example.com", "description": "Production environment"},
    ],
    root_path="/api/v1",
)
```

produces `servers: [{"url": "/api/v1"}, {"url": "https://stag..."}, {"url": "https://prod..."}]`. If no `servers` are given and `root_path` is `/`, the `servers` key is omitted entirely.

To stop the automatic `root_path` server, pass `root_path_in_servers=False` (`tutorial004_py310.py`).

The parameter `openapi_prefix` is deprecated in favor of `root_path`.

Mounting sub-apps behind a proxy with `root_path` works as expected; FastAPI combines the paths.

## Including WSGI apps (Flask, Django, …)

Wrap a WSGI app with `WSGIMiddleware` and mount it. Use the `a2wsgi` package (`uv add a2wsgi`); `fastapi.middleware.wsgi.WSGIMiddleware` (a re-export of Starlette's) is deprecated.

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

Requests under `/v1/` go to Flask; everything else goes to FastAPI. This is a common way to migrate an app incrementally.

## Related

- [HTTPS, TLS Termination and Cloud Providers](../deployment/https-and-cloud.md)
- [Deploying with Docker](../deployment/docker.md) — `--proxy-headers` in containers
- [API Metadata and Docs UIs](../openapi/metadata-and-docs-ui.md)
