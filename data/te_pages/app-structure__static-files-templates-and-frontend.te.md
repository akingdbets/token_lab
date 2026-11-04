---
type: guide
title: static Files, templates and Frontends
description: Serve static assets with StaticFiles, render server-side HTML with Jinja2Templates and url_for, and serve a built single-page or static-site frontend with app.frontend() including fallback and check_dir behavior.
tags: [static-files, StaticFiles, templates, jinja2, frontend, SPA, mount]
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

H1: static Files, templates and Frontends

FASTAPI IS API-FIRST; ALSO SERVES FILES AND HTML. THREE TOOLS:

| NEED | TOOL |
|------|------|
| SERVE ASSET FOLDER (CSS, IMAGES, DOWNLOADS) UNDER path | `StaticFiles` MOUNTED WITH `app.mount()` |
| RENDER HTML SERVER-SIDE PER REQUEST | `Jinja2Templates` + `TemplateResponse` |
| SERVE BUILT JS FRONTEND (REACT/VITE, VUE, SVELTE, ANGULAR, ASTRO, …) NEXT TO API | `app.frontend()` / `router.frontend()` |

`fastapi.staticfiles.StaticFiles` AND `fastapi.templating.Jinja2Templates` ARE
DIRECT RE-EXPORTS OF STARLETTE CLASSES, PROVIDED FOR CONVENIENCE.

H2: static files

`docs_src/static_files/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
```

- `"/static"` IS SUB-path: REQUESTS STARTING WITH `/static` ARE HANDLED BY
  `StaticFiles` app (`/static/styles.css` → `static/styles.css`).
- `directory="static"` IS DISK FOLDER.
- `name="static"` ENABLES URL BUILDING WITH `url_for("static", path=...)`.

MOUNTING ADDS INDEPENDENT ASGI app: IT DOES NOT APPEAR IN OpenAPI SCHEMA
OR INHERIT YOUR app'S DEPENDENCIES. SEE
[SUB-APPLICATIONS](sub-applications-proxy-and-wsgi.md) FOR GENERAL MOUNTING.

H2: templates (Jinja2)

INSTALL `jinja2` (INCLUDED IN `fastapi[standard]`).
`docs_src/templates/tutorial001_py310.py`:

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

- CREATE ONE `Jinja2Templates(directory=...)` OBJECT; REUSE IT.
- DECLARE A `Request` PARAMETER; `TemplateResponse` NEEDS IT FOR `url_for`
  AND context.
- PASS `request=`, TEMPLATE `name=`, AND `context=` DICT.
- `response_class=HTMLResponse` MAKES DOCS SHOW AN HTML RESPONSE.

TEMPLATE `templates/item.html`:

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

`url_for()` TAKES ROUTE name (path OPERATION FUNCTION name, e.g. `read_item`,
OR MOUNT name, e.g. `static`) AND SAME ARGUMENTS AS THAT path. IT PRODUCES
CORRECT URLs EVEN BEHIND PROXY WITH `root_path`.

H2: Serving a built frontend: `app.frontend()`

`app.frontend()` (ALSO `router.frontend()`) SERVES static OUTPUT OF FRONTEND
build (e.g. `npm run build` → `dist/`) FOLLOWING SPA AND static-SITE
CONVENTIONS.

```python
from fastapi import FastAPI

app = FastAPI()

app.frontend("/", directory="dist")
```

WITH THIS, `GET /assets/app.js` SERVES `dist/assets/app.js`; directory PATHS
SERVE THEIR `index.html`, REDIRECTING TO ADD TRAILING SLASH WHEN NEEDED.

path OPERATIONS ALWAYS WIN. FRONTEND FILES ARE CONSIDERED ONLY WHEN NO
NORMAL ROUTE MATCHES; API IS NEVER SHADOWED, EVEN WHEN FRONTEND MOUNTED AT `/`.

H3: fallback for missing paths

`fallback` PARAMETER ACCEPTS `"auto"` (DEFAULT), `"index.html"`, `"404.html"`
OR `None`:

```python
app.frontend("/", directory="dist", fallback="index.html")  # SPA client-side routing
app.frontend("/", directory="dist", fallback="404.html")    # static sites, e.g. Astro
app.frontend("/", directory="dist", fallback=None)          # plain 404
```

WHEN REQUESTED FILE DOES NOT EXIST:
1. `"404.html"` → SERVE `dist/404.html` WITH STATUS 404.
2. `"index.html"` → SERVE `dist/index.html` WITH STATUS 200, ONLY FOR
   NAVIGATION REQUESTS: `GET`/`HEAD` REQUESTS WITH `Accept` INCLUDING
   `text/html` OR `application/xhtml+xml` (AS BROWSERS SEND).
   MISSING JS/CSS/IMAGES AND `POST`/`PUT` REQUESTS STILL GET 404.
3. `"auto"` → USE `404.html` IF IT EXISTS; ELSE USE `index.html` BEHAVIOR
   IF `index.html` EXISTS; ELSE PLAIN 404.
4. `None` → PLAIN 404.

MOST PROJECTS: `app.frontend("/", directory="dist")` IS ENOUGH.

H3: CHECKING THE directory: `check_dir`

`check_dir` ACCEPTS `"auto"` (DEFAULT), `True` OR `False`:

- `"auto"`: IF `FASTAPI_ENV` IS `development`, MISSING directory ONLY EMITS
  A WARNING, ALLOWING BACKEND STARTUP BEFORE FRONTEND build.
  `fastapi dev` SETS `FASTAPI_ENV=development` IF NOT ALREADY SET.
  IN ANY OTHER ENVIRONMENT, MISSING directory RAISES AN ERROR WHEN THE app
  IS CREATED, CATCHING DEPLOYS WITHOUT FRONTEND FILES EARLY.
- `True`: ALWAYS CHECK AT app CREATION.
- `False`: NEVER CHECK AT CREATION (USEFUL IF FILES ARE PRODUCED LATER);
  REQUEST RAISES AN ERROR IF THE directory IS STILL MISSING.

```python
app.frontend("/", directory="dist", check_dir=False)
```

H3: WITH `APIRouter`

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

router.frontend("/", directory="dist", fallback="index.html")
app.include_router(router, prefix="/app")
```

FRONTEND SERVED UNDER `/app`; REGULAR path OPERATIONS ANYWHERE IN THE app
STILL TAKE PRECEDENCE.

H2: DEPENDENCIES AND MIDDLEWARE APPLY

FRONTEND RESPONSES run INSIDE THE NORMAL application: HTTP MIDDLEWARE
APPLIES, AND DEPENDENCIES FROM THE app, ROUTER AND `include_router()` run
TOO. USEFUL, e.g., TO PROTECT A FRONTEND WITH COOKIE AUTHENTICATION.
DEPENDENCIES CAN ALSO SET RESPONSE HEADERS OR ADD BACKGROUND TASKS.

`app.frontend()` SERVES PRE-BUILT FILES ONLY; IT DOES NOT DO SERVER-SIDE
RENDERING.

H2: RELATED

- [CORS](../middleware/cors.md) — NEEDED WHEN THE FRONTEND IS SERVED FROM A
  DIFFERENT ORIGIN
- [Custom Responses](../responses/custom-responses.md) — `HTMLResponse`,
  `FileResponse`
- [Sub-applications, Proxies and WSGI](sub-applications-proxy-and-wsgi.md)
