## The `Depends` options
- `fastapi.params.Depends` is a small frozen dataclass:
  - `dependency=None`: callable; with `Annotated[SomeClass, Depends()]`, the annotated type is used if omitted.
  - `use_cache=True`: reuse a dependency value if needed more than once per request; `False` calls it every time.
  - `scope=None`: for `yield` dependencies, `"request"` (default) or `"function"`.
- `fastapi.params.Security` subclasses `Depends` and adds `scopes`.

## Parameterized dependencies with callable instances
- Any callable can be a dependency, including a class instance defining `__call__`.
- FastAPI does not inspect `__init__`; you configure the instance yourself. It inspects `__call__` for request parameters and sub-dependencies, then calls the instance per request.
- Use `Depends(checker)`, not `Depends(FixedContentQueryChecker)`.
- Security utilities use configured callable instances, e.g. `OAuth2PasswordBearer(tokenUrl="token")`, `HTTPBasic()`, `APIKeyHeader(name=...)`.

## Dependency `scope` for `yield` dependencies
- Since FastAPI 0.121.0, `Depends(scope=...)` is supported: `"request"` (default) runs exit code after the response is sent; `"function"` runs it after the path operation returns, before the response is sent.
- FastAPI keeps separate request- and function-scope exit stacks and pushes each generator dependency onto its matching stack.
- A request-scope `yield` dependency cannot depend on a `"function"`-scope sub-dependency; FastAPI raises `DependencyScopeError` at route setup.

## How exit-code timing evolved
- `< 0.106.0`: exit code ran after response and background tasks; tasks could reuse yielded objects, but post-`yield` exceptions could not reach handlers.
- `0.106.0`: exit code moved before response sending. Background tasks should create their own resources (e.g. a new DB session) and receive an object **ID**, not an ORM object.
- `0.110.0`: caught exceptions not re-raised in `yield` dependencies are no longer forwarded automatically; use `raise` to propagate.
- `0.118.0`: exit code again runs after response sending, allowing `StreamingResponse` to use a yielded DB session while streaming.
- `0.121.0`: added `Depends(scope="function")` for early exit.

### Releasing a resource early by hand
- Default request scope keeps a yielded session open until a slow `StreamingResponse` finishes, even if only an auth dependency used it. Explicitly call `session.close()` when done; the example does this after `session.get`, raising `HTTPException(status_code=403, detail="Not authorized")` if no user is found.

## Related
- Testing Dependencies (`app.dependency_overrides`), Background Tasks, and How FastAPI Handles a Request.
