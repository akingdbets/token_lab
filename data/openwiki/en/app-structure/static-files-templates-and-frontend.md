---
type: guide
title: Static Files, Templates and Frontends
description: Serve static assets with StaticFiles, render server-side HTML with Jinja2Templates and url_for, and serve a built single-page or static-site frontend with app.frontend() including fallback and check_dir behavior.
tags: [static-files, staticfiles, templates, jinja2, frontend, spa, mount]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-61cabf4804d33ca7cac37dd8
    resource: repo://docs_src/frontend/tutorial004_py310.py
  - id: openwiki-source-1a1b474cd7a5d78df4df498e
    resource: repo://docs_src/static_files/tutorial001_py310.py
  - id: openwiki-source-ed1031cd9afb79ebd46b739a
    resource: repo://docs_src/templates/templates/item.html
  - id: openwiki-source-7fd958075fa7d6f7fa668120
    resource: repo://docs_src/templates/tutorial001_py310.py
  - id: openwiki-source-3edfa959d42b9f564280c905
    resource: repo://docs/en/docs/tutorial/frontend.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-a2658bf7fa1d2b96ae2bef15
    resource: repo://fastapi/staticfiles.py
  - id: openwiki-source-8d07ead49806eddd070fe43f
    resource: repo://fastapi/templating.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Static Files, Templates and Frontends

FastAPI is API-first, but it can also serve files and HTML. There are three tools:

| Need | Tool |
|------|------|
| Serve a folder of assets (CSS, images, downloads) under a path | `StaticFiles` mounted with `app.mount()` |
| Render HTML on the server per request | `Jinja2Templates` + `TemplateResponse` |
| Serve a built JS frontend (React/Vite, Vue, Svelte, Angular, Astro, …) next to the API | `app.frontend()` / `router.frontend()` |

`fastapi.staticfiles.StaticFiles` and `fastapi.templating.Jinja2Templates` are direct re-exports of Starlette's classes, provided for convenience.

## Static files

`docs_src/static_files/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
```

- `"/static"` is the sub-path: every request starting with `/static` is handled by the `StaticFiles` app (`/static/styles.css` → `static/styles.css`).
- `directory="static"` is the folder on disk.
- `name="static"` lets you build URLs with `url_for("static", path=...)`.

Mounting adds an **independent** ASGI app: it does not appear in your OpenAPI schema and is not affected by your app's dependencies. See [Sub-applications](sub-applications-proxy-and-wsgi.md) for mounting in general.

## Templates (Jinja2)

Install `jinja2` (included in `fastapi[standard]`). `docs_src/templates/tutorial001_py310.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/items/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse(
        request=request, name="item.html", context={"id": id}
    )
```

- Create one `Jinja2Templates(directory=...)` object and reuse it.
- Declare a `Request` parameter — `TemplateResponse` needs it (for `url_for` and context).
- Pass `request=`, the template `name=` and a `context=` dict.
- `response_class=HTMLResponse` makes the docs show an HTML response.

The template `templates/item.html`:

```html
<html>
<head>
    <title>Item Details</title>
    <link href="{{ url_for('static', path='/styles.css') }}" rel="stylesheet">
</head>
<body>
    <h1><a href="{{ url_for('read_item', id=id) }}">Item ID: {{ id }}</a></h1>
</body>
</html>
```

`url_for()` takes a route name (the path operation function name, e.g. `read_item`, or the mount name, e.g. `static`) and the same arguments as that path; it produces correct URLs even behind a proxy with a `root_path`.

## Serving a built frontend: `app.frontend()`

`app.frontend()` (also `router.frontend()`) serves the static output of a frontend build (e.g. `npm run build` → `dist/`) following SPA and static-site conventions.

```python
from fastapi import FastAPI

app = FastAPI()

app.frontend("/", directory="dist")
```

With this, `GET /assets/app.js` serves `dist/assets/app.js`, and directory paths serve their `index.html` (redirecting to add a trailing slash when needed).

**Path operations always win.** Frontend files are only considered when no normal route matched, so your API is never shadowed — even when the frontend is mounted at `/`.

### Fallback for missing paths

The `fallback` parameter accepts `"auto"` (default), `"index.html"`, `"404.html"` or `None`:

```python
app.frontend("/", directory="dist", fallback="index.html")  # SPA client-side routing
app.frontend("/", directory="dist", fallback="404.html")    # static sites, e.g. Astro
app.frontend("/", directory="dist", fallback=None)          # plain 404
```

When a requested file does not exist:

1. `"404.html"` — serve `dist/404.html` with status **404**.
2. `"index.html"` — serve `dist/index.html` with status **200**, but only for navigation requests: `GET`/`HEAD` requests whose `Accept` header includes `text/html` or `application/xhtml+xml` (as browsers send). Missing JS/CSS/images and `POST`/`PUT` requests still get `404`.
3. `"auto"` — use `404.html` if that file exists; otherwise use the `index.html` behavior if `index.html` exists; otherwise a plain 404.
4. `None` — plain 404.

So in most projects `app.frontend("/", directory="dist")` is enough.

### Checking the directory: `check_dir`

`check_dir` accepts `"auto"` (default), `True` or `False`:

- `"auto"`: if the environment variable `FASTAPI_ENV` is `development`, a missing directory only emits a warning (so you can start the backend before building the frontend). `fastapi dev` sets `FASTAPI_ENV=development` if not already set. In any other environment, a missing directory raises an error when the app is created — catching deploys without frontend files early.
- `True`: always check at app creation.
- `False`: never check at creation (useful if files are produced later); a request will raise an error if the directory is still missing.

```python
app.frontend("/", directory="dist", check_dir=False)
```

### With `APIRouter`

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

router.frontend("/", directory="dist", fallback="index.html")
app.include_router(router, prefix="/app")
```

The frontend is served under `/app`; regular path operations anywhere in the app still take precedence.

### Dependencies and middleware apply

Frontend responses run inside the normal application: HTTP middleware applies, and dependencies from the app, the router and `include_router()` run too — useful, for example, to protect a frontend with cookie authentication. Dependencies can also set response headers or add background tasks.

`app.frontend()` serves pre-built files only; it does not do server-side rendering.

## Related

- [CORS](../middleware/cors.md) — needed when the frontend is served from a *different* origin
- [Custom Responses](../responses/custom-responses.md) — `HTMLResponse`, `FileResponse`
- [Sub-applications, Proxies and WSGI](sub-applications-proxy-and-wsgi.md)
