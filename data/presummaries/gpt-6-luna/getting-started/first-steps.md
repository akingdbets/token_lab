## The simplest app

- Minimal app:
  ```python
  from fastapi import FastAPI
  app = FastAPI()

  @app.get("/")
  async def root():
      return {"message": "Hello World"}
  ```
- `FastAPI` is a Python class and Starlette subclass. `app = FastAPI()` is the server’s app and can be configured (title, docs URLs, middleware, etc.).
- A path operation decorator such as `@app.get("/")` maps an HTTP method and path to the function below it. Functions can use `async def` or `def`; return `dict`, `list`, `str`, `int`, Pydantic models, etc., which FastAPI converts to JSON.

### Paths and operations

- A path (also “endpoint” or “route”) is the URL part after the domain, starting with `/`, e.g. `/items/foo`.
- Operations are HTTP methods. Decorators: `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()`, `@app.options()`, `@app.head()`, `@app.patch()`, `@app.trace()`.
- Conventionally `POST` creates, `GET` reads, `PUT` updates, and `DELETE` deletes, but FastAPI enforces no meaning; GraphQL, for example, uses only `POST`. A path operation is a path + operation pair handled by one function.

## Running the app with the FastAPI CLI

- Installing `fastapi[standard]` provides the `fastapi` command from `fastapi-cli`; if missing, `fastapi/cli.py` raises an error instructing installation.
- `fastapi dev main.py` (or `uv run fastapi dev`) finds the `FastAPI` app, searches package `__init__.py` structure to build its import (e.g. `from main import app`), runs Uvicorn with auto-reload, listens on `127.0.0.1:8000`, and sets `FASTAPI_ENV` to `development` only if not already set.
- `fastapi run main.py` is for production: no reload, listens on `0.0.0.0`, and leaves `FASTAPI_ENV` unchanged.

### Configure the entrypoint once

- In `pyproject.toml`, set `[tool.fastapi]` and `entrypoint = "main:app"` (means `from main import app`). For `backend/main.py`, use `entrypoint = "backend.main:app"`.
- Then plain `fastapi dev` / `fastapi run`, the FastAPI editor extension, and FastAPI Cloud work. Alternatives: `fastapi dev main.py` or `fastapi dev --entrypoint main:app`.

## Check it

- `http://127.0.0.1:8000` returns `{"message": "Hello World"}`.
- Swagger UI at `/docs` lets you try requests; ReDoc at `/redoc` is alternative documentation. Both use `/openapi.json`.
- OpenAPI describes paths, parameters, and responses; schemas use JSON Schema. It powers docs UIs and client code generators. Default OpenAPI version is `3.1.0`; example metadata is title `FastAPI`, version `0.1.0`, with a `200` “Successful Response”. Title, description, URLs, and docs can be customized/disabled.

## Deploying (optional)

- `fastapi deploy` deploys to FastAPI Cloud.

## Next steps

- Path Parameters, Query Parameters, Request Body, and Development Workflow (uv, env vars, debugging).
