---
type: index
title: FastAPI Wiki Quickstart
description: Entry point to this FastAPI wiki for application developers — what FastAPI is, a minimal app, the public API at a glance, and a task-routing map pointing to the page that answers each question.
tags: [quickstart, overview, routing-map, fastapi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-9bc15a21c009b14775a3dd72
    resource: repo://docs/en/docs/fastapi-cli.md
  - id: openwiki-source-a3f3bff310bc9be49c926bf2
    resource: repo://docs/en/docs/index.md
  - id: openwiki-source-3d064375c9dbfa073c9f1466
    resource: repo://fastapi/__init__.py
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# FastAPI Wiki Quickstart

This wiki documents **FastAPI 0.142.2** (this repository: `fastapi/`, `docs/en/docs/`, `docs_src/`) for developers **using** FastAPI, from beginners to advanced users. Every page uses examples from `docs_src` and exact class, function and parameter names. Internals are covered only as far as they explain user-visible behavior.

## FastAPI in 30 seconds

FastAPI is a Python (3.10+) framework for building APIs from standard type hints. It is a subclass of **Starlette** (web layer) and uses **Pydantic v2** (data validation), run by an ASGI server such as **Uvicorn**.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item
```

```bash
uv add "fastapi[standard]"
fastapi dev main.py        # then open http://127.0.0.1:8000/docs
```

From the type hints FastAPI reads `item_id` from the path, `q` from the query string and `item` from the JSON body; it validates them (422 on errors), serializes the response and documents everything in OpenAPI (`/openapi.json`, `/docs`, `/redoc`).

## Public API at a glance

`from fastapi import ...` (`fastapi/__init__.py`): `FastAPI`, `APIRouter`, `Depends`, `Security`, `Path`, `Query`, `Header`, `Cookie`, `Body`, `Form`, `File`, `UploadFile`, `Request`, `Response`, `WebSocket`, `WebSocketDisconnect`, `BackgroundTasks`, `HTTPException`, `WebSocketException`, `status`.

Submodules: `fastapi.responses` (response classes), `fastapi.security` (auth utilities), `fastapi.encoders` (`jsonable_encoder`), `fastapi.exceptions` (`RequestValidationError`, …), `fastapi.exception_handlers`, `fastapi.middleware.*`, `fastapi.staticfiles`, `fastapi.templating`, `fastapi.testclient`, `fastapi.sse`, `fastapi.openapi.*`, `fastapi.concurrency`, `fastapi.telemetry`.

## Task routing map

### Getting started

| I want to… | Read |
|------------|------|
| Know what FastAPI includes, install extras, compare with other frameworks | [Features, Alternatives and Ecosystem](about/features-and-ecosystem.md) |
| Create and run my first app, use `fastapi dev` / `fastapi run`, configure the entrypoint | [First Steps and the FastAPI CLI](getting-started/first-steps.md) |
| Understand type hints, `Annotated`, and `async def` vs `def` | [Python Types and async/await](getting-started/python-types-and-async.md) |
| Set up uv/venv, env vars, debug in VS Code/PyCharm | [Development Workflow](getting-started/development-workflow.md) |

### Request data

| I want to… | Read |
|------------|------|
| Use path parameters, enums, `:path`, numeric validation (`gt`, `le`…) | [Path Parameters](request/path-parameters.md) |
| Use query parameters, `Query()` validation, lists, `AfterValidator`, query models | [Query Parameters](request/query-parameters.md) |
| Receive JSON bodies, multiple bodies, `Body(embed=True)`, `Field()`, nested models | [Request Body](request/request-body.md) |
| Read headers and cookies, header/cookie models | [Header and Cookie Parameters](request/headers-and-cookies.md) |
| Handle forms and file uploads (`Form`, `File`, `UploadFile`) | [Forms and File Uploads](request/forms-and-files.md) |
| Use `datetime`/`UUID`/`Decimal`, add schema examples, base64 bytes | [Extra Data Types and Examples](request/extra-data-types-and-examples.md) |
| Access the raw `Request`, understand strict `Content-Type`, custom route classes | [Using the Request Object](request/using-request-directly.md) |

### Response data

| I want to… | Read |
|------------|------|
| Declare/filter output with return types or `response_model` | [Response Models](models/response-model.md) |
| Model input/output/DB variants, `jsonable_encoder`, PUT/PATCH updates | [Extra Models and Body Updates](models/extra-models-and-updates.md) |
| Use dataclasses, separate input/output schemas, migrate from Pydantic v1 | [Dataclasses and Pydantic Versions](models/dataclasses-and-pydantic-versions.md) |
| Set status codes (default, extra, dynamic) | [Response Status Codes](responses/status-codes.md) |
| Return HTML, files, redirects, custom response classes | [Custom Responses](responses/custom-responses.md) |
| Set response headers and cookies | [Response Headers and Cookies](responses/response-headers-and-cookies.md) |
| Stream data, JSON Lines, Server-Sent Events | [Streaming and SSE](responses/streaming-and-sse.md) |
| Raise errors, customize exception handlers, 401 vs 403 | [Handling Errors](errors/handling-errors.md) |

### Dependencies and security

| I want to… | Read |
|------------|------|
| Share logic with `Depends`, classes as dependencies, sub-dependencies, caching | [Dependency Injection Basics](dependencies/dependency-injection-basics.md) |
| Open/close resources per request with `yield`, handle exceptions, `scope` | [Dependencies with yield](dependencies/dependencies-with-yield.md) |
| Apply dependencies to a decorator, router or whole app | [Decorator and Global Dependencies](dependencies/decorator-and-global-dependencies.md) |
| Parameterize dependencies, understand `yield` timing history | [Advanced Dependencies](dependencies/advanced-dependencies.md) |
| Add login with OAuth2 password flow and `get_current_user` | [Security Basics](security/oauth2-password-flow.md) |
| Issue JWTs and hash passwords | [OAuth2 with JWT](security/oauth2-jwt.md) |
| Add permissions with scopes | [OAuth2 Scopes](security/oauth2-scopes.md) |
| Use HTTP Basic, Bearer, API keys, OpenID Connect | [HTTP Basic, Bearer, API Keys](security/http-basic-and-api-keys.md) |

### Application structure and cross-cutting concerns

| I want to… | Read |
|------------|------|
| Split the app into modules with `APIRouter` | [Bigger Applications](app-structure/bigger-applications.md) |
| Set tags, summaries, docstrings, `operation_id`, `openapi_extra` | [Path Operation Configuration](app-structure/path-operation-configuration.md) |
| Run code at startup/shutdown (`lifespan`) | [Lifespan Events](app-structure/lifespan-events.md) |
| Load configuration from env vars / `.env` | [Settings](app-structure/settings.md) |
| Mount sub-apps, run behind a proxy (`root_path`), embed Flask/Django | [Sub-applications, Proxies and WSGI](app-structure/sub-applications-proxy-and-wsgi.md) |
| Serve static files, Jinja2 templates or a built SPA (`app.frontend()`) | [Static Files, Templates and Frontends](app-structure/static-files-templates-and-frontend.md) |
| Add middleware (timing, GZip, trusted hosts, HTTPS redirect) | [Middleware](middleware/middleware.md) |
| Allow browser frontends on other origins | [CORS](middleware/cors.md) |

### OpenAPI and docs

| I want to… | Read |
|------------|------|
| Set API title/version/description, tag docs, docs URLs, Swagger UI options, disable docs | [API Metadata and Docs UIs](openapi/metadata-and-docs-ui.md) |
| Document extra responses, customize the schema, callbacks, webhooks | [Extending OpenAPI](openapi/extending-openapi.md) |
| Generate TypeScript/other SDK clients with clean method names | [Generating SDK Clients](openapi/generating-clients.md) |

### Integrations

| I want to… | Read |
|------------|------|
| Use a SQL database (SQLModel, sessions, CRUD) | [SQL Databases](integrations/sql-databases.md) |
| Run work after the response | [Background Tasks](integrations/background-tasks.md) |
| Build WebSocket endpoints | [WebSockets](integrations/websockets.md) |
| Add GraphQL or OpenTelemetry tracing/metrics/logs | [GraphQL and OpenTelemetry](integrations/graphql-and-opentelemetry.md) |

### Testing

| I want to… | Read |
|------------|------|
| Write tests with `TestClient` and pytest | [Testing with TestClient](testing/testing-basics.md) |
| Override dependencies, test lifespan and WebSockets | [Testing Dependencies, Events and WebSockets](testing/testing-dependencies-events-websockets.md) |
| Write `async` tests, test with a database | [Async Tests and Testing Databases](testing/async-tests-and-database-testing.md) |

### Deployment

| I want to… | Read |
|------------|------|
| Understand deployment concepts, workers, version pinning | [Deployment Concepts, Servers and Workers](deployment/deployment-concepts-and-servers.md) |
| Build a Docker image | [Deploying with Docker](deployment/docker.md) |
| Understand HTTPS/TLS proxies, deploy to FastAPI Cloud or other clouds | [HTTPS and Cloud](deployment/https-and-cloud.md) |

### How it works

| I want to… | Read |
|------------|------|
| Understand the request lifecycle (middleware order, validation, serialization, exit stacks) | [How FastAPI Handles a Request](internals/request-handling-internals.md) |

## Suggested learning path

1. [First Steps](getting-started/first-steps.md) → [Path](request/path-parameters.md) / [Query](request/query-parameters.md) parameters → [Request Body](request/request-body.md) → [Response Models](models/response-model.md)
2. [Handling Errors](errors/handling-errors.md) → [Dependency Injection](dependencies/dependency-injection-basics.md) → [Security Basics](security/oauth2-password-flow.md) → [JWT](security/oauth2-jwt.md)
3. [Bigger Applications](app-structure/bigger-applications.md) → [SQL Databases](integrations/sql-databases.md) → [Testing](testing/testing-basics.md) → [Deployment](deployment/deployment-concepts-and-servers.md)
