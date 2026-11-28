## What FastAPI is built on
- Uvicorn (or another ASGI server) runs the app. Starlette provides routing, requests/responses, WebSockets, middleware, background tasks, test client, static files and sessions. Pydantic (v2) provides model parsing, validation, serialization and JSON Schema. FastAPI adds type-hint driven parameters, dependency injection, security utilities, OpenAPI and docs.
- `class FastAPI(Starlette)` in `fastapi/applications.py`: Starlette middleware, `Request`, response classes and routes work unchanged inside FastAPI.
- Requires Python 3.10+; depends on `starlette`, `pydantic>=2.9.0`, `typing-extensions`, `typing-inspection`, `annotated-doc` and `opentelemetry-api`. Pydantic v1 models are no longer the primary path.

## Main features
- OpenAPI (including JSON Schema) at `/openapi.json` by default; Swagger UI at `/docs`, ReDoc at `/redoc`.
- Type hints declare parameters, bodies and responses; typing enables editor completion and checks for request data.
- Pydantic validates JSON objects, arrays, bounded numbers, length-limited strings, URLs, emails and UUIDs; errors automatically return `422`.
- Reusable dependencies provide OAuth2 (including JWT), HTTP Basic/Bearer, API keys in headers, query or cookies, and OpenID Connect. Dependencies can form graphs, resolved per request; their parameters are validated and documented.
- Starlette features include WebSockets, in-process background tasks, lifespan events, HTTPX-based `TestClient`, CORS, GZip, static files, streaming responses, sessions and cookies.

## Installation extras
- Base package: `fastapi`; most users install `fastapi[standard]` (`uv add "fastapi[standard]"` or `pip install "fastapi[standard]"`).
- `standard` includes: `fastapi-cli[standard]` (`fastapi dev` / `fastapi run`, FastAPI Cloud CLI); `uvicorn[standard]` (server with uvloop); `httpx` (`TestClient`); `jinja2` (`Jinja2Templates`); `python-multipart` (`Form()`, `File()` / `UploadFile`); `email-validator` (Pydantic `EmailStr`); `pydantic-settings` (`BaseSettings`); `pydantic-extra-types`; `opentelemetry-sdk`, OTLP exporter (telemetry export).
- Also `standard-no-fastapi-cloud-cli` (same without cloud CLI) and `all`. Plain `fastapi` requires users to add dependencies they use; forms fail without `python-multipart`.

## Versioning
- FastAPI remains `0.x`; repository version `0.142.2`, declared in `fastapi/__init__.py`. Under semantic versioning, any minor bump may break compatibility. Pin tested versions (e.g. `fastapi[standard]>=0.112.0,<0.113.0`) and upgrade deliberately with tests.

## Alternatives and how FastAPI compares
- Django / Django REST Framework: docs and batteries included; FastAPI keeps automatic docs without ORM coupling. Flask: minimal, decoupled, “plug in what you need” style.
- Requests inspired `@app.get`, `@app.post`; Swagger / OpenAPI supplied the standard schema. Marshmallow, Webargs, APISpec, Flask-apispec: validation, parsing, schema generation replaced by Pydantic and type hints.
- NestJS / Angular inspired dependency injection, made type-hint based and less verbose. Sanic, Falcon, Molten, Hug, APIStar contributed performance, async, typed parameters and schema-generation ideas.

## Reading benchmarks
- Chain: Uvicorn → Starlette → FastAPI; FastAPI cannot be faster than Starlette, nor Starlette faster than Uvicorn. Compare Uvicorn with ASGI/WSGI servers (Hypercorn, Daphne, uWSGI), Starlette with micro-frameworks (Sanic, Flask, Django), and FastAPI with frameworks doing validation, serialization and docs (Flask-apispec, NestJS, Molten).
- FastAPI’s validation/serialization replaces work otherwise done manually; real-world overhead is usually similar or lower. `app.openapi()` generates OpenAPI on first use and caches it in `app.openapi_schema`; it regenerates only if routes change, so docs add no per-request endpoint cost.

## Ecosystem tools
- FastAPI CLI: `fastapi dev`, `fastapi run`.
- VS Code and Cursor FastAPI editor extension: path operation explorer, route search, CodeLens links from `client.get(...)` test calls to path operations, FastAPI Cloud deployment and log streaming. Discovers apps by scanning for `FastAPI()`; if detection fails, set `[tool.fastapi]` in `pyproject.toml` or `fastapi.entryPoint` (module notation such as `myapp.main:app`).
- Full Stack FastAPI Template: FastAPI + SQLModel + PostgreSQL, React/TypeScript frontend with generated client, Docker Compose, JWT auth, password hashing, Pytest tests, Traefik and GitHub Actions CI/CD. FastAPI Cloud is the FastAPI team’s hosting service; SQLModel is the tutorial’s recommended SQL library.
