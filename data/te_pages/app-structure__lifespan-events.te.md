---
type: guide
title: lifespan events
description: RUN CODE ONCE BEFORE app SERVES REQUESTS, ONCE AFTER IT STOPS; USE lifespan async CONTEXT MANAGER; ROUTER lifespan MERGING, lifespan STATE, deprecated startup/shutdown events.
tags: [lifespan, startup, shutdown, on_event, events, resources]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-3cec1b06c25d3cf1c240cc47
    resource: repo://docs_src/events/tutorial003_py310.py
  - id: openwiki-source-f3f5740af79e7e432255437e
    resource: repo://docs/en/docs/advanced/events.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: lifespan events

RESOURCES TO CREATE ONCE FOR WHOLE app: MACHINE LEARNING MODEL,
DATABASE CONNECTION POOL, HTTP client.
RELEASE RESOURCES WHEN app SHUTS DOWN.
FastAPI SUPPORTS THIS VIA `lifespan` PARAMETER OF `FastAPI` AND `APIRouter`.

lifespan CODE RUNS BEFORE app STARTS RECEIVING REQUESTS AND AFTER IT
FINISHES HANDLING THEM; NOT AT IMPORT TIME.
∴ IMPORTS STAY CHEAP (USEFUL FOR TESTS AND TOOLING);
SETUP/TEARDOWN STAY TOGETHER.

H2: THE `lifespan` async CONTEXT MANAGER

FROM `docs_src/events/tutorial003_py310.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model
    yield
    # Clean up the ML models and release the resources
    ml_models.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/predict")
async def predict(x: float):
<!-- openwiki: broken internal link [x] file "x" does not exist. Fix the href or restore the target, then delete this comment. -->
    result = ml_models["answer_to_everything"](x)
    return {"result": result}
```

HOW IT WORKS:
- FUNCTION RECEIVES `app`; MUST `yield` EXACTLY ONCE.
- EVERYTHING BEFORE `yield` RUNS AT startup; app SERVES NO REQUESTS
  UNTIL IT FINISHES.
- EVERYTHING AFTER `yield` RUNS AT shutdown, AFTER REQUESTS FINISH.
- `@asynccontextmanager` TURNS GENERATOR INTO async CONTEXT MANAGER,
  LIKE `async with lifespan(app): ...`.

FastAPI LENIENT ABOUT PASSED FORM:
IN `APIRouter.__init__`, async GENERATOR FUNCTION IS AUTOMATICALLY
WRAPPED with `asynccontextmanager`;
PLAIN (SYNC) GENERATOR FUNCTION IS WRAPPED INTO async CONTEXT MANAGER;
ANYTHING ELSE IS USED as-IS.
EXPLICIT `@asynccontextmanager`, as IN DOCS, IS CLEAREST OPTION.

H2: lifespan STATE

INSTEAD OF MODULE-LEVEL GLOBALS, lifespan CAN `yield` A DICTIONARY.
THIS IS Starlette'S *lifespan STATE*:
YIELDED MAPPING IS COPIED INTO EACH REQUEST'S STATE;
ENDPOINTS CAN READ IT VIA `request.state`:

```python
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        yield {"http_client": client}


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def proxy(request: Request):
    response = await request.state.http_client.get("https://example.com")
    return {"status": response.status_code}
```

H2: LIFESPANS ON ROUTERS

`APIRouter` ALSO ACCEPTS `lifespan=`.
ON `include_router()`, FastAPI MERGES INCLUDED ROUTER'S lifespan
INTO PARENT'S (`_merge_lifespan_context` IN `fastapi/routing.py`):
- PARENT lifespan ENTERS FIRST, THEN INCLUDED ROUTER'S (NESTED);
  TEARDOWN RUNS IN REVERSE ORDER.
- IF BOTH yield STATE DICTIONARIES, MERGE INTO ONE;
  ON DUPLICATE KEYS, PARENT'S VALUE WINS.

ROUTER `on_startup` / `on_shutdown` HANDLERS ALSO COPY TO PARENT
ON INCLUSION.

H2: deprecated: `startup` AND `shutdown` events

OLDER CODE USES EVENT HANDLERS.
THEY STILL WORK, BUT `on_event` IS MARKED `@deprecated` IN FAVOR
OF `lifespan`.

```python
from fastapi import FastAPI

app = FastAPI()

items = {}


@app.on_event("startup")
async def startup_event():
    items["foo"] = {"name": "Fighters"}
    items["bar"] = {"name": "Tenders"}


@app.on_event("shutdown")
def shutdown_event():
    with open("log.txt", mode="a") as log:
        log.write("Application shutdown")
```

(`docs_src/events/tutorial001_py310.py` AND `tutorial002_py310.py`.)
HANDLERS CAN BE `async def` OR PLAIN `def`.
ALSO PASS LISTS VIA `FastAPI(on_startup=[...], on_shutdown=[...])`.

ALL `lifespan` OR ALL events; NOT BOTH.
WHEN NO `lifespan` IS GIVEN, FastAPI USES INTERNAL `_DefaultLifespan`
THAT RUNS `on_startup` / `on_shutdown` HANDLERS
(Starlette REMOVED THIS; FastAPI KEEPS IT FOR BACKWARD COMPATIBILITY).
WHEN `lifespan` IS PROVIDED, THAT DEFAULT IS REPLACED;
THAT app'S EVENT HANDLERS ARE NO LONGER CALLED.

H2: CAVEATS
- lifespan events RUN ONLY FOR MAIN APPLICATION, NOT SUB-APPLICATIONS MOUNTED with `app.mount()` (SEE [SUB-APPLICATIONS](sub-applications-proxy-and-wsgi.md)).
- IN TESTS, lifespan RUNS ONLY WHEN `TestClient` IS USED as A CONTEXT MANAGER (`with TestClient(app) as client:`). SEE [TESTING DEPENDENCIES, lifespan events AND WebSockets](../testing/testing-dependencies-events-websockets.md).
- FOR PER-REQUEST SETUP/TEARDOWN (e.g., A DB SESSION PER REQUEST), USE [DEPENDENCIES with `yield`](../dependencies/dependencies-with-yield.md), NOT lifespan.

H2: RELATED

- [SETTINGS AND ENVIRONMENT VARIABLES](settings.md)
- [SQL DATABASES with SQLModel](../integrations/SQL-databases.md) — CREATING TABLES AT startup
