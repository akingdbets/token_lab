---
type: tutorial
title: SQL 데이터베이스(SQLModel)
description: SQLModel(SQLAlchemy + Pydantic)로 FastAPI 앱에 SQL 데이터베이스를 연결하는 방법—테이블 모델과 create_engine(check_same_thread), create_all로 테이블 생성, yield 세션 의존성(SessionDep), CRUD 경로 작업, HeroBase/Hero/HeroPublic/HeroCreate/HeroUpdate 다중 모델 패턴, model_dump(exclude_unset=True)와 sqlmodel_update로 PATCH 구현—을 설명한다.
tags: [database, sql, sqlmodel, sqlalchemy, session, crud]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-0f8c534832fbc8753319627a
    resource: repo://docs_src/sql_databases/tutorial001_an_py310.py
  - id: openwiki-source-ce488c1d921d5f2531ab24a4
    resource: repo://docs_src/sql_databases/tutorial002_an_py310.py
  - id: openwiki-source-0a37e890afc7a8dceed367e9
    resource: repo://docs/en/docs/tutorial/sql-databases.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# SQL 데이터베이스(SQLModel)

FastAPI는 SQL(관계형) 데이터베이스 사용을 강제하지 않으며, 원하는 어떤 SQL/NoSQL 라이브러리(ORM)든 쓸 수 있다. 여기서는 FastAPI 작성자가 만든 [SQLModel](https://sqlmodel.tiangolo.com/)을 사용한다. SQLModel은 **SQLAlchemy와 Pydantic** 위에 만들어졌으므로 SQLAlchemy가 지원하는 PostgreSQL, MySQL, SQLite, Oracle, Microsoft SQL Server 등을 모두 쓸 수 있다.

예제는 단일 파일이고 Python에 내장 지원이 있는 **SQLite**를 사용한다. 운영 환경에서는 PostgreSQL 같은 DB 서버를 권장하며, FastAPI + PostgreSQL 공식 템플릿은 [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)이다([프로젝트 생성](../about/features-and-ecosystem.md)).

```console
$ uv add sqlmodel
```

## 단일 모델로 시작하기

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)
    secret_name: str


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

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/heroes/")
def create_hero(hero: Hero, session: SessionDep) -> Hero:
    session.add(hero)
    session.commit()
    session.refresh(hero)
    return hero


@app.get("/heroes/")
def read_heroes(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Hero]:
    heroes = session.exec(select(Hero).offset(offset).limit(limit)).all()
    return heroes


@app.get("/heroes/{hero_id}")
def read_hero(hero_id: int, session: SessionDep) -> Hero:
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero


@app.delete("/heroes/{hero_id}")
def delete_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    session.delete(hero)
    session.commit()
    return {"ok": True}
```

### 모델 정의

- `table=True`: **테이블 모델**임을 뜻한다. SQL 테이블을 나타내며, 일반 Pydantic 클래스 같은 단순 *데이터 모델*이 아니다.
- `Field(primary_key=True)`: 기본 키. `id`는 DB가 생성하므로 코드에서는 `None`일 수 있어 `int | None`으로 선언한다.
- `Field(index=True)`: SQL 인덱스를 만들어 해당 컬럼으로 필터링할 때 조회를 빠르게 한다.
- `str` 타입은 `TEXT`(DB에 따라 `VARCHAR`) 컬럼이 된다.

### 엔진

`engine`은 DB 연결을 보유하며 코드 전체에서 **하나만** 만들어 공유한다. `check_same_thread=False`는 SQLite를 여러 스레드에서 쓰도록 허용한다. 하나의 요청이 의존성 등에서 **여러 스레드**를 쓸 수 있기 때문이며, 요청당 세션 하나를 쓰는 구조로 실제 의도(같은 스레드 보장)를 지킨다.

### 테이블 생성

`SQLModel.metadata.create_all(engine)`이 모든 테이블 모델의 테이블을 만든다. 예제는 시작 이벤트에서 호출하지만, 새 코드에서는 [lifespan](../app-structure/lifespan-events.md)을 권장한다. 운영에서는 앱 시작 전에 실행하는 마이그레이션 스크립트(현재는 [Alembic](https://alembic.sqlalchemy.org/en/latest/) 직접 사용)를 쓰는 것이 일반적이다([배포 개념: 시작 전 단계](../deployment/deployment-concepts-and-https.md)).

### 세션 의존성

`Session`은 객체를 메모리에 두고 변경 사항을 추적하며, `engine`을 통해 DB와 통신한다. [yield 의존성](../dependencies/dependencies-with-yield.md)으로 **요청마다 새 세션**을 제공하고, `Annotated` 별칭 `SessionDep`으로 코드를 단순화한다.

### CRUD

- **생성**: `Hero` 테이블 모델이 Pydantic 모델이기도 하므로 요청 본문으로 받아 `session.add()` → `commit()` → `refresh()` 후 반환한다.
- **목록**: `select(Hero).offset(offset).limit(limit)`. `limit`는 `Query(le=100)`으로 최대 100개로 제한한다.
- **단건**: `session.get(Hero, hero_id)`, 없으면 404.
- **삭제**: `session.delete(hero)` → `commit()`.

`fastapi dev`로 실행하고 `/docs`에서 시험할 수 있다.

## 다중 모델로 개선하기

단일 모델 버전에는 문제가 있다. 클라이언트가 `id`를 지정할 수 있고, `secret_name`이 응답으로 노출된다. 서로 다른 용도의 모델을 만들되 **상속**으로 필드 중복을 피한다. `table=True`가 없는 모델은 **데이터 모델**(사실상 Pydantic 모델)이다.

```Python
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

