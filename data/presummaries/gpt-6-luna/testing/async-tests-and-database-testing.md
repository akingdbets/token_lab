## When you need async tests
- `TestClient` can test `async def` endpoints from normal `def` tests. If the test itself must `await` something (e.g. query an async database driver), it must be `async`, so use `httpx.AsyncClient` instead of synchronous `TestClient`.

## Example
- Mark the test with `@pytest.mark.anyio`; the AnyIO pytest plugin runs it asynchronously and is installed with Starlette/FastAPI, so `pytest-asyncio` is unnecessary.
- `ASGITransport(app=app)` sends requests to the ASGI app in-process, without a server or network. `base_url` is required for relative URLs; any value works, e.g. `"http://test"`.
- Use `await ac.get(...)`, `await ac.post(...)`, etc.; the API is the same as `TestClient` (both are HTTPX-based). Run with `pytest` as usual.
- Example asserts `response.status_code == 200` and `response.json() == {"message": "Tomato"}`.

## Pitfalls
- `AsyncClient` + `ASGITransport` does not run lifespan events. For apps relying on `lifespan`/startup, wrap the app with `LifespanManager` from `asgi-lifespan`, and use `ASGITransport(app=manager.app)`. With `TestClient`, use `with TestClient(app) as client:` (see [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md)).
- `RuntimeError: Task attached to a different loop` can occur (e.g. with MongoDB's `MotorClient`). Create event-loop-bound objects inside async code, such as a lifespan or startup handler, not at import time.
- After a request, an async test can call other `async` functions, e.g. to check the database.

## Testing with a database
- Recommended: point the app at a separate test database by overriding the session dependency. `get_session` is the `yield` dependency from [SQL Databases with SQLModel](../integrations/sql-databases.md); `app.dependency_overrides` swaps it for a test session.
- Example uses `create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)`, creates tables with `SQLModel.metadata.create_all(engine)`, and yields a `Session(engine)`. An in-memory SQLite database with `StaticPool` gives each test a fresh, fast database shared across threads.
- Pytest fixtures provide tables, session and client, then `app.dependency_overrides.clear()` isolates tests. The `session` fixture can insert data directly or verify endpoint writes. Example `test_create_hero` posts to `"/heroes/"` and asserts status `200` and name `"Deadpond"`.

## Related
- [Testing with TestClient](testing-basics.md); [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md); [Settings](../app-structure/settings.md) — overriding configuration in tests.
