---
type: tutorial
title: SQL DATABASES WITH SQLModel
description: CONNECT FastAPI TO SQL DATABASE VIA SQLModel: engine, PER-REQUEST SESSION DEPENDENCY WITH yield, table CREATION, CRUD ENDPOINTS, AND HeroBase/Hero/HeroPublic/HeroCreate/HeroUpdate MULTIPLE-MODEL PATTERN WITH PATCH UPDATES.
tags: [database, SQL, SQLModel, SQLAlchemy, session, CRUD, SQLite, PostgreSQL]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-ce488c1d921d5f2531ab24a4
    resource: repo://docs_src/sql_databases/tutorial002_an_py310.py
  - id: openwiki-source-0a37e890afc7a8dceed367e9
    resource: repo://docs/en/docs/tutorial/SQL-databases.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: SQL DATABASES WITH SQLModel

FastAPI REQUIRES NO PARTICULAR DATABASE. DOCS USE **SQLModel** — BUILT ON SQLAlchemy AND PYDANTIC BY FastAPI'S AUTHOR — SO MODELS WORK AS DATABASE TABLES AND FastAPI REQUEST/RESPONSE MODELS. SQLAlchemy UNDERLIES IT; THEREFORE, ANY SQLAlchemy-SUPPORTED DATABASE WORKS: PostgreSQL, MySQL, SQLite, ORACLE, SQL SERVER, …

EXAMPLE USES SQLite (SINGLE FILE, NO SERVER). PRODUCTION TYPICALLY USES PostgreSQL; [FULL STACK FastAPI TEMPLATE](../about/features-and-ecosystem.md) SHOWS COMPLETE SETUP.

```bash
uv add sqlmodel
```

H2: BUILDING BLOCKS

FROM `docs_src/sql_databases/tutorial002_an_py310.py`:

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

- **engine**: HOLDS DATABASE CONNECTIONS. CREATE **ONE** FOR WHOLE APP.
- `check_same_thread=False` (SQLite ONLY): ONE REQUEST MAY USE >1 THREAD (e.g. `def` DEPENDENCIES RUN IN THREADPOOL); SQLite FORBIDS THIS BY DEFAULT. ONE SESSION PER REQUEST KEEPS THIS SAFE.
- `SQLModel.metadata.create_all(engine)` CREATES TABLES FOR ALL *table MODELS*.
- **SESSION**: TRACKS OBJECTS IN MEMORY AND TALKS TO DB THROUGH engine. `yield` DEPENDENCY PROVIDES **ONE NEW SESSION PER REQUEST** AND CLOSES IT AFTERWARDS (SEE [DEPENDENCIES WITH yield](../dependencies/dependencies-with-yield.md)). `SessionDep` IS REUSABLE `Annotated` ALIAS.

CREATE TABLES AT STARTUP:

```python
app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
```

(TUTORIAL USES OLDER STARTUP EVENT; `lifespan` IS RECOMMENDED MECHANISM — SEE [lifespan EVENTS](../app-structure/lifespan-events.md).) IN PRODUCTION, RUN MIGRATIONS (e.g. **ALEMBIC**) IN A STEP BEFORE STARTING APP INSTEAD.

H2: MULTIPLE MODELS

ONE table MODEL FOR INPUT AND OUTPUT WOULD LET CLIENTS SET `id` AND LEAK PRIVATE COLUMNS. SPLIT INTO SEVERAL MODELS (`tutorial002`):

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
| `HeroBase` | DATA MODEL | SHARED FIELDS |
| `Hero` | **table MODEL** (`table=True`) | DB table; HAS `id` (PRIMARY KEY) AND `secret_name` |
| `HeroPublic` | DATA MODEL | RETURNED TO CLIENTS: `id` REQUIRED (ALWAYS SET AFTER SAVING); `secret_name` OMITTED |
| `HeroCreate` | DATA MODEL | INPUT FOR CREATION: NO `id`; INCLUDES `secret_name` |
| `HeroUpdate` | DATA MODEL | INPUT FOR PARTIAL UPDATES: EVERY Field OPTIONAL |

Field DETAILS: `table=True` MAKES IT A table; `Field(primary_key=True)` MARKS PRIMARY KEY (TYPED `int | None` SO OBJECTS CAN BE CREATED BEFORE DB ASSIGNS `id`); `Field(index=True)` CREATES index. `str` MAPS TO `TEXT`/`VARCHAR`.

H2: CRUD ENDPOINTS

H3: CREATE

```python
@app.post("/heroes/", response_model=HeroPublic)
def create_hero(hero: HeroCreate, session: SessionDep):
    db_hero = Hero.model_validate(hero)
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    return db_hero
```

`Hero.model_validate(hero)` BUILDS table OBJECT FROM INPUT; `response_model=HeroPublic` FILTERS RETURNED `Hero`, SO `secret_name` NEVER LEAVES API (SEE [RESPONSE MODELS](../models/response-model.md)).

H3: READ MANY, WITH PAGINATION

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

`Query(le=100)` CAPS PAGE SIZE.

H3: READ ONE

```python
@app.get("/heroes/{hero_id}", response_model=HeroPublic)
def read_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero
```

H3: PARTIAL UPDATE WITH PATCH

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

`model_dump(exclude_unset=True)` CONTAINS ONLY FIELDS CLIENT ACTUALLY SENT, SO OMITTED FIELDS AREN'T OVERWRITTEN WITH DEFAULTS; `sqlmodel_update()` APPLIES THEM. SEE [EXTRA MODELS, jsonable_encoder AND BODY UPDATES](../models/extra-models-and-updates.md).

H3: DELETE

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
H2: SINGLE-MODEL VERSION
`tutorial001_an_py310.py` USES ONE `Hero` table MODEL FOR EVERYTHING ∧ RETURN TYPE ANNOTATIONS (`-> Hero`, `-> list[Hero]`). SIMPLER, BUT EXPOSES `secret_name` ∧ LETS CLIENTS SEND `id`; USE ONLY TO START.

====

H2: NOTES
- ENDPOINTS ARE PLAIN `def` BECAUSE SQLModel/SQLAlchemy SESSIONS HERE ARE SYNCHRONOUS; FastAPI RUNS THEM IN THE THREADPOOL (SEE [PYTHON TYPES AND ASYNC/AWAIT](../getting-started/python-types-and-async.md)).
- TO TEST WITH A SEPARATE DATABASE, OVERRIDE `get_session` VIA `app.dependency_overrides` (SEE [ASYNC TESTS AND TESTING DATABASES](../testing/async-tests-and-database-testing.md)).
- CLOSING A SESSION EARLY DURING LONG STREAMING RESPONSES IS COVERED IN [ADVANCED DEPENDENCIES](../dependencies/advanced-dependencies.md).
