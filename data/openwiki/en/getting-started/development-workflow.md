---
type: guide
title: "Development Workflow: Virtual Environments, Environment Variables and Debugging"
description: Set up an isolated FastAPI project with uv, use environment variables for configuration, and debug your app in VS Code or PyCharm by running Uvicorn from your code.
tags: [development, uv, virtual-environment, environment-variables, debugging, uvicorn, vscode, pycharm]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-a63798837acc79e7e4562614
    resource: repo://docs_src/debugging/tutorial001_py310.py
  - id: openwiki-source-2a4258075d06ec0b26b7e5f9
    resource: repo://docs/en/docs/environment-variables.md
  - id: openwiki-source-9bc15a21c009b14775a3dd72
    resource: repo://docs/en/docs/fastapi-cli.md
  - id: openwiki-source-d8b088114289e51e24813c52
    resource: repo://docs/en/docs/tutorial/debugging.md
  - id: openwiki-source-7ee7d971f429ba15850f3e46
    resource: repo://docs/en/docs/virtual-environments.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Development Workflow: Virtual Environments, Environment Variables and Debugging

## Virtual environments with `uv`

Each Python project should have its own **virtual environment** so its packages don't conflict with other projects. The FastAPI docs recommend **uv** to manage the project, its dependencies and its environment:

```bash
uv init awesome-project --bare
cd awesome-project
uv add "fastapi[standard]"
```

- `uv` creates the virtual environment automatically — no manual creation or activation needed.
- Dependencies are declared in `pyproject.toml` and locked in `uv.lock`.
- Run commands inside the environment with `uv run`:

```bash
uv run fastapi dev
```

Quote `"fastapi[standard]"` so the brackets work in every shell. The classic alternative (`python -m venv .venv`, activate, `pip install "fastapi[standard]"`) still works; see the linked Virtual Environments guide in the docs. For which extras `standard` installs, see [Features, Alternatives and Ecosystem](../about/features-and-ecosystem.md).

## Environment variables

An **environment variable** lives in the operating system, outside your code, and can be read by your app. FastAPI apps commonly use them for configuration: database URLs, email credentials, secret keys.

```bash
# Bash: set for a single command
MY_NAME="Wade Wilson" uv run python main.py
```

```powershell
# PowerShell
$Env:MY_NAME = "Wade Wilson"
uv run python main.py
```

```python
import os

name = os.getenv("MY_NAME", "World")
```

Values are always strings. For typed, validated configuration use Pydantic's `BaseSettings` — see [Settings and Environment Variables](../app-structure/settings.md). Two environment variables matter to FastAPI tooling itself:

- `FASTAPI_ENV` — `fastapi dev` sets it to `development` if unset; `app.frontend(check_dir="auto")` uses it (see [Static Files, Templates and Frontends](../app-structure/static-files-templates-and-frontend.md)). `fastapi run` leaves it unchanged.
- `PATH` — determines which `python`/`fastapi` executable runs; `uv run` takes care of it for you.

## Debugging

To use your editor's debugger (breakpoints, stepping), start Uvicorn from your own code (`docs_src/debugging/tutorial001_py310.py`):

```python
import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    a = "a"
    b = "b" + a
    return {"hello world": b}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

`if __name__ == "__main__":` runs only when the file is executed directly (`uv run python myapp.py`), not when it's imported (`from myapp import app`) by the `fastapi` CLI, a test or another module.

Then start the file from the debugger:

- **VS Code**: Debug panel → "Add configuration…" → Python → run "Python: Current File (Integrated Terminal)".
- **PyCharm**: Run menu → "Debug…" → choose the file (e.g. `main.py`).

The server starts with your code and stops at your breakpoints.

For day-to-day development without a debugger, `fastapi dev` (auto-reload) is the usual choice; see [First Steps and the FastAPI CLI](first-steps.md).

## Related

- [Testing with TestClient](../testing/testing-basics.md)
- [Deployment Concepts](../deployment/deployment-concepts-and-servers.md)
