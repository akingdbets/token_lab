## API metadata

- `FastAPI(...)` parameters fill the OpenAPI `info` section shown at the top of the docs.
- `title: str` defaults to `"FastAPI"`; `summary: str` is a short summary (OpenAPI 3.1); `description: str` supports Markdown.
- `version: str` is **your API's** version, default `"0.1.0"`—not FastAPI's or OpenAPI's. `terms_of_service: str` is a URL.
- `contact: dict` supports `name`, `url`, `email`. `license_info: dict` requires `name` plus **either** `url` **or** an SPDX `identifier` (e.g. `"Apache-2.0"`).
- Related parameters: `openapi_version` (default `"3.1.0"`), `servers`, `root_path`, `openapi_external_docs`, `separate_input_output_schemas`. `servers` and `root_path` relate to Sub-applications, Proxies.

## Tag metadata (`openapi_tags`)

- Entries describe path-operation tags, and list order determines docs order. Each entry has required `name` (same string as in `tags=[...]`), optional Markdown `description`, and `externalDocs` with `description` and `url`. You need not describe every tag you use.

## URLs of the schema and docs

- `openapi_url` defaults to `"/openapi.json"`; setting it to `None` disables the schema and both docs UIs.
- `docs_url` defaults to `"/docs"`; `None` disables Swagger UI. `redoc_url` defaults to `"/redoc"`; `None` disables ReDoc. `swagger_ui_oauth2_redirect_url` defaults to `"/docs/oauth2-redirect"`; `None` disables the OAuth2 redirect page.
- Docs routes are added only when `openapi_url` is set (e.g. `if self.openapi_url and self.docs_url`) and use `include_in_schema=False`. Behind a proxy, docs prepend the request's `root_path` to `openapi_url`.

## Configuring Swagger UI

- `swagger_ui_parameters` merges options over `swagger_ui_default_parameters` in `fastapi.openapi.docs`: `dom_id="#swagger-ui"`, `layout="BaseLayout"`, `deepLinking=True`, `showExtensions=True`, `showCommonExtensions=True`.
- Examples: `{"syntaxHighlight": False}`, `{"syntaxHighlight": {"theme": "obsidian"}}`, `{"deepLinking": False}`. Any JSON-serializable config works; JavaScript-only settings (functions) cannot be passed this way. Use a custom docs page for those. `swagger_ui_init_oauth` passes OAuth2 init settings such as `clientId`.

## Custom docs pages and self-hosted assets

- By default, docs load JS/CSS from CDN `cdn.jsdelivr.net` (`swagger-ui-dist@5`, `redoc@2`). For another CDN or self-hosting (e.g. offline/intranet), disable automatic pages and use `fastapi.openapi.docs` helpers: `get_swagger_ui_html`, `get_swagger_ui_oauth2_redirect_html`, `get_redoc_html`.
- Mount assets with `StaticFiles`; download `swagger-ui-bundle.js`, `swagger-ui.css`, and `redoc.standalone.js` into `static/` (an example uses unpkg).
- Keep the OAuth2 redirect route if using Swagger UI's "Authorize" dialog with OAuth2. Other helper parameters include `swagger_favicon_url`, `swagger_ui_parameters`, `init_oauth`; `get_redoc_html` accepts `redoc_favicon_url` and `with_google_fonts`.

## Conditional OpenAPI

- Hiding docs is **not** a security measure: endpoints remain reachable (security through obscurity). Secure the API with real authentication.
- Drive `openapi_url` from settings, e.g. `Settings(BaseSettings)` with `openapi_url: str = "/openapi.json"`, then `FastAPI(openapi_url=settings.openapi_url)`.
- `OPENAPI_URL= uvicorn main:app` sets an empty URL, disabling schema and docs; requests to `/openapi.json`, `/docs`, `/redoc` return 404.
