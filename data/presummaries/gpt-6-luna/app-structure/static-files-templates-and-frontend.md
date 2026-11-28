- **Tools:** Use `StaticFiles` mounted with `app.mount()` for asset folders; `Jinja2Templates` + `TemplateResponse` for per-request server-rendered HTML; `app.frontend()` or `router.frontend()` for a built JS frontend. `fastapi.staticfiles.StaticFiles` and `fastapi.templating.Jinja2Templates` re-export Starlette classes.

- **Static files:**  
  ```python
  app.mount("/static", StaticFiles(directory="static"), name="static")
  ```
  `/static` handles requests starting with that path (for example, `/static/styles.css` → `static/styles.css`); `directory` is the disk folder; `name` enables `url_for("static", path=...)`. A mount adds an independent ASGI app: it is absent from OpenAPI and unaffected by app dependencies.

- **Templates (Jinja2):** Install `jinja2` (included in `fastapi[standard]`). Create and reuse one `Jinja2Templates(directory=...)`; declare a `Request` parameter because `TemplateResponse` needs it for `url_for` and context. Pass `request=`, template `name=`, and a `context=` dict. `response_class=HTMLResponse` makes docs show an HTML response. `url_for()` takes a route name (path operation function name, e.g. `read_item`, or mount name, e.g. `static`) and matching arguments; it generates correct URLs behind a proxy with `root_path`.

- **`app.frontend()` / `router.frontend()`:** Serves built static output (e.g. `npm run build` → `dist/`) with SPA/static-site conventions; it does not do server-side rendering. `GET /assets/app.js` serves `dist/assets/app.js`; directory paths serve `index.html`, redirecting to add a trailing slash when needed. Path operations always win; frontend files are considered only when no normal route matched, including when mounted at `/`.

- **`fallback`:** Accepts `"auto"` (default), `"index.html"`, `"404.html"` or `None`. Missing files: `"404.html"` serves `dist/404.html` with status 404. `"index.html"` serves `dist/index.html` with status 200 only for `GET`/`HEAD` navigation requests whose `Accept` includes `text/html` or `application/xhtml+xml`; missing JS/CSS/images and `POST`/`PUT` still get 404. `"auto"` uses `404.html` if it exists, else the `index.html` behavior if `index.html` exists, else plain 404. `None` gives plain 404. Usually `app.frontend("/", directory="dist")` suffices.

- **`check_dir`:** Accepts `"auto"` (default), `True`, or `False`. `"auto"`: if `FASTAPI_ENV` is `development`, a missing directory only warns; `fastapi dev` sets `FASTAPI_ENV=development` if unset. Otherwise, missing directory raises an error at app creation. `True` always checks at creation. `False` never checks then; requests raise an error if the directory is still missing.

- **Router, dependencies and related:** `router.frontend("/", directory="dist", fallback="index.html")` followed by `app.include_router(router, prefix="/app")` serves the frontend under `/app`; regular path operations anywhere still take precedence. Frontend responses run inside the app: HTTP middleware and dependencies from the app, router, and `include_router()` apply; dependencies can set response headers or add background tasks. Related: CORS for a different origin; `HTMLResponse`, `FileResponse`; Sub-applications, Proxies and WSGI.
