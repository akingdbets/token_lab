- **Dependencies with `yield`**
  - Code before `yield` runs before the path operation; code after it runs as cleanup. Use for resources such as database sessions and connections. Use `yield` exactly once per dependency.
  - FastAPI internally uses `asynccontextmanager` for `async def` generators and runs `contextmanager` for `def` generators in a threadpool.
- **Basic example**
  - Setup runs before the request; the yielded value is injected into the path operation or another dependency. `finally` ensures cleanup runs even if an exception occurs.
  - SQLModel pattern: `def get_session(): with Session(engine) as session: yield session`; `SessionDep = Annotated[Session, Depends(get_session)]`.
- **Sub-dependencies with `yield`**
  - Any number can depend on one another. Setup runs in dependency order (`a → b → c`); teardown runs in reverse (`c → b → a`), allowing cleanup code to use sub-dependencies. `yield` and `return` dependencies can be mixed.
- **Exceptions and yield**
  - Exceptions from the path operation or later dependencies are thrown into the generator at `yield`, where `try/except` can catch them. Catching `OwnerError` and raising `HTTPException(status_code=400, detail=...)` is one way to convert it; you can also raise `HTTPException` in exit code or register a custom exception handler.
  - Always re-raise caught exceptions (for example, with bare `raise`) unless intentionally converting them. Swallowing an `InternalError` still gives the client `500 Internal Server Error`, but logs nothing about the real error; re-raising logs its traceback. `HTTPException`s from the path operation also pass through `except`; re-raise them or catch only specific types.
- **Execution order**
  1. Dependencies run up to `yield`.
  2. The path operation runs.
  3. A response is produced from its return value or an exception handler.
  4. Exit code runs before or after sending, depending on `scope`.
  - Only one response is sent; it cannot be changed afterward. An `HTTPException` in exit code after a request-scoped response cannot alter what the client received.
- **Early exit with `scope`**
  - `Depends()` accepts `scope`. `"request"` is the default for `yield` dependencies: teardown runs after the response is sent, so `StreamingResponse` can use the resource while streaming. `"function"` runs teardown after the path operation returns, before sending the response.
  - A `"request"`-scoped dependency may depend only on `"request"`-scoped dependencies; a `"function"`-scoped dependency may depend on either. Violations raise `DependencyScopeError` when the route is created.
- **Using context managers**
  - Use context managers inside a `yield` dependency with `with` / `async with`. Do not decorate the dependency with `@contextlib.contextmanager` or `@asynccontextmanager`; FastAPI does this internally.
- **Background tasks**
  - They run after the response is sent. Don’t rely on yielded resources (such as a DB session) in a task; create a fresh resource there and pass IDs instead of ORM objects.
