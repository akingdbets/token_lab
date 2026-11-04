---
type: overview
title: Features, Alternatives and Ecosystem
description: What FastAPI gives you on top of Starlette and pydantic, how it compares to other python frameworks, how to read benchmarks, the install extras, the editor extension and the Full Stack FastAPI Template.
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

H1: FEATURES, ALTERNATIVES AND ECOSYSTEM

FASTAPI IS A python WEB FRAMEWORK FOR BUILDING APIs FROM standard python TYPE HINTS.
THIS PAGE COVERS ITS FOUNDATIONS, ADDITIONS, AND USER-FACING TOOLS.
THE WIKI COVERS FEATURE USE; START AT [QUICKSTART](../quickstart.md).

H2: WHAT FASTAPI IS BUILT ON

FASTAPI BUILDS ON TWO LIBRARIES AND TYPICALLY RUNS VIA A THIRD.

| LAYER | ROLE | PROVIDED |
|---|---|---|
| **uvicorn** (OR ANOTHER ASGI SERVER) | RUNS THE app | HTTP SERVER PROCESS |
| **Starlette** | ASGI WEB TOOLKIT | ROUTING, REQUESTS/RESPONSES, WebSockets, MIDDLEWARE, BACKGROUND TASKS, TEST CLIENT, STATIC FILES, SESSIONS |
| **pydantic** (v2) | DATA VALIDATION | PARSING, VALIDATION, SERIALIZATION, JSON SCHEMA FOR YOUR MODELS |
| **FastAPI** | API FRAMEWORK | TYPE-HINT-DRIVEN PARAMETERS, DEPENDENCY INJECTION, SECURITY UTILITIES, AUTOMATIC OpenAPI AND docs |

`FastAPI` IS A SUBCLASS OF Starlette'S APPLICATION class
(`class FastAPI(Starlette)` IN `fastapi/applications.py`).
THEREFORE, Starlette CODE—MIDDLEWARE, `Request`, RESPONSE CLASSES, ROUTES—
WORKS UNCHANGED INSIDE A FastAPI app.

THE PACKAGE REQUIRES python 3.10+ AND DEPENDS ON `starlette`,
`pydantic>=2.9.0`, `typing-extensions`, `typing-inspection`, `annotated-doc`
AND `opentelemetry-api` (SEE `pyproject.toml`).
pydantic v1 MODELS ARE no LONGER THE PRIMARY PATH;
SEE [DATACLASSES AND pydantic VERSIONS](../models/dataclasses-and-pydantic-versions.md).

H2: MAIN FEATURES
- OPEN STANDARDS: EVERY app PRODUCES AN OpenAPI SCHEMA, INCLUDING JSON Schema FOR MODELS; SERVED AT `/openapi.json` BY DEFAULT. SEE [API Metadata and docs UIs](../OpenAPI/metadata-and-docs-ui.md).
- AUTOMATIC INTERACTIVE docs: Swagger UI AT `/docs`; ReDoc AT `/redoc`.
- MODERN python: PARAMETERS, BODIES, RESPONSES DECLARED WITH TYPE HINTS (`int`, `str`, `list[Item]`, `Annotated[...]`, pydantic MODELS). SEE [python types and async/await](../getting-started/python-types-and-async.md).
- EDITOR SUPPORT: typing ENABLES COMPLETION AND TYPE CHECKS FOR Request DATA INSIDE FUNCTIONS.
- VALIDATION: pydantic VALIDATES JSON OBJECTS, ARRAYS, LENGTH-CONSTRAINED STRINGS, BOUNDED NUMBERS, AND EXOTIC types (URLs, EMAILS, UUIDs). ERRORS AUTOMATICALLY RETURN TO CLIENTS AS `422` RESPONSES.
- SECURITY/AUTHENTICATION: OAuth2 (INCLUDING JWT), HTTP Basic/Bearer, API KEYS IN HEADERS, QUERY OR COOKIES, AND OpenID Connect; all REUSABLE DEPENDENCIES. SEE [Security Basics](../security/oauth2-password-flow.md).
- DEPENDENCY INJECTION: DEPENDENCIES MAY HAVE DEPENDENCIES, FORMING A GRAPH FastAPI RESOLVES PER Request; THEIR PARAMETERS ARE ALSO VALIDATED AND DOCUMENTED. SEE [Dependency Injection Basics](../dependencies/dependency-injection-basics.md).
- Starlette FEATURES: WebSockets, IN-PROCESS BACKGROUND TASKS, LIFESPAN EVENTS, HTTPX-BASED `TestClient`, CORS, GZip, STATIC FILES, STREAMING RESPONSES, SESSIONS, COOKIES.

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

H2: INSTALLATION EXTRAS

BASE PACKAGE: `fastapi`. MOST USERS INSTALL `standard` extra:

```bash
uv add "fastapi[standard]"   # or: pip install "fastapi[standard]"
```

`standard` extra, DEFINED IN `pyproject.toml`, INSTALLS:
- `fastapi-cli[standard]`: `fastapi dev` / `fastapi run` COMMANDS AND FastAPI cloud CLI.
- `uvicorn[standard]`: SERVER RUNNING WITH uvloop.
- `httpx`: `TestClient`.
- `jinja2`: `Jinja2Templates`.
- `python-multipart`: `Form()` AND `File()` / `UploadFile`.
- `email-validator`: pydantic `EmailStr`.
- `pydantic-settings`: `BaseSettings`; SEE [settings](../app-structure/settings.md).
- `pydantic-extra-types`: extra pydantic types.
- `opentelemetry-sdk`, OTLP EXPORTER: TELEMETRY EXPORT; SEE [GraphQL and OpenTelemetry](../integrations/GraphQL-and-opentelemetry.md).

