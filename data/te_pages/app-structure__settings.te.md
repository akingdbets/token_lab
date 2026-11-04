---
type: guide
title: Settings and Environment Variables
description: Load typed application configuration from environment variables and .env files with pydantic-settings BaseSettings, expose it through a cached get_settings dependency, and override it in tests.
tags: [settings, configuration, pydantic-settings, BaseSettings, Env, lru_cache, dependency_overrides]
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

H1: Settings and Environment Variables

CONFIGURATION (e.g., SECRETS, DATABASE URLs, FEATURE FLAGS) USUALLY COMES FROM
**ENVIRONMENT VARIABLES**.
ENVIRONMENT VARIABLES ARE ALWAYS STRINGS; `BaseSettings` READS, CONVERTS TO
DECLARED TYPES, AND VALIDATES THEM.

`BaseSettings` LIVES IN SEPARATE `pydantic-settings` PACKAGE (INCLUDED IN
`fastapi[standard]`; OR INSTALL `pydantic-settings` YOURSELF).
ENVIRONMENT-VARIABLE BASICS: [DEVELOPMENT WORKFLOW](../getting-started/development-workflow.md).

H2: Define a `Settings` class

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

- EACH ATTRIBUTE READS ENVIRONMENT VARIABLE WITH SAME NAME, CASE-INSENSITIVELY
  (`APP_NAME` → `app_name`).
- DEFAULTS APPLY IF VARIABLE MISSING; FIELDS WITHOUT DEFAULTS (`admin_email`)
  ARE **REQUIRED**; `Settings()` RAISES VALIDATION ERROR IF THEY ARE NOT SET.
- VALUES CONVERT: `ITEMS_PER_USER=100` BECOMES `int` `100`.
  `Field()` VALIDATION WORKS AS IN NORMAL pydantic MODELS.

RUN WITH VARIABLES SET:

```bash
ADMIN_EMAIL="deadpool@example.com" APP_NAME="ChimichangApp" fastapi run main.py
```

IN PowerShell, SET `$Env:ADMIN_EMAIL = "..."` BEFORE RUNNING.
`items_per_user` KEEPS DEFAULT `50`.

H2: Settings in a separate module

PUT CLASS (AND OPTIONALLY MODULE-LEVEL INSTANCE) IN `config.py` AND IMPORT IT
(`docs_src/settings/app01_py310/`):

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

H2: Settings as a dependency (recommended)

GLOBAL INSTANCE CREATED AT IMPORT TIME; AWKWARD TO CHANGE IN TESTS.
INSTEAD, PROVIDE SETTINGS THROUGH DEPENDENCY
(`docs_src/settings/app02_an_py310/main.py`):

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

H3: Why `@lru_cache`

`Settings()` READS ENVIRONMENT (AND POSSIBLY A FILE) EACH TIME IT IS CREATED.
`functools.lru_cache` MAKES `get_settings()` RETURN **SAME OBJECT** AFTER FIRST
CALL; SETTINGS ARE BUILT ONCE, LAZILY, ON FIRST REQUEST THAT NEEDS THEM.
`get_settings` TAKES NO ARGUMENTS; THEREFORE, ONE CACHE ENTRY.
FASTAPI'S PER-REQUEST DEPENDENCY CACHE ONLY DEDUPLICATES WITHIN ONE REQUEST.

H2: Overriding settings in tests

`get_settings` IS A DEPENDENCY; TESTS CAN REPLACE IT WITH
`app.dependency_overrides` (`docs_src/settings/app02_an_py310/test_main.py`):

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

CONSTRUCTOR VALUES TAKE PRIORITY OVER ENVIRONMENT VARIABLES.
MORE: [TESTING DEPENDENCIES](../testing/testing-dependencies-events-websockets.md).

H2: Reading a `.env` file

CONFIGURE `model_config` WITH `SettingsConfigDict(env_file=".env")`
(`docs_src/settings/app03_an_py310/config.py`):

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

REAL ENVIRONMENT VARIABLES STILL TAKE PRECEDENCE OVER `.env` FILE.
DOCS RECOMMEND ADDING `python-dotenv` TO PROJECT
(`uv add python-dotenv`) FOR dotenv SUPPORT.
WITH `@lru_cache` ON `get_settings`, FILE IS READ ONCE, NOT EACH REQUEST.
DO NOT COMMIT `.env` FILES CONTAINING SECRETS.

H2: Related

- [LIFESPAN EVENTS](lifespan-events.md) — USE SETTINGS TO CONFIGURE STARTUP RESOURCES
- [CONDITIONAL OpenAPI](../OpenAPI/metadata-and-docs-ui.md) — e.g., DISABLE DOCS
  VIA AN `openapi_url` SETTING
