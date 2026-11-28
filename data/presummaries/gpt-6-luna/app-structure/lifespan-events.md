## Lifespan Events
- Use `FastAPI`’s or `APIRouter`’s `lifespan` parameter to create application-wide resources once and release them at shutdown. Lifespan code runs before the app receives requests and after it finishes handling them—not at import time—keeping imports cheap and setup/teardown together.
- In an async context manager, receive `app` and `yield` exactly once. Code before `yield` runs at startup; requests wait for it to finish. Code after `yield` runs at shutdown, after requests are done. `@asynccontextmanager` wraps the generator; it is the clearest option.
- `APIRouter.__init__` automatically wraps async generator functions with `asynccontextmanager` and plain (sync) generator functions into an async context manager; other forms are used as-is.
- Example: `ml_models["answer_to_everything"]` is set to `fake_answer_to_everything_ml_model`, which returns `x * 42`; after `yield`, `ml_models.clear()` releases it. `/predict` uses it to return `{"result": result}`.

## Lifespan state
- A lifespan can `yield` a dictionary instead of using module-level globals. Starlette lifespan state copies the yielded mapping into each request’s state, accessible through `request.state`. The example yields `{"http_client": client}` from an `httpx.AsyncClient` context; `proxy` gets `https://example.com` and returns `{"status": response.status_code}`.

## Lifespans on routers
- `APIRouter` accepts `lifespan=`. `include_router()` merges it into the parent via `_merge_lifespan_context` in `fastapi/routing.py`: parent enters first, included router next, and teardown runs in reverse order. If both yield dictionaries, they merge and the parent wins duplicate keys. Router `on_startup` / `on_shutdown` handlers are also copied to the parent.

## Deprecated: `startup` and `shutdown` events
- `on_event` is marked `@deprecated` in favor of `lifespan`, though event handlers still work. Handlers can be `async def` or plain `def`; lists can be passed via `FastAPI(on_startup=[...], on_shutdown=[...])`.
- Use all `lifespan` or all events, not both. Without `lifespan`, FastAPI’s internal `_DefaultLifespan` runs event handlers for backward compatibility; providing `lifespan` replaces it, so that app’s event handlers are not called. Examples set `items["foo"]` and `items["bar"]` at startup and append `"Application shutdown"` to `log.txt` at shutdown.

## Caveats
- Lifespan events run only for the main application, not sub-applications mounted with `app.mount()`.
- In tests, lifespan runs only with `TestClient` used as a context manager: `with TestClient(app) as client:`.
- For per-request setup/teardown, such as a DB session per request, use dependencies with `yield`, not lifespan.
