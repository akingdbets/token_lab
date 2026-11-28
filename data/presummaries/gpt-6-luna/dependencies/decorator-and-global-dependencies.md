## Purpose
- Use `dependencies=[...]` for dependencies needed only for side effects, without adding an unused parameter.

## Path operation decorator
- `dependencies` is a `list` of `Depends(...)` (or `Security(...)`).
- Dependencies run like parameter dependencies: parameters are read, validated, and documented in OpenAPI; sub-dependencies are resolved. They can raise `HTTPException` to stop the request.
- Return values are discarded; a normal dependency can be reused without editor warnings about unused parameters.
- Example: `@app.get("/items/", dependencies=[Depends(verify_token), Depends(verify_key)])`. `verify_token` checks `X-Token` against `"fake-super-secret-token"`; `verify_key` checks `X-Key` against `"fake-super-secret-key"` and returns `x_key`, which is ignored. Each raises `HTTPException(status_code=400, detail=...)` for an invalid header.
- Prefer integrated security utilities over hand-rolled header checks in real apps.

## Router and include_router
- Apply dependencies to a router with `APIRouter(prefix="/items", dependencies=[Depends(get_token_header)])`, or at include time with `app.include_router(admin.router, prefix="/admin", dependencies=[Depends(get_token_header)])`.

## Global dependencies
- `FastAPI(dependencies=[Depends(verify_token), Depends(verify_key)])` applies to every path operation, including operations from included routers; both headers are required.

## Execution order and `yield`
- Lists combine outermost to innermost: app-level; router / `include_router` (outer includes before inner); decorator; function-signature parameter dependencies.
- A dependency is evaluated once and cached per request unless `use_cache=False`; a global `verify_token` reused as a parameter is not called twice.
- Decorator, router, and global dependencies may use `yield`; teardown follows the normal rules for `yield` dependencies.