| 모델 | 종류 | 필드 | 용도 |
| --- | --- | --- | --- |
| `HeroBase` | 데이터 | `name`, `age` | 공통 필드 |
| `Hero` | **테이블** | `id`, `name`, `age`, `secret_name` | DB 테이블 |
| `HeroPublic` | 데이터 | `id`(항상 `int`), `name`, `age` | 클라이언트에 **반환** — `secret_name` 제외 |
| `HeroCreate` | 데이터 | `name`, `age`, `secret_name` | 생성 요청 **검증** |
| `HeroUpdate` | 데이터 | 모두 선택(`None` 기본값) | 부분 수정 |

- `HeroPublic`이 `id: int`를 재선언해 "응답에는 항상 정수 `id`가 있다"는 계약을 만든다. 클라이언트 코드와 [자동 생성 클라이언트](../openapi/generate-clients.md)가 단순해진다.
- `HeroCreate`는 비밀번호를 다루는 방식과 같다. 받아서 저장하되 API로 반환하지 않으며, 실제 비밀번호라면 평문이 아닌 **해시**로 저장한다([JWT와 비밀번호 해싱](../security/oauth2-jwt.md)).

### 다중 모델을 쓰는 경로 작업

```Python
@app.post("/heroes/", response_model=HeroPublic)
def create_hero(hero: HeroCreate, session: SessionDep):
    db_hero = Hero.model_validate(hero)
    session.add(db_hero)
    session.commit()
    session.refresh(db_hero)
    return db_hero


@app.get("/heroes/", response_model=list[HeroPublic])
def read_heroes(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    heroes = session.exec(select(Hero).offset(offset).limit(limit)).all()
    return heroes


@app.get("/heroes/{hero_id}", response_model=HeroPublic)
def read_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero


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

- **생성**: `HeroCreate`로 받고 `Hero.model_validate(hero)`로 테이블 모델을 만든다.
- **응답**: 실제로는 `Hero` 테이블 모델을 반환하지만 `response_model=HeroPublic`으로 선언해 FastAPI가 `HeroPublic`으로 검증·직렬화한다(`secret_name` 필터링). 반환값이 실제로 `HeroPublic`이 아니므로 반환 타입 주석(`-> HeroPublic`) 대신 `response_model`을 쓴다([응답 모델](../responses/response-model.md)).
- **수정(PATCH)**: `hero.model_dump(exclude_unset=True)`로 **클라이언트가 실제로 보낸 값만** 담은 딕셔너리를 얻고(기본값 제외), `hero_db.sqlmodel_update(hero_data)`로 반영한다. 일반 Pydantic 모델의 부분 업데이트는 [본문 업데이트](../models/body-updates-and-encoder.md)를 참고한다.
- **삭제**: 단일 모델 버전과 같다.

## 관련 페이지

- [yield를 사용하는 의존성](../dependencies/dependencies-with-yield.md)
- [추가 모델](../models/extra-models-and-dataclasses.md) — 입력/출력/DB 모델 분리
- [비동기 테스트와 데이터베이스 테스트](../testing/async-tests-and-database.md)
- [고급 의존성](../dependencies/advanced-dependencies.md) — 스트리밍 응답과 세션 수명
