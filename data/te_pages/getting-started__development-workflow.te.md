---
type: guide
title: "development Workflow: Virtual Environments, Environment Variables and debugging"
description: Set up an isolated FastAPI project with uv, use environment variables for configuration, and debug your app in VS Code or PyCharm by running Uvicorn from your code.
tags: [development, uv, virtual-environment, environment-variables, debugging, uvicorn, vscode, PyCharm]
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

H1: development Workflow: Virtual Environments, Environment Variables and debugging

H2: Virtual environments with `uv`

EACH python PROJECT NEEDS ITS OWN VIRTUAL ENVIRONMENT;
PREVENTS PACKAGE CONFLICTS WITH OTHER PROJECTS.
FASTAPI DOCS RECOMMEND `uv` TO MANAGE PROJECT, DEPENDENCIES, ENVIRONMENT:

```bash
uv init awesome-project --bare
cd awesome-project
uv add "fastapi[standard]"
```

- `uv` CREATES VIRTUAL ENVIRONMENT AUTOMATICALLY; NO MANUAL CREATION OR ACTIVATION.
- DECLARE DEPENDENCIES IN `pyproject.toml`; LOCK IN `uv.lock`.
- run COMMANDS INSIDE ENVIRONMENT WITH `uv run`:

```bash
uv run fastapi dev
```

QUOTE `"fastapi[standard]"` SO BRACKETS WORK IN EVERY SHELL.
CLASSIC ALTERNATIVE (`python -m venv .venv`, ACTIVATE,
`pip install "fastapi[standard]"`) STILL WORKS;
SEE LINKED VIRTUAL ENVIRONMENTS GUIDE IN DOCS.
SEE [Features, Alternatives and Ecosystem](../about/features-and-ecosystem.md)
FOR EXTRAS INSTALLED BY `standard`.

H2: Environment variables

ENVIRONMENT VARIABLE LIVES IN OPERATING SYSTEM, OUTSIDE CODE;
app CAN READ IT.
FASTAPI APPS COMMONLY USE THEM FOR CONFIGURATION:
DATABASE URLs, EMAIL CREDENTIALS, SECRET KEYS.

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

VALUES ALWAYS STRINGS.
FOR TYPED, VALIDATED CONFIGURATION, USE PYDANTIC'S `BaseSettings`;
SEE [Settings and Environment Variables](../app-structure/settings.md).
TWO ENVIRONMENT VARIABLES AFFECT FASTAPI TOOLING ITSELF:

- `FASTAPI_ENV` — `fastapi dev` SETS IT TO `development` if UNSET;
  `app.frontend(check_dir="auto")` USES IT
  (SEE [Static Files, Templates and Frontends](../app-structure/static-files-templates-and-frontend.md)).
  `fastapi run` LEAVES IT UNCHANGED.
- `PATH` — DETERMINES WHICH `python`/`fastapi` EXECUTABLE RUNS;
  `uv run` HANDLES THIS FOR YOU.

H2: debugging

TO USE EDITOR DEBUGGER (BREAKPOINTS, STEPPING), START UVICORN from YOUR CODE
(`docs_src/debugging/tutorial001_py310.py`):

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

`if __name__ == "__main__":` RUNS ONLY WHEN FILE EXECUTED DIRECTLY
(`uv run python myapp.py`);
NOT WHEN IMPORTED (`from myapp import app`) BY `fastapi` CLI, A TEST,
OR ANOTHER MODULE.

THEN START FILE from DEBUGGER:

- **VS Code**: DEBUG PANEL → "Add configuration…" → python →
  run "python: Current File (Integrated Terminal)".
- **PyCharm**: run MENU → "Debug…" → CHOOSE FILE (e.g. `main.py`).

SERVER STARTS WITH YOUR CODE; STOPS AT YOUR BREAKPOINTS.

FOR DAY-TO-DAY development WITHOUT DEBUGGER, `fastapi dev`
(auto-RELOAD) IS USUAL CHOICE;
SEE [First Steps and the FastAPI CLI](first-steps.md).

H2: Related

- [Testing with TestClient](../testing/testing-basics.md)
- [Deployment Concepts](../deployment/deployment-concepts-and-servers.md)
