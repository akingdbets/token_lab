- **Type hints**
  - Standard Python annotations are optional; editors and tools understand them. FastAPI uses them at runtime to convert, validate, and document data.
  - Simple types: `str`, `int`, `float`, `bool`, `bytes`. Generics include `list[str]`, `tuple[int, int, str]`, `set[bytes]`, and `dict[str, float]` (keys `str`, values `float`). Unions include `int | str`; possibly-`None` types include `str | None`.
  - Where `|` cannot be used, use `typing.Union[str, None]`. The docs prefer `Union[X, None]` to `Optional[X]`: `Optional[str]` without a default is still required, but accepts `None`. A FastAPI parameter is optional because of its default (`= None`), not its type.
  - Classes can be types. Pydantic model instances validate and convert input. FastAPI uses Pydantic (v2) for all request and response data.
  - `typing.Annotated[T, ...]` attaches metadata without changing the type. Python ignores it; FastAPI reads it for parameter sources, validation, and dependencies. `Annotated` is the recommended style. Example: `Annotated[str | None, Query(max_length=50)] = None`.
  - Types provide editor completion and type checks, conversion of incoming strings/JSON to Python types, validation with automatic 422 errors, output-to-JSON conversion, and OpenAPI documentation.

- **`async def` vs `def`**
  - If a library requires `await` (e.g. an async DB driver, `httpx.AsyncClient`), use `async def` and `await`. For blocking libraries without `await` (many DB libraries, file I/O, `requests`), use plain `def`. Use `async def` for quick functions that wait on nothing; if unsure, use plain `def`. You can mix both in path operations and dependencies.
  - `async def` path operations are awaited directly on the event loop; blocking calls inside them block the whole server process for that time, so avoid blocking I/O. Plain `def` path operations run in an external threadpool and are awaited (`run_in_threadpool` in `run_endpoint_function`, `fastapi/routing.py`).
  - The same applies to dependencies and sub-dependencies: `def` dependencies run in the threadpool; `async def` ones are awaited; `def` generator (`yield`) dependencies run enter/exit in threads. FastAPI only decides how to call path operations and dependencies, not your utility functions; call helpers normally or `await` them if they are `async def`.
  - For trivial compute-only endpoints, `async def` is slightly faster than `def` in FastAPI (no thread hop).
  - `fastapi.concurrency` re-exports Starlette's `run_in_threadpool`, `iterate_in_threadpool`, and `run_until_first_complete`; `run_in_threadpool` can call blocking code from your own `async` code.

- **Concurrency vs parallelism**
  - `async` provides concurrency: while a request waits for network, DB, or disk I/O, the server works on others. CPU-bound work (e.g. ML inference) benefits from parallelism via multiple processes/workers or a task queue.
