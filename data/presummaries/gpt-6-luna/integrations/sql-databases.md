- **SQL Databases with SQLModel**
  - FastAPI does not require a particular database. SQLModel is built on SQLAlchemy and Pydantic; models can be database tables and FastAPI request/response models. Any SQLAlchemy-supported database works, including PostgreSQL, MySQL, SQLite, Oracle, and SQL Server.
  - Example uses SQLite (one file, no server); production typically uses PostgreSQL. Install with `uv add sqlmodel`.

- **Building blocks**
  - Imports include `Annotated`, `Depends`, `FastAPI`, `HTTPException`, `Query`, `Field`, `Session`, `SQLModel`, `create_engine`, `select`.
  - `sqlite_file_name = "database.db"`; `sqlite_url = f"sqlite:///{sqlite_file_name}"`; `connect_args = {"check_same_thread": False}`; `engine = create_engine(sqlite_url, connect_args=connect_args)`.
  - Create one engine for the app. `check_same_thread=False` is SQLite-only: a request may use multiple threads (e.g. `def` dependencies run in the threadpool), while SQLite forbids this by default; one session per request keeps it safe.
  - `SQLModel.metadata.create_all(engine)` creates tables for all table models. `Session` tracks objects and accesses the DB through the engine. `get_session()` yields one new `Session(engine)` per request and closes it afterward; `SessionDep = Annotated[Session, Depends(get_session)]`.
  - `@app.on_event("startup")` calls `create_db_and_tables()`. This is the older tutorial approach; `lifespan` is recommended. In production, run migrations (e.g. Alembic) before starting the app.

- **Multiple models**
  - `HeroBase`: `name: str = Field(index=True)`, `age: int | None = Field(default=None, index=True)`.
  - `Hero(HeroBase, table=True)`: `id: int | None = Field(default=None, primary_key=True)`, `secret_name: str`.
  - `HeroPublic(HeroBase)` has required `id`, omits `secret_name`; `HeroCreate(HeroBase)` has `secret_name`, no `id`; `HeroUpdate(HeroBase)` makes `name`, `age`, and `secret_name` optional (`= None`).
  - Split models so clients cannot set `id` or receive private columns. `table=True` makes a table; `Field(primary_key=True)` marks the primary key (nullable typing permits creation before DB assigns it); `Field(index=True)` creates an index. `str` maps to `TEXT`/`VARCHAR`.

- **CRUD endpoints**
  - Create: `POST /heroes/`, `response_model=HeroPublic`; `Hero.model_validate(hero)`, then `session.add`, `commit`, `refresh`. The response model filters `secret_name`.
  - Read many: `GET /heroes/`, `response_model=list[HeroPublic]`; `offset: int = 0`, `limit: Annotated[int, Query(le=100)] = 100`; `Query(le=100)` caps page size.
  - Read one: `GET /heroes/{hero_id}`; `session.get(Hero, hero_id)`. Missing hero raises `HTTPException(status_code=404, detail="Hero not found")`.
  - PATCH ` /heroes/{hero_id}` (path is `/heroes/{hero_id}`): missing hero raises the same 404. `hero.model_dump(exclude_unset=True)` includes only sent fields, preventing omitted fields being overwritten; `sqlmodel_update()` applies them, then add/commit/refresh.
  - Delete: `DELETE /heroes/{hero_id}`; missing hero raises the same 404; otherwise delete and commit, return `{"ok": True}`.

- **Single-model version and notes**
  - `tutorial001_an_py310.py` uses one `Hero` table model and return annotations `-> Hero`, `-> list[Hero]`; simpler, but exposes `secret_name` and allows clients to send `id`—use only to start.
  - Endpoints use plain `def` because sessions are synchronous; FastAPI runs them in the threadpool. For a separate test database, override `get_session` via `app.dependency_overrides`. Explicitly closing a session early during long streaming responses is covered under Advanced Dependencies.
