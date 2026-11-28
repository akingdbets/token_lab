## Mounting a sub-application
- A mounted app is independent: it has its own path operations, OpenAPI schema, and docs UI. Unlike `APIRouter`, its operations do not become part of the main app.
- `app.mount("/subapi", subapi)` routes `GET /app` to `app` and `GET /subapi/sub` to `subapi`. `/docs` shows only `app` operations; `/subapi/docs` shows only `subapi` operations, with correct `/subapi` URLs.
- Mounting supplies the mount path through ASGI `root_path`, supporting nested mounts and docs UIs. Lifespan events run only for the main app; main-app dependencies do not apply to mounted apps.
- `app.mount()` accepts any ASGI app, including `StaticFiles`, GraphQL apps, and WSGI wrappers.

## Behind a proxy: forwarded headers
- Proxies such as Traefik, Nginx, or cloud load balancers may terminate HTTPS and forward HTTP with `X-Forwarded-For` (client IP), `X-Forwarded-Proto` (original scheme, e.g. `https`), and `X-Forwarded-Host` (original host).
- These headers are ignored unless the proxy is trusted. With the FastAPI CLI (Uvicorn), use `fastapi run --forwarded-allow-ips="*"`. `"*"` trusts every client IP and is appropriate only when only the proxy can reach the server.
- Trusting headers lets redirects and `url_for()` use the original public HTTPS host instead of `http://localhost:8000`.

## Stripped path prefixes: `root_path`
- If a proxy exposes `/api/v1/...` but strips that prefix before forwarding, set `root_path` so docs and generated URLs include it. Use `fastapi run main.py --forwarded-allow-ips="*" --root-path /api/v1` or `FastAPI(root_path="/api/v1")`.
- `FastAPI.__call__` writes the app’s `root_path` into each request’s `scope["root_path"]`. The server still serves paths without the prefix (e.g. `http://127.0.0.1:8000/app`); adding the prefix is the proxy’s job. Docs endpoints prefix `openapi_url` and the OAuth2 redirect URL with the current `root_path`.
- If the proxy does not strip the prefix, do not use `root_path`; put the prefix in routes, e.g. `include_router(prefix="/api/v1")`.

## OpenAPI `servers`
- With non-empty `root_path`, `/openapi.json` inserts `{"url": root_path}` at the start of `servers`, unless that URL is already present. Additional servers can be configured for environments. With no `servers` and `root_path` `/`, the `servers` key is omitted.
- Set `root_path_in_servers=False` to disable the automatic root-path server. `openapi_prefix` is deprecated in favor of `root_path`. Mounted sub-apps work behind proxies; FastAPI combines paths.

## Including WSGI apps
- Wrap and mount WSGI apps (e.g. Flask or Django) with `WSGIMiddleware` from `a2wsgi` (`uv add a2wsgi`). `fastapi.middleware.wsgi.WSGIMiddleware` (a Starlette re-export) is deprecated.
- Requests under `/v1/` go to the mounted Flask app; other requests go to FastAPI. This supports incremental migration.

## Related
- HTTPS/TLS: `../deployment/https-and-cloud.md`; Docker (`--proxy-headers`): `../deployment/docker.md`; API metadata and docs: `../openapi/metadata-and-docs-ui.md`.
