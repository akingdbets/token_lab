---
type: overview
title: Features, Alternatives and Ecosystem
description: What FastAPI gives you on top of Starlette and Pydantic, how it compares to other Python frameworks, how to read benchmarks, the install extras, the editor extension and the Full Stack FastAPI Template.
tags: [overview, features, ecosystem, starlette, pydantic, benchmarks, installation]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-65385d28aa615ccf9c247795
    resource: repo://docs/en/docs/benchmarks.md
  - id: openwiki-source-59423393aef62df38afc5cc7
    resource: repo://docs/en/docs/deployment/versions.md
  - id: openwiki-source-84c2fb1bfb265caa7a5aec95
    resource: repo://docs/en/docs/editor-support.md
  - id: openwiki-source-150d8aa89aa20ce136f4a262
    resource: repo://docs/en/docs/features.md
  - id: openwiki-source-3d064375c9dbfa073c9f1466
    resource: repo://fastapi/__init__.py
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Features, Alternatives and Ecosystem

FastAPI is a Python web framework for building APIs from standard Python type hints. This page explains what it is built on, what it adds, and which tools around it you will meet as a user. The rest of the wiki covers how to use each feature; start from the [Quickstart](../quickstart.md).

## What FastAPI is built on

FastAPI sits on top of two libraries and is usually run by a third:

| Layer | Role | What you get from it |
|-------|------|----------------------|
| **Uvicorn** (or another ASGI server) | Runs the app | The HTTP server process |
| **Starlette** | ASGI web toolkit | Routing, requests/responses, WebSockets, middleware, background tasks, test client, static files, sessions |
| **Pydantic** (v2) | Data validation | Parsing, validation, serialization and JSON Schema for your models |
| **FastAPI** | API framework | Type-hint driven parameters, dependency injection, security utilities, automatic OpenAPI and docs |

`FastAPI` is literally a subclass of Starlette's application class (`class FastAPI(Starlette)` in `fastapi/applications.py`), so Starlette code — middleware, `Request`, response classes, routes — works inside a FastAPI app unchanged.

The package itself requires Python 3.10+ and depends on `starlette`, `pydantic>=2.9.0`, `typing-extensions`, `typing-inspection`, `annotated-doc` and `opentelemetry-api` (see `pyproject.toml`). Pydantic v1 models are no longer the primary path; see [Dataclasses and Pydantic versions](../models/dataclasses-and-pydantic-versions.md).

## Main features

- **Open standards**: every app produces an OpenAPI schema (including JSON Schema for models), served at `/openapi.json` by default. See [API Metadata and Docs UIs](../openapi/metadata-and-docs-ui.md).
- **Automatic interactive docs**: Swagger UI at `/docs` and ReDoc at `/redoc`.
- **Just modern Python**: parameters, bodies and responses are declared with type hints (`int`, `str`, `list[Item]`, `Annotated[...]`, Pydantic models). See [Python Types and async/await](../getting-started/python-types-and-async.md).
- **Editor support**: because everything is typed, completion and type checks work for request data inside your functions.
- **Validation**: Pydantic validates JSON objects, arrays, strings with lengths, numbers with bounds, and exotic types like URLs, emails and UUIDs. Errors are returned to clients automatically as `422` responses.
- **Security and authentication**: OAuth2 (including JWT), HTTP Basic/Bearer, API keys in headers, query or cookies, and OpenID Connect — all as reusable dependencies. See [Security Basics](../security/oauth2-password-flow.md).
- **Dependency Injection**: dependencies can have dependencies, forming a graph that FastAPI resolves per request, and their parameters are validated and documented too. See [Dependency Injection Basics](../dependencies/dependency-injection-basics.md).
- **Starlette features**: WebSockets, in-process background tasks, lifespan events, an HTTPX-based `TestClient`, CORS, GZip, static files, streaming responses, sessions and cookies.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


@app.post("/items/")
async def create_item(item: Item):
    # item is validated and fully typed here
    return item
