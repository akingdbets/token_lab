## Virtual environments with `uv`
- Each Python project should have its own virtual environment to prevent package conflicts. FastAPI docs recommend `uv`:
  ```bash
  uv init awesome-project --bare
  cd awesome-project
  uv add "fastapi[standard]"
  ```
- `uv` creates the environment automatically; manual creation or activation is unnecessary. Dependencies go in `pyproject.toml` and are locked in `uv.lock`. Run commands with `uv run`, e.g. `uv run fastapi dev`.
- Quote `"fastapi[standard]"` so brackets work in every shell. The alternative `python -m venv .venv`, activate, and `pip install "fastapi[standard]"` still works. See the Virtual Environments guide and [Features, Alternatives and Ecosystem](../about/features-and-ecosystem.md) for `standard` extras.

## Environment variables
- Variables live in the operating system outside code; apps commonly use them for database URLs, email credentials, and secret keys. Values are always strings. Examples:
  ```bash
  MY_NAME="Wade Wilson" uv run python main.py
  ```
  ```powershell
  $Env:MY_NAME = "Wade Wilson"
  uv run python main.py
  ```
  ```python
  name = os.getenv("MY_NAME", "World")
  ```
- For typed, validated configuration, use Pydantic's `BaseSettings` ([Settings and Environment Variables](../app-structure/settings.md)).
- `FASTAPI_ENV`: `fastapi dev` sets it to `development` if unset; `app.frontend(check_dir="auto")` uses it. `fastapi run` leaves it unchanged.
- `PATH` determines which `python`/`fastapi` executable runs; `uv run` handles it.

## Debugging
- To use editor breakpoints and stepping, start Uvicorn from your code (`docs_src/debugging/tutorial001_py310.py`), with `uvicorn.run(app, host="0.0.0.0", port=8000)`. `if __name__ == "__main__":` runs when executed directly (`uv run python myapp.py`), not when imported by the `fastapi` CLI, a test, or another module.
- VS Code: Debug panel → “Add configuration…” → Python → “Python: Current File (Integrated Terminal)”. PyCharm: Run → “Debug…” → choose the file. The server stops at breakpoints.
- For daily development without a debugger, use `fastapi dev` (auto-reload); see [First Steps and the FastAPI CLI](first-steps.md).

## Related
- [Testing with TestClient](../testing/testing-basics.md); [Deployment Concepts](../deployment/deployment-concepts-and-servers.md).
