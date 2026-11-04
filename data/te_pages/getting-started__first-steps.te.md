---
type: tutorial
title: First Steps and the FastAPI CLI
description: Create a minimal FastAPI app, understand paths, operations, path operation decorators and functions, run it with fastapi dev / fastapi run, configure the entrypoint in pyproject.toml, and explore /docs, /redoc and /openapi.json.
tags: [getting-started, fastapi-cli, fastapi-dev, fastapi-run, path-operation, OpenAPI, docs]
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
H1: FIRST STEPS AND THE FastAPI CLI
H2: THE SIMPLEST app
`docs_src/first_steps/tutorial001_py310.py`:
```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
```
STEP BY STEP:
1. import `FastAPI`: Python class (Starlette subclass) providing all API functionality.
2. CREATE INSTANCE: `app = FastAPI()`. Server runs `app`; configure it (title, docs URLs, middleware, …).
3. DECLARE PATH OPERATION WITH DECORATOR: `@app.get("/")` means "the function below handles `GET` requests to path `/`".
4. DEFINE PATH OPERATION FUNCTION (`root`): use `async def` or plain `def` (`tutorial003_py310.py`); see [Python Types and async/await](python-types-and-async.md).
5. RETURN CONTENT: `dict`, `list`, `str`, `int`, Pydantic model, etc.; automatically convert to JSON.
H3: PATHS AND OPERATIONS
- PATH (also "endpoint" or "route"): URL part after domain, starting with `/`; e.g. `/items/foo` in `https://example.com/items/foo`.
- OPERATION: HTTP method. Decorators exist for each: `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()`, plus `@app.options()`, `@app.head()`, `@app.patch()`, `@app.trace()`.
CONVENTION: `POST` creates, `GET` reads, `PUT` updates, `DELETE` deletes. FastAPI enforces no meaning (GraphQL, for instance, uses only `POST`). PATH OPERATION=PATH + OPERATION PAIR, HANDLED BY ONE FUNCTION.
H2: RUNNING THE app WITH THE FastAPI CLI
INSTALLING `fastapi[standard]` PROVIDES THE `fastapi` COMMAND (from THE `fastapi-cli` PACKAGE). IF MISSING, `fastapi/cli.py` RAISES AN ERROR TELLING YOU TO INSTALL `fastapi[standard]`.
```bash
fastapi dev main.py      # or: uv run fastapi dev
```
`fastapi dev`:
- FINDS THE `FastAPI` app OBJECT IN THE MODULE; SEARCHES UP THROUGH `__init__.py` PACKAGE STRUCTURE TO BUILD THE import, e.g. `from main import app`.
- RUNS Uvicorn WITH **AUTO-RELOAD** ON FILE CHANGES.
- LISTENS ON `127.0.0.1:8000` (LOCAL ONLY).
- SETS `FASTAPI_ENV` TO `development` IF NOT ALREADY SET.
```bash
fastapi run main.py
```
`fastapi run` IS FOR PRODUCTION: **NO RELOAD**, LISTENS ON `0.0.0.0` (ALL INTERFACES), AND LEAVES `FASTAPI_ENV` UNCHANGED. SEE [Deployment Concepts, Servers and Workers](../deployment/deployment-concepts-and-servers.md).
H3: CONFIGURE THE entrypoint ONCE
INSTEAD OF PASSING A PATH EACH TIME, DECLARE THE app LOCATION IN `pyproject.toml`:
```toml
[tool.fastapi]
entrypoint = "main:app"
```
THIS MEANS `from main import app`. FOR PACKAGE LAYOUT LIKE `backend/main.py`, USE `entrypoint = "backend.main:app"`. THEN PLAIN `fastapi dev` / `fastapi run` WORK; SO DO THE FastAPI EDITOR EXTENSION AND FastAPI Cloud.
ALTERNATIVES: `fastapi dev main.py` (GUESS app from FILE) OR `fastapi dev --entrypoint main:app`.
H2: CHECK IT
OPEN `http://127.0.0.1:8000` → `{"message": "Hello World"}`.
H3: INTERACTIVE docs
- **Swagger UI** AT `http://127.0.0.1:8000/docs`: TRY REQUESTS from BROWSER.
- **ReDoc** AT `http://127.0.0.1:8000/redoc`: ALTERNATIVE DOCUMENTATION.
BOTH GENERATED from OpenAPI SCHEMA AT `http://127.0.0.1:8000/openapi.json`:
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

OpenAPI DESCRIBES API PATHS, PARAMETERS ∧ RESPONSES; DATA SHAPES
("SCHEMAS") USE JSON SCHEMA.
SAME SCHEMA POWERS docs UIs ∧ CLIENT CODE GENERATORS.
DEFAULT OpenAPI VERSION: `3.1.0`.
CUSTOMIZE TITLE, DESCRIPTION, URLs OR DISABLE docs:
[API METADATA AND docs UIs](../OpenAPI/metadata-and-docs-ui.md).

H2: DEPLOYING (OPTIONAL)

`fastapi deploy` DEPLOYS app TO FASTAPI CLOUD; SEE
[HTTPS, TLS TERMINATION AND CLOUD PROVIDERS](../deployment/https-and-cloud.md).

H2: NEXT STEPS

- [PATH PARAMETERS](../request/path-parameters.md) ∧
  [QUERY PARAMETERS](../request/query-parameters.md)
- [REQUEST BODY](../request/request-body.md)
- [development WORKFLOW](development-workflow.md): uv, ENV VARS, DEBUGGING
