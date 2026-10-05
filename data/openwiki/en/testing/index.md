# Files

- [Async Tests and Testing Databases](async-tests-and-database-testing.md) - Write async test functions with @pytest.mark.anyio and httpx.AsyncClient over ASGITransport, handle lifespan and event-loop pitfalls, and test database-backed apps by overriding the session dependency with a test database.
- [Testing with TestClient](testing-basics.md) - Test FastAPI apps with pytest and TestClient (HTTPX-based) — plain def test functions, separating app and tests into modules, and sending path/query parameters, headers, JSON bodies, form data and cookies.
- [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md) - Replace dependencies in tests with app.dependency_overrides, run lifespan and startup/shutdown code by using TestClient as a context manager, and test WebSocket endpoints with client.websocket_connect().