```

## Installation extras

The base package is `fastapi`. Most users install the `standard` extra:

```bash
uv add "fastapi[standard]"   # or: pip install "fastapi[standard]"
```

The `standard` extra (defined in `pyproject.toml`) pulls in:

| Dependency | Needed for |
|------------|-----------|
| `fastapi-cli[standard]` | The `fastapi dev` / `fastapi run` commands (and FastAPI Cloud CLI) |
| `uvicorn[standard]` | Running the server (with uvloop) |
| `httpx` | `TestClient` |
| `jinja2` | `Jinja2Templates` |
| `python-multipart` | `Form()` and `File()` / `UploadFile` |
| `email-validator` | Pydantic `EmailStr` |
| `pydantic-settings` | `BaseSettings` (see [Settings](../app-structure/settings.md)) |
| `pydantic-extra-types` | Extra Pydantic types |
| `opentelemetry-sdk`, OTLP exporter | Telemetry export (see [GraphQL and OpenTelemetry](../integrations/graphql-and-opentelemetry.md)) |

There is also `standard-no-fastapi-cloud-cli` (same, without the cloud CLI) and `all`. If you install plain `fastapi`, you must add whichever of these you use yourself — for example, forms fail without `python-multipart`.

## Versioning

FastAPI is still `0.x` (this repository is version `0.142.2`, declared in `fastapi/__init__.py`). Under semantic versioning conventions, any minor bump may contain breaking changes, so pin the version you tested, e.g. `fastapi[standard]>=0.112.0,<0.113.0`, and upgrade deliberately with tests. Details in [Deployment Concepts](../deployment/deployment-concepts-and-servers.md).

## Alternatives and how FastAPI compares

FastAPI took ideas from many earlier tools (documented in `docs/en/docs/alternatives.md` and `history-design-future.md`):

- **Django / Django REST Framework** — automatic API docs and a batteries-included approach; FastAPI keeps automatic docs but avoids coupling to an ORM.
- **Flask** — a simple micro-framework with decoupled pieces; FastAPI keeps the minimal core and "plug in what you need" style.
- **Requests** — the simple, intuitive `get`/`post` API style inspired the path operation decorators (`@app.get`, `@app.post`).
- **Swagger / OpenAPI** — adopted as the standard schema instead of a custom one.
- **Marshmallow, Webargs, APISpec, Flask-apispec** — validation, request parsing and schema generation, which FastAPI replaces with Pydantic and type hints.
- **NestJS / Angular** — dependency injection; FastAPI's is type-hint based and less verbose.
- **Sanic, Falcon, Molten, Hug, APIStar** — performance, async, type-hint parameter declaration and schema generation ideas.

## Reading benchmarks

The dependency chain is Uvicorn → Starlette → FastAPI, so FastAPI cannot be faster than Starlette, which cannot be faster than Uvicorn. Compare like with like:

- Uvicorn vs other ASGI/WSGI servers (Hypercorn, Daphne, uWSGI).
- Starlette vs micro-frameworks (Sanic, Flask, Django).
- FastAPI vs frameworks that also do validation, serialization and docs (Flask-apispec, NestJS, Molten).

The validation and serialization FastAPI does is work you would otherwise write yourself, so the real-world overhead is usually similar or lower. The OpenAPI schema is generated by `app.openapi()` on first use and cached in `app.openapi_schema` (it is regenerated only if the set of routes changes), so docs add no per-request cost to your API endpoints.

## Ecosystem tools

- **FastAPI CLI** (`fastapi dev`, `fastapi run`) — see [First Steps and the FastAPI CLI](../getting-started/first-steps.md).
- **FastAPI editor extension** for VS Code and Cursor — path operation explorer, route search, CodeLens links from `client.get(...)` test calls to their path operations, FastAPI Cloud deployment and log streaming. It discovers apps by scanning for `FastAPI()`; set an entrypoint via `[tool.fastapi]` in `pyproject.toml` or the `fastapi.entryPoint` setting (module notation such as `myapp.main:app`) if detection fails.
- **Full Stack FastAPI Template** — a starter project with FastAPI + SQLModel + PostgreSQL, a React/TypeScript frontend with a generated client, Docker Compose, JWT auth, password hashing, Pytest tests, Traefik and GitHub Actions CI/CD.
- **FastAPI Cloud** — the hosting service by the FastAPI team; see [HTTPS and Cloud](../deployment/https-and-cloud.md).
- **SQLModel** — the recommended SQL library in the tutorial; see [SQL Databases](../integrations/sql-databases.md).
