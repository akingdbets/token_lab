---
type: tutorial
title: SQL Databases with SQLModel
description: Connect FastAPI to a SQL database with SQLModel — engine, per-request Session dependency with yield, table creation, CRUD endpoints, and the HeroBase/Hero/HeroPublic/HeroCreate/HeroUpdate multiple-model pattern with PATCH updates.
tags: [database, sql, sqlmodel, sqlalchemy, session, crud, sqlite, postgresql]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-ce488c1d921d5f2531ab24a4
    resource: repo://docs_src/sql_databases/tutorial002_an_py310.py
  - id: openwiki-source-0a37e890afc7a8dceed367e9
    resource: repo://docs/en/docs/tutorial/sql-databases.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# SQL Databases with SQLModel

FastAPI doesn't require any particular database. The docs use **SQLModel** — built on SQLAlchemy and Pydantic by FastAPI's author — so models work both as database tables and as FastAPI request/response models. Because it is SQLAlchemy underneath, any SQLAlchemy-supported database works: PostgreSQL, MySQL, SQLite, Oracle, SQL Server, …

The example uses SQLite (a single file, no server). For production you'd typically use PostgreSQL; the [Full Stack FastAPI Template](../about/features-and-ecosystem.md) shows a complete setup.

```bash
uv add sqlmodel
```

## Building blocks

From `docs_src/sql_databases/tutorial002_an_py310.py`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
```

- **Engine**: holds the database connections. Create **one** for the whole app.
- `check_same_thread=False` (SQLite only): one request may use more than one thread (e.g. `def` dependencies run in the threadpool), and SQLite forbids that by default. Using one session per request keeps this safe.
- `SQLModel.metadata.create_all(engine)` creates tables for all *table models*.
- **Session**: tracks objects in memory and talks to the DB through the engine. The `yield` dependency gives **one new session per request** and closes it afterwards (see [Dependencies with yield](../dependencies/dependencies-with-yield.md)). `SessionDep` is a reusable `Annotated` alias.

Create tables at startup:

```python
app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
```

(The tutorial uses the older startup event; `lifespan` is the recommended mechanism — see [Lifespan Events](../app-structure/lifespan-events.md).) In production, run migrations (e.g. **Alembic**) in a step before starting the app instead.

## Multiple models

Using a single table model for input and output would let clients set `id` and would leak private columns. Split into several models (`tutorial002`):

```python
class HeroBase(SQLModel):
    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)


class Hero(HeroBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    secret_name: str


class HeroPublic(HeroBase):
    id: int


class HeroCreate(HeroBase):
    secret_name: str


class HeroUpdate(HeroBase):
    name: str | None = None
    age: int | None = None
    secret_name: str | None = None
```

| Model | Kind | Role |
|-------|------|------|
| `HeroBase` | data model | Shared fields |
| `Hero` | **table model** (`table=True`) | The DB table; has `id` (primary key) and `secret_name` |
| `HeroPublic` | data model | Returned to clients: `id` is required (always set after saving), `secret_name` omitted |
| `HeroCreate` | data model | Input for creation: no `id`, includes `secret_name` |
| `HeroUpdate` | data model | Input for partial updates: every field optional |

Field details: `table=True` makes it a table; `Field(primary_key=True)` marks the primary key (typed `int | None` so you can create objects before the DB assigns the id); `Field(index=True)` creates an index. `str` maps to `TEXT`/`VARCHAR`.

## CRUD endpoints

### Create

```python
@app.post("/heroes/", response_model=HeroPublic)
def create_hero(hero: HeroCreate, session: SessionDep):
    db_hero = Hero.model_validate(hero)
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    return db_hero
```

`Hero.model_validate(hero)` builds a table object from the input; `response_model=HeroPublic` filters the returned `Hero` so `secret_name` never leaves the API (see [Response Models](../models/response-model.md)).

### Read many, with pagination

```python
@app.get("/heroes/", response_model=list[HeroPublic])
def read_heroes(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    heroes = session.exec(select(Hero).offset(offset).limit(limit)).all()
    return heroes
```

`Query(le=100)` caps the page size.

### Read one

```python
@app.get("/heroes/{hero_id}", response_model=HeroPublic)
def read_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero
```

### Partial update with PATCH

```python
@app.patch("/heroes/{hero_id}", response_model=HeroPublic)
def update_hero(hero_id: int, hero: HeroUpdate, session: SessionDep):
    hero_db = session.get(Hero, hero_id)
    if not hero_db:
        raise HTTPException(status_code=404, detail="Hero not found")
    hero_data = hero.model_dump(exclude_unset=True)
    hero_db.sqlmodel_update(hero_data)
    session.add(hero_db)
    session.commit()
    session.refresh(hero_db)
    return hero_db
```

`model_dump(exclude_unset=True)` contains only fields the client actually sent, so omitted fields aren't overwritten with defaults; `sqlmodel_update()` applies them. See [Extra Models, jsonable_encoder and Body Updates](../models/extra-models-and-updates.md).

### Delete

```python
@app.delete("/heroes/{hero_id}")
def delete_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    session.delete(hero)
    session.commit()
    return {"ok": True}
```

## Single-model version

`tutorial001_an_py310.py` uses one `Hero` table model for everything and return type annotations (`-> Hero`, `-> list[Hero]`). It's simpler but exposes `secret_name` and lets clients send `id` — use it only to start.

## Notes

- The endpoints are plain `def` because SQLModel/SQLAlchemy sessions here are synchronous; FastAPI runs them in the threadpool (see [Python Types and async/await](../getting-started/python-types-and-async.md)).
- For testing with a separate database, override `get_session` via `app.dependency_overrides` — see [Async Tests and Testing Databases](../testing/async-tests-and-database-testing.md).
- Explicitly closing a session early during long streaming responses is covered in [Advanced Dependencies](../dependencies/advanced-dependencies.md).
