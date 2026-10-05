---
type: tutorial
title: First Steps and the FastAPI CLI
description: Create a minimal FastAPI app, understand paths, operations, path operation decorators and functions, run it with fastapi dev / fastapi run, configure the entrypoint in pyproject.toml, and explore /docs, /redoc and /openapi.json.
tags: [getting-started, fastapi-cli, fastapi-dev, fastapi-run, path-operation, openapi, docs]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-e912e06b230ad432d81148c2
    resource: repo://docs_src/first_steps/tutorial001_py310.py
  - id: openwiki-source-0d5fbd2e5c9e1777ecbb618b
    resource: repo://docs_src/first_steps/tutorial003_py310.py
  - id: openwiki-source-9bc15a21c009b14775a3dd72
    resource: repo://docs/en/docs/fastapi-cli.md
  - id: openwiki-source-95935867654abe313559916b
    resource: repo://docs/en/docs/tutorial/first-steps.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-dc198b5a2f25036adad646d4
    resource: repo://fastapi/cli.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# First Steps and the FastAPI CLI

## The simplest app

`docs_src/first_steps/tutorial001_py310.py`:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
```

Step by step:

1. **Import `FastAPI`** — a Python class (a subclass of Starlette) that provides all the functionality for your API.
2. **Create an instance**: `app = FastAPI()`. This `app` is what the server runs and what you configure (title, docs URLs, middleware, …).
3. **Declare a path operation** with a decorator: `@app.get("/")` means "the function below handles `GET` requests to path `/`".
4. **Define the path operation function** (`root`). It can be `async def` or plain `def` (`tutorial003_py310.py`); see [Python Types and async/await](python-types-and-async.md).
5. **Return content**: a `dict`, `list`, `str`, `int`, Pydantic model, etc. It is converted to JSON automatically.

### Paths and operations

- **Path** (also "endpoint" or "route"): the part of the URL after the domain, starting with `/` — e.g. `/items/foo` in `https://example.com/items/foo`.
- **Operation**: an HTTP method. Decorators exist for each: `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()`, plus `@app.options()`, `@app.head()`, `@app.patch()`, `@app.trace()`.

Conventionally `POST` creates, `GET` reads, `PUT` updates and `DELETE` deletes, but FastAPI enforces no meaning (GraphQL, for instance, uses only `POST`). A "path operation" is a path + operation pair, handled by one function.

## Running the app with the FastAPI CLI

Installing `fastapi[standard]` provides the `fastapi` command (from the `fastapi-cli` package; `fastapi/cli.py` raises an error telling you to install `fastapi[standard]` if it's missing).

```bash
fastapi dev main.py      # or: uv run fastapi dev
```

`fastapi dev`:

- finds the `FastAPI` app object in the module (searching up through `__init__.py` package structure to build the import, e.g. `from main import app`);
- runs Uvicorn with **auto-reload** on file changes;
- listens on `127.0.0.1:8000` (local only);
- sets the `FASTAPI_ENV` environment variable to `development` if not already set.

```bash
fastapi run main.py
```

`fastapi run` is for production: **no reload**, listens on `0.0.0.0` (all interfaces), and leaves `FASTAPI_ENV` unchanged. See [Deployment Concepts, Servers and Workers](../deployment/deployment-concepts-and-servers.md).

### Configure the entrypoint once

Instead of passing a path every time, declare the app location in `pyproject.toml`:

```toml
[tool.fastapi]
entrypoint = "main:app"
```

This means `from main import app`. For a package layout like `backend/main.py`, use `entrypoint = "backend.main:app"`. Then plain `fastapi dev` / `fastapi run` work, and so do the FastAPI editor extension and FastAPI Cloud.

Alternatives: `fastapi dev main.py` (guess the app from a file) or `fastapi dev --entrypoint main:app`.

## Check it

Open `http://127.0.0.1:8000` → `{"message": "Hello World"}`.

### Interactive docs

- **Swagger UI** at `http://127.0.0.1:8000/docs` — try requests from the browser.
- **ReDoc** at `http://127.0.0.1:8000/redoc` — alternative documentation.

Both are generated from the **OpenAPI** schema at `http://127.0.0.1:8000/openapi.json`:

```json
{
    "openapi": "3.1.0",
    "info": {"title": "FastAPI", "version": "0.1.0"},
    "paths": {
        "/items/": {
            "get": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {"application/json": {}}
                    }
                }
            }
        }
    }
}
```

**OpenAPI** describes your API's paths, parameters and responses; data shapes ("schemas") use **JSON Schema**. The same schema powers the docs UIs and client code generators. The default OpenAPI version is `3.1.0`. Customize the title, description, URLs or disable the docs in [API Metadata and Docs UIs](../openapi/metadata-and-docs-ui.md).

## Deploying (optional)

`fastapi deploy` deploys the app to FastAPI Cloud; see [HTTPS, TLS Termination and Cloud Providers](../deployment/https-and-cloud.md).

## Next steps

- [Path Parameters](../request/path-parameters.md) and [Query Parameters](../request/query-parameters.md)
- [Request Body](../request/request-body.md)
- [Development Workflow](development-workflow.md) — uv, env vars, debugging
