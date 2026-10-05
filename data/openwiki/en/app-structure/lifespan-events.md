---
type: guide
title: Lifespan Events
description: Run code once before the app starts serving requests and once after it stops, using the lifespan async context manager; how router lifespans merge, lifespan state, and the deprecated startup/shutdown events.
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

# Lifespan Events

Some resources should be created **once** for the whole application — a machine learning model, a database connection pool, an HTTP client — and released when the app shuts down. FastAPI supports this through the `lifespan` parameter of `FastAPI` (and `APIRouter`).

Code that runs in lifespan executes before the app starts **receiving requests** and after it **finishes handling them**, not at import time. That makes imports cheap (useful for tests and tooling) and keeps setup/teardown together.

## The `lifespan` async context manager

From `docs_src/events/tutorial003_py310.py`:

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

How it works:

- The function receives the `app` and must `yield` exactly once.
- Everything **before** `yield` runs at startup; the app does not serve requests until it finishes.
- Everything **after** `yield` runs at shutdown, after requests are done.
- Decorating with `@asynccontextmanager` turns the generator into an async context manager, like `async with lifespan(app): ...`.

FastAPI is lenient about the form you pass: in `APIRouter.__init__`, an async generator function is wrapped with `asynccontextmanager` automatically, a plain (sync) generator function is wrapped into an async context manager, and anything else is used as-is. Using `@asynccontextmanager` explicitly, as in the docs, is the clearest option.

## Lifespan state

Instead of module-level globals, the lifespan can `yield` a dictionary. This is Starlette's *lifespan state*: the yielded mapping is copied into each request's state, so endpoints can read it via `request.state`:

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

## Lifespans on routers

`APIRouter` also accepts `lifespan=`. When you call `include_router()`, FastAPI merges the included router's lifespan into the parent's (`_merge_lifespan_context` in `fastapi/routing.py`):

- The parent's lifespan is entered first, then the included router's (nested), so teardown runs in reverse order.
- If both yield state dictionaries, they are merged into one; on duplicate keys the parent's value wins.

Router `on_startup` / `on_shutdown` handlers are also copied to the parent on inclusion.

## Deprecated: `startup` and `shutdown` events

Older code uses event handlers. They still work but `on_event` is marked `@deprecated` in favor of `lifespan`.

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

(`docs_src/events/tutorial001_py310.py` and `tutorial002_py310.py`.) Handlers can be `async def` or plain `def`. You can also pass lists via `FastAPI(on_startup=[...], on_shutdown=[...])`.

**It is all `lifespan` or all events, not both.** When no `lifespan` is given, FastAPI uses an internal `_DefaultLifespan` that runs the `on_startup` / `on_shutdown` handlers (Starlette removed this, FastAPI keeps it for backward compatibility). When you provide `lifespan`, that default is replaced, so the event handlers of that app are no longer called.

## Caveats

- Lifespan events run only for the **main application**, not for sub-applications mounted with `app.mount()` (see [Sub-applications](sub-applications-proxy-and-wsgi.md)).
- In tests, lifespan runs only when you use `TestClient` as a context manager (`with TestClient(app) as client:`). See [Testing Dependencies, Lifespan Events and WebSockets](../testing/testing-dependencies-events-websockets.md).
- For per-request setup/teardown (e.g. a DB session per request) use [dependencies with `yield`](../dependencies/dependencies-with-yield.md), not lifespan.

## Related

- [Settings and Environment Variables](settings.md)
- [SQL Databases with SQLModel](../integrations/sql-databases.md) — creating tables at startup