ALSO AVAILABLE: `standard-no-fastapi-cloud-cli` (SAME, WITHOUT cloud CLI) AND `all`. WITH PLAIN `fastapi`, YOU MUST ADD EACH extra YOU USE; e.g., FORMS FAIL WITHOUT `python-multipart`.

H2: VERSIONING

FastAPI REMAINS `0.x`; THIS REPOSITORY IS VERSION `0.142.2`, DECLARED IN `fastapi/__init__.py`. UNDER SEMANTIC VERSIONING, ANY MINOR BUMP MAY CONTAIN BREAKING CHANGES. PIN THE TESTED VERSION, e.g. `fastapi[standard]>=0.112.0,<0.113.0`, AND UPGRADE DELIBERATELY WITH TESTS. DETAILS: [Deployment Concepts](../deployment/deployment-concepts-and-servers.md).

H2: ALTERNATIVES AND HOW FastAPI COMPARES

FastAPI DREW IDEAS FROM MANY EARLIER TOOLS, DOCUMENTED IN `docs/en/docs/alternatives.md` AND `history-design-future.md`:
- DJANGO / DJANGO REST FRAMEWORK: AUTOMATIC API docs ∧ BATTERIES-INCLUDED APPROACH; FastAPI KEEPS AUTOMATIC docs BUT AVOIDS ORM COUPLING.
- FLASK: SIMPLE MICRO-FRAMEWORK WITH DECOUPLED PIECES; FastAPI KEEPS MINIMAL CORE ∧ "plug in what you need" STYLE.
- Requests’ SIMPLE, INTUITIVE `get`/`post` API STYLE INSPIRES PATH OPERATION DECORATORS (`@app.get`, `@app.post`).
- Swagger / OpenAPI: ADOPTED AS standard SCHEMA, NOT CUSTOM SCHEMA.
- Marshmallow, Webargs, APISpec, Flask-APISpec: VALIDATION, Request PARSING ∧ SCHEMA GENERATION; FastAPI REPLACES THESE WITH pydantic ∧ TYPE HINTS.
- NestJS / Angular: DEPENDENCY INJECTION; FastAPI’S IS TYPE-HINT-BASED ∧ LESS VERBOSE.
- Sanic, Falcon, Molten, Hug, APIStar: IDEAS FOR PERFORMANCE, ASYNC, TYPE-HINT PARAMETER DECLARATION ∧ SCHEMA GENERATION.

H2: Reading benchmarks

DEPENDENCY CHAIN: uvicorn → Starlette → FastAPI.
∴ FastAPI CANNOT BE FASTER THAN Starlette, WHICH CANNOT BE FASTER THAN uvicorn.
COMPARE LIKE WITH LIKE:
- uvicorn VS OTHER ASGI/WSGI SERVERS (Hypercorn, Daphne, uWSGI).
- Starlette VS MICRO-FRAMEWORKS (Sanic, Flask, Django).
- FastAPI VS FRAMEWORKS THAT ALSO DO VALIDATION, SERIALIZATION ∧ docs
  (Flask-APISpec, NestJS, Molten).

FastAPI’S VALIDATION ∧ SERIALIZATION IS WORK YOU WOULD OTHERWISE WRITE YOURSELF;
REAL-WORLD OVERHEAD IS USUALLY SIMILAR OR LOWER.
`app.openapi()` GENERATES THE OpenAPI SCHEMA ON FIRST USE; THE SCHEMA IS CACHED
IN `app.openapi_schema` AND REGENERATED ONLY IF THE SET OF ROUTES CHANGES.
∴ docs ADD no PER-Request COST TO API ENDPOINTS.

H2: Ecosystem tools

- FastAPI CLI (`fastapi dev`, `fastapi run`): SEE
  [First Steps and the FastAPI CLI](../getting-started/first-steps.md).
- FastAPI EDITOR EXTENSION FOR VS Code AND Cursor: PATH OPERATION EXPLORER,
  ROUTE SEARCH, CodeLens LINKS FROM `client.get(...)` TEST CALLS TO THEIR PATH
  OPERATIONS, FastAPI cloud DEPLOYMENT ∧ LOG STREAMING.
  IT DISCOVERS APPS BY SCANNING FOR `FastAPI()`.
  IF DETECTION FAILS, SET AN ENTRYPOINT VIA `[tool.fastapi]` IN `pyproject.toml`
  OR THE `fastapi.entryPoint` SETTING (MODULE NOTATION SUCH AS `myapp.main:app`).
- Full Stack FastAPI Template: STARTER PROJECT WITH FastAPI + SQLModel +
  PostgreSQL; React/TypeScript FRONTEND WITH GENERATED CLIENT; Docker Compose;
  JWT AUTH; PASSWORD HASHING; Pytest TESTS; Traefik; GitHub Actions CI/CD.
- FastAPI cloud: HOSTING SERVICE BY THE FastAPI TEAM; SEE
  [HTTPS and cloud](../deployment/HTTPS-and-cloud.md).
- SQLModel: RECOMMENDED SQL LIBRARY IN THE TUTORIAL; SEE
  [SQL Databases](../integrations/SQL-databases.md).
