- **Settings and Environment Variables**
  - Environment variables (for secrets, database URLs, feature flags, etc.) are strings. `BaseSettings` converts them to declared types and validates them.
  - `BaseSettings` is in the separate `pydantic-settings` package, included in `fastapi[standard]`; alternatively install `pydantic-settings`.

- **Define a `Settings` class**
  - Attributes read same-named environment variables case-insensitively (`APP_NAME` → `app_name`). Defaults apply when variables are missing; fields without defaults, such as `admin_email`, are required, and `Settings()` raises a validation error if they are unset.
  - Values are converted (for example, `ITEMS_PER_USER=100` becomes `int` `100`); `Field()` validation works as in normal Pydantic models.
  - Example defaults: `app_name: str = "Awesome API"` and `items_per_user: int = 50`. `ADMIN_EMAIL="deadpool@example.com" APP_NAME="ChimichangApp" fastapi run main.py`; PowerShell uses `$Env:ADMIN_EMAIL = "..."`. Unset `items_per_user` remains `50`.
  - The class and optionally a module-level `settings = Settings()` instance can live in `config.py`, then be imported by `main.py`.

- **Settings as a dependency (recommended)**
  - Use `@lru_cache` on `get_settings()` returning `Settings()`, then inject with `Annotated[Settings, Depends(get_settings)]`.
  - `Settings()` reads the environment and possibly a file on each creation. `functools.lru_cache` returns the same object after the first call; construction is lazy, on the first request needing it. No-argument `get_settings` has one cache entry; FastAPI’s per-request dependency cache only deduplicates within one request.

- **Overriding settings in tests**
  - Replace `get_settings` via `app.dependency_overrides[get_settings] = get_settings_override`. Constructor values take priority over environment variables. Example override: `Settings(admin_email="testing_admin@example.com")`; other defaults remain (`"Awesome API"`, `50`).

- **Reading a `.env` file**
  - Set `model_config = SettingsConfigDict(env_file=".env")`. Real environment variables take precedence over `.env`; docs recommend `uv add python-dotenv`. With `@lru_cache`, the file is read once instead of every request. Do not commit `.env` files containing secrets.

- **Related**
  - Lifespan Events: configure startup resources. Conditional OpenAPI: e.g. disable docs via an `openapi_url` setting.
