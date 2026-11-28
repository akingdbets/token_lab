## Overriding dependencies
- `app.dependency_overrides` is a plain `dict` on the `FastAPI` app: key = original dependency callable; value = replacement callable. Use it when tests should avoid external services or real databases, or need fixed values.
- FastAPI checks overrides while solving dependencies for every request. It calls the override instead of the original; the original and its sub-dependencies do not run. The override’s own signature determines which request parameters are read and validated.
- Overrides apply wherever the dependency is used: function parameters, decorator `dependencies=[...]`, routers, `include_router()`, global app dependencies, and sub-dependencies. The replacement can be `async def`, `def`, a `yield` function, a class, or a lambda.
- Example: `app.dependency_overrides[common_parameters] = override_dependency`. If `override_dependency(q: str | None = None)` returns `{"q": q, "skip": 5, "limit": 10}`, URL `skip`/`limit` are ignored. Example tests assert status `200`; `/items/?q=foo&skip=100&limit=200` returns `{"message": "Hello Items!", "params": {"q": "foo", "skip": 5, "limit": 10}}`.
- Reset with `app.dependency_overrides = {}` or `app.dependency_overrides.clear()`. To override only in some tests, set at test start (or in a pytest fixture) and clear at end. Typical uses: `get_settings` ([Settings](../app-structure/settings.md)), `get_session` ([Async Tests and Testing Databases](async-tests-and-database-testing.md)), and current-user dependencies.

## Testing lifespan and startup/shutdown
- `TestClient` runs app lifespan only as a context manager: startup on entering `with`, shutdown on leaving. A module-level `client = TestClient(app)` used without `with` does **not** run lifespan.
- In the example, `lifespan(app: FastAPI)` adds `"foo": {"name": "Fighters"}` and `"bar": {"name": "Tenders"}` to `items`; it clears `items` after `yield`. Before the context `items == {}`; inside it, a request to `/items/foo` returns status `200` and `{"name": "Fighters"}`; after it, `items == {}`.
- The same applies to deprecated `@app.on_event("startup")` / `("shutdown")` handlers. For `httpx.AsyncClient`, use `asgi-lifespan`’s `LifespanManager` ([Async Tests](async-tests-and-database-testing.md)). See [Lifespan Events](../app-structure/lifespan-events.md).

## Testing WebSockets
- Use `client.websocket_connect(path)` as a context manager. The example `/ws` endpoint accepts, sends `{"msg": "Hello WebSocket"}`, then closes; the test receives JSON and asserts that value.
- Session methods: `send_text()`, `send_bytes()`, `send_json()`, `receive_text()`, `receive_bytes()`, `receive_json()`, `close()`. Pass query parameters in the URL, and `headers=` / cookies on the client for auth.
- If the server closes or rejects the connection (e.g. `WebSocketException` with code `1008`), the test client raises `WebSocketDisconnect`; assert with `pytest.raises`. See [WebSockets](../integrations/websockets.md).

## Related
- [Testing with TestClient](testing-basics.md); [Dependency Injection Basics](../dependencies/dependency-injection-basics.md); [How FastAPI Handles a Request](../internals/request-handling-internals.md) (where overrides are applied).
