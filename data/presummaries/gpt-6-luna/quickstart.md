# FastAPI Wiki Quickstart

- Documents **FastAPI 0.142.2** for developers using FastAPI; examples come from `docs_src`, with exact class, function, and parameter names. Internals are covered only to explain user-visible behavior.
- **FastAPI in 30 seconds:** Python (3.10+) API framework using standard type hints; subclass of **Starlette**, uses **Pydantic v2**, and runs on an ASGI server such as **Uvicorn**.
  ```python
  from fastapi import FastAPI
  from pydantic import BaseModel
  app = FastAPI()
  ```
  Install/run: `uv add "fastapi[standard]"`; `fastapi dev main.py` (then open `http://127.0.0.1:8000/docs`). Type hints identify path (`item_id`), query (`q`), and JSON body (`item`) data; FastAPI validates (422 on errors), serializes responses, and documents OpenAPI at `/openapi.json`, `/docs`, `/redoc`.
- **Public API at a glance:** `fastapi/__init__.py` exports `FastAPI`, `APIRouter`, `Depends`, `Security`, `Path`, `Query`, `Header`, `Cookie`, `Body`, `Form`, `File`, `UploadFile`, `Request`, `Response`, `WebSocket`, `WebSocketDisconnect`, `BackgroundTasks`, `HTTPException`, `WebSocketException`, `status`. Submodules: `fastapi.responses`, `fastapi.security`, `fastapi.encoders` (`jsonable_encoder`), `fastapi.exceptions` (`RequestValidationError`, …), `fastapi.exception_handlers`, `fastapi.middleware.*`, `fastapi.staticfiles`, `fastapi.templating`, `fastapi.testclient`, `fastapi.sse`, `fastapi.openapi.*`, `fastapi.concurrency`, `fastapi.telemetry`.

## Task routing map

- **Getting started:** features/install extras/framework comparisons → `about/features-and-ecosystem.md`; first app, `fastapi dev`/`fastapi run`, entrypoint → `getting-started/first-steps.md`; type hints, `Annotated`, `async def` vs `def` → `getting-started/python-types-and-async.md`; uv/venv, env vars, VS Code/PyCharm debugging → `getting-started/development-workflow.md`.
- **Request data:** path parameters, enums, `:path`, numeric validation (`gt`, `le`…) → `request/path-parameters.md`; query, `Query()`, lists, `AfterValidator`, query models → `request/query-parameters.md`; JSON/multiple bodies, `Body(embed=True)`, `Field()`, nested models → `request/request-body.md`; headers/cookies and models → `request/headers-and-cookies.md`; forms/uploads → `request/forms-and-files.md`; `datetime`/`UUID`/`Decimal`, schema examples, base64 bytes → `request/extra-data-types-and-examples.md`; raw `Request`, strict `Content-Type`, custom route classes → `request/using-request-directly.md`.
- **Response data:** output types/`response_model` → `models/response-model.md`; input/output/DB variants, `jsonable_encoder`, PUT/PATCH → `models/extra-models-and-updates.md`; dataclasses, schemas, Pydantic v1 migration → `models/dataclasses-and-pydantic-versions.md`; status codes → `responses/status-codes.md`; HTML/files/redirects/custom responses → `responses/custom-responses.md`; headers/cookies → `responses/response-headers-and-cookies.md`; streaming, JSON Lines, SSE → `responses/streaming-and-sse.md`; errors, handlers, 401 vs 403 → `errors/handling-errors.md`.
- **Dependencies and security:** `Depends`, classes, sub-dependencies, caching → `dependencies/dependency-injection-basics.md`; `yield`, resources, exceptions, `scope` → `dependencies/dependencies-with-yield.md`; decorator/router/app dependencies → `dependencies/decorator-and-global-dependencies.md`; parameterized dependencies and `yield` timing history → `dependencies/advanced-dependencies.md`; OAuth2 password flow, `get_current_user` → `security/oauth2-password-flow.md`; JWT/password hashing → `security/oauth2-jwt.md`; scopes → `security/oauth2-scopes.md`; HTTP Basic, Bearer, API keys, OpenID Connect → `security/http-basic-and-api-keys.md`.
- **Application structure and cross-cutting concerns:** `APIRouter` modules → `app-structure/bigger-applications.md`; operation metadata → `app-structure/path-operation-configuration.md`; `lifespan` → `app-structure/lifespan-events.md`; env/`.env` settings → `app-structure/settings.md`; sub-apps, `root_path`, Flask/Django → `app-structure/sub-applications-proxy-and-wsgi.md`; static files, Jinja2, SPA, `app.frontend()` → `app-structure/static-files-templates-and-frontend.md`; middleware → `middleware/middleware.md`; cross-origin browser access → `middleware/cors.md`.
- **OpenAPI and docs:** API metadata/docs UIs → `openapi/metadata-and-docs-ui.md`; responses, schema, callbacks, webhooks → `openapi/extending-openapi.md`; SDK clients → `openapi/generating-clients.md`.
- **Integrations:** SQLModel/sessions/CRUD → `integrations/sql-databases.md`; post-response work → `integrations/background-tasks.md`; WebSockets → `integrations/websockets.md`; GraphQL/OpenTelemetry → `integrations/graphql-and-opentelemetry.md`.
- **Testing:** `TestClient`/pytest → `testing/testing-basics.md`; overrides, lifespan, WebSockets → `testing/testing-dependencies-events-websockets.md`; async/database tests → `testing/async-tests-and-database-testing.md`.
- **Deployment:** concepts, workers, version pinning → `deployment/deployment-concepts-and-servers.md`; Docker → `deployment/docker.md`; HTTPS/TLS proxies and cloud deployment → `deployment/https-and-cloud.md`.
- **How it works:** request lifecycle, middleware order, validation, serialization, exit stacks → `internals/request-handling-internals.md`.

## Suggested learning path

1. `getting-started/first-steps.md` → path/query parameters → `request/request-body.md` → `models/response-model.md`.
2. `errors/handling-errors.md` → `dependencies/dependency-injection-basics.md` → `security/oauth2-password-flow.md` → `security/oauth2-jwt.md`.
3. `app-structure/bigger-applications.md` → `integrations/sql-databases.md` → `testing/testing-basics.md` → `deployment/deployment-concepts-and-servers.md`.
