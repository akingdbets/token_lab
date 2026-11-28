- **Dependency injection:** A dependency is a callable (function or class) whose parameters are declared like a path operation’s: query, path, header, cookie, body, or other dependencies. FastAPI provides its result per request. Uses include shared logic, database connections, security/authentication, and role checks; no plugin registration is needed.

- **A first dependency:** For `Depends(common_parameters)`, pass the function itself, not a call; `Depends` takes one callable. Per request FastAPI reads `q`, `skip`, and `limit` from the query string, converts and validates them (errors → 422), calls `common_parameters(...)`, then passes its result as `commons`. Dependency parameters appear in OpenAPI docs for each operation using them. Dependencies can be `async def` or `def`, mixed freely with endpoint styles; plain `def` dependencies run in a threadpool.
  - Example defaults: `q: str | None = None`, `skip: int = 0`, `limit: int = 100`.

- **Reusable `Annotated` aliases:** Store `Annotated[...]` in a variable, e.g. `CommonsDep = Annotated[dict, Depends(common_parameters)]`, and reuse it. This is the recommended style (e.g. `SessionDep`, `CurrentUser`). `commons: dict = Depends(common_parameters)` also works; `Annotated` keeps the type and works better with editors and direct function calls.

- **Classes as dependencies:** A class is callable; calling it runs `__init__`, and FastAPI provides the instance. For `CommonQueryParams`, `q`, `skip`, and `limit` have the same defaults above. The type in `Annotated[...]` is for the editor; FastAPI uses `Depends`’ argument, so `Annotated[Any, Depends(CommonQueryParams)]` works too. Pydantic models and dataclasses also work as class dependencies.
  - **`Depends()` shortcut:** If the dependency is the annotated class, use `Annotated[CommonQueryParams, Depends()]`. With no dependency argument, FastAPI uses the annotated type (`dataclasses.replace(depends, dependency=type_annotation)` in `fastapi/dependencies/utils.py`).

- **Sub-dependencies:** Dependencies can depend on other dependencies to any depth. FastAPI resolves `query_extractor` first, then `query_or_cookie_extractor` (also reading `last_query` with `Cookie()`), then the endpoint.

- **Per-request caching (`use_cache`):** Repeated use of a dependency in one request calls it once and reuses the value. The cache key combines the dependency callable, effective security scopes, and dependency scope; the same callable with different OAuth2 scopes is evaluated separately. Set `use_cache=False` to force a fresh call every time. Cache lasts one request; use something like `functools.lru_cache` for cross-request caching.

- **Where dependencies can be declared:** Parameters inject the value; `dependencies=[...]` in decorators, routers, or the whole app discards it. Other options: `yield` for setup/teardown, configured callable instances, and WebSocket endpoints. Dependencies may receive `Request`, `Response`, `BackgroundTasks`, `WebSocket`, and `SecurityScopes`.

- **Related:** Security Basics (`get_current_user` sub-dependency chain); Testing Dependencies (`app.dependency_overrides`); How FastAPI Handles a Request.
