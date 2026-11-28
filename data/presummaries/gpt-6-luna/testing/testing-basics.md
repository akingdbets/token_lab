# Testing with TestClient

- `fastapi.testclient.TestClient` is Starlette’s `TestClient`, re-exported by FastAPI. It calls the app in-process, needs no server, is built on **HTTPX** (whose API mirrors `requests`), and works with **pytest**.
- Install with `uv add httpx` and `uv add pytest` (`httpx` is part of `fastapi[standard]`). Run tests with `uv run pytest`.

## A first test

- Create `TestClient(app)`; write pytest-convention functions named `test_...`. Use `client.get()`, `client.post()`, `client.put()`, `client.delete()`, etc., and plain `assert` on `response.status_code`, `response.json()`, `response.headers`, or `response.text`.
- Tests are normal `def` even for `async def` endpoints; the client runs the app. If the test itself must `await` (e.g. an async DB call), see [Async Tests](async-tests-and-database-testing.md).
- Example: `GET /` returns `{"msg": "Hello World"}`; assert status `200` and that JSON.

## Separating app and tests

- Typical layout: `app/__init__.py`, `app/main.py`, `app/test_main.py`. With `__init__.py`, `from .main import app` works. The test creates `TestClient(app)` and asserts `GET /` returns status `200` and `{"msg": "Hello World"}`.

## Extended example: headers, bodies, error cases

- `Item` has `id: str`, `title: str`, and `description: str | None = None`. `GET /items/{item_id}` and `POST /items/` require `x_token: Annotated[str, Header()]`; valid token is `"coneofsilence"`.
- Invalid token raises `HTTPException` status `400`, detail `"Invalid X-Token header"`; missing item returns `404`, detail `"Item not found"`; duplicate ID on creation returns `409`, detail `"Item already exists"`. Successful requests return `200`. Creation stores `item.model_dump()`.
- Test both success and failure paths; send headers such as `{"X-Token": "coneofsilence"}` and JSON with `json={...}`.

## Passing data in requests

- Path/query: URL (e.g. `client.get("/items/foo?q=1")`) or `params={"q": 1}`; JSON: `json={...}`; forms: `data={...}`; files: `files={"file": ("name.txt", b"content")}`; headers: `headers={...}`; cookies: `cookies={...}` on request or client.
- HTTPX/`requests` docs cover most sending questions. Convert Pydantic models to JSON using `jsonable_encoder` or `model.model_dump(mode="json")`.

## Related

- [Testing Dependencies, Lifespan Events and WebSockets](testing-dependencies-events-websockets.md): `dependency_overrides`, `with TestClient(app)`, `websocket_connect`.
- [Async Tests and Testing Databases](async-tests-and-database-testing.md); [Settings](../app-structure/settings.md) covers overriding settings in tests.
