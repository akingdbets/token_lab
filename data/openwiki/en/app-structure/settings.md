---
type: guide
title: Settings and Environment Variables
description: Load typed application configuration from environment variables and .env files with pydantic-settings BaseSettings, expose it through a cached get_settings dependency, and override it in tests.
tags: [settings, configuration, pydantic-settings, basesettings, env, lru_cache, dependency_overrides]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-188e99702cd491f53e3e07ce
    resource: repo://docs_src/settings/app02_an_py310/main.py
  - id: openwiki-source-cebb973f623815ed295b6cf7
    resource: repo://docs_src/settings/app02_an_py310/test_main.py
  - id: openwiki-source-1e385c4545f62f58e5fa9ba0
    resource: repo://docs_src/settings/app03_an_py310/config.py
  - id: openwiki-source-a1d76c3802220e582db0d953
    resource: repo://docs_src/settings/tutorial001_py310.py
  - id: openwiki-source-dd96f06e91bf8d1fb494d27b
    resource: repo://docs/en/docs/advanced/settings.md
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Settings and Environment Variables

Configuration such as secrets, database URLs or feature flags usually comes from **environment variables**. Environment variables are always strings; Pydantic's `BaseSettings` reads them, converts them to the declared types and validates them.

`BaseSettings` lives in the separate `pydantic-settings` package (included in `fastapi[standard]`, or install `pydantic-settings` yourself). For environment-variable basics see [Development Workflow](../getting-started/development-workflow.md).

## Define a `Settings` class

`docs_src/settings/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50


settings = Settings()
app = FastAPI()


@app.get("/info")
async def info():
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }
```

- Each attribute is read from an environment variable with the same name, case-insensitively (`APP_NAME` → `app_name`).
- Defaults apply when the variable is missing; fields without defaults (`admin_email`) are **required** — `Settings()` raises a validation error if they are not set.
- Values are converted: `ITEMS_PER_USER=100` becomes the `int` `100`. You can use `Field()` validation just like normal Pydantic models.

Run with variables set:

```bash
ADMIN_EMAIL="deadpool@example.com" APP_NAME="ChimichangApp" fastapi run main.py
```

In PowerShell set `$Env:ADMIN_EMAIL = "..."` before running. `items_per_user` keeps its default `50`.

## Settings in a separate module

Put the class (and optionally a module-level instance) in `config.py` and import it (`docs_src/settings/app01_py310/`):

```python
# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50


settings = Settings()
```

```python
# main.py
from fastapi import FastAPI

from .config import settings

app = FastAPI()
```

## Settings as a dependency (recommended)

A global instance is created at import time and is awkward to change in tests. Instead, provide settings through a dependency (`docs_src/settings/app02_an_py310/main.py`):

```python
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI

from .config import Settings

app = FastAPI()


@lru_cache
def get_settings():
    return Settings()


@app.get("/info")
async def info(settings: Annotated[Settings, Depends(get_settings)]):
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }
```

### Why `@lru_cache`

`Settings()` reads the environment (and possibly a file) every time it is created. `functools.lru_cache` makes `get_settings()` return the **same object** after the first call, so settings are built once, lazily, on the first request that needs them. Because `get_settings` takes no arguments there is only one cache entry. (FastAPI's own per-request dependency cache would only deduplicate within a single request.)

## Overriding settings in tests

Since `get_settings` is a dependency, tests can replace it with `app.dependency_overrides` (`docs_src/settings/app02_an_py310/test_main.py`):

```python
from fastapi.testclient import TestClient

from .config import Settings
from .main import app, get_settings

client = TestClient(app)


def get_settings_override():
    return Settings(admin_email="testing_admin@example.com")


app.dependency_overrides[get_settings] = get_settings_override


def test_app():
    response = client.get("/info")
    data = response.json()
    assert data == {
        "app_name": "Awesome API",
        "admin_email": "testing_admin@example.com",
        "items_per_user": 50,
    }
```

Values passed to the constructor take priority over environment variables. More in [Testing Dependencies](../testing/testing-dependencies-events-websockets.md).

## Reading a `.env` file

Configure `model_config` with `SettingsConfigDict(env_file=".env")` (`docs_src/settings/app03_an_py310/config.py`):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50

    model_config = SettingsConfigDict(env_file=".env")
```

```bash
# .env
ADMIN_EMAIL="deadpool@example.com"
APP_NAME="ChimichangApp"
```

Real environment variables still take precedence over the `.env` file. The docs recommend adding `python-dotenv` to your project (`uv add python-dotenv`) for dotenv support. Combined with `@lru_cache` on `get_settings`, the file is read only once instead of on every request. Do not commit `.env` files containing secrets.

## Related

- [Lifespan Events](lifespan-events.md) — use settings to configure startup resources
- [Conditional OpenAPI](../openapi/metadata-and-docs-ui.md) — e.g. disabling docs via an `openapi_url` setting
