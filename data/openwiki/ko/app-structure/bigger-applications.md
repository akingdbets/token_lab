---
type: "참조"
title: "큰 애플리케이션: APIRouter로 여러 파일 구성"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-689087189304d4d19a915e26
    resource: repo://docs_src/bigger_applications/app_an_py310/main.py
  - id: openwiki-source-a93f3fe8fdcae43cc7777c57
    resource: repo://docs_src/bigger_applications/app_an_py310/routers/items.py
  - id: openwiki-source-ffe84a85602c83d29ec1965b
    resource: repo://docs/en/docs/tutorial/bigger-applications.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 큰 애플리케이션: APIRouter로 여러 파일 구성

애플리케이션이 커지면 경로 작업을 한 파일에 모두 둘 수 없다. FastAPI는 `APIRouter`로 경로 작업을 모듈별로 나누고, 메인 `FastAPI` 앱에서 `include_router()`로 합치는 방식을 제공한다(Flask의 Blueprint와 비슷한 역할).

## 예제 파일 구조

`docs_src/bigger_applications/app_an_py310/` 예제는 다음 구조를 가진다.

```
app/
├── __init__.py          # app을 Python 패키지로 만든다
├── main.py              # FastAPI 앱 생성 및 라우터 포함
├── dependencies.py      # 공용 의존성
├── routers/
│   ├── __init__.py
│   ├── items.py         # /items 경로들
│   └── users.py         # /users 경로들
└── internal/
    ├── __init__.py
    └── admin.py         # 조직 내 다른 프로젝트와 공유하는 관리자 라우터
```

각 디렉터리의 `__init__.py`(비어 있어도 됨)가 있어야 패키지/서브패키지로 인식되어 상대 임포트를 쓸 수 있다.

## APIRouter로 경로 작업 선언

`APIRouter`는 "작은 `FastAPI`"처럼 동작한다. `FastAPI` 앱과 같은 데코레이터(`@router.get`, `@router.post` …)와 같은 파라미터(`response_model`, `dependencies`, `tags`, `responses` 등)를 그대로 쓴다.

```Python
# app/routers/users.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/users/", tags=["users"])
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]


@router.get("/users/me", tags=["users"])
async def read_user_me():
    return {"username": "fakecurrentuser"}


@router.get("/users/{username}", tags=["users"])
async def read_user(username: str):
    return {"username": username}
```

## 공용 의존성

```Python
# app/dependencies.py
from typing import Annotated

from fastapi import Header, HTTPException


async def get_token_header(x_token: Annotated[str, Header()]):
    if x_token != "fake-super-secret-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")


async def get_query_token(token: str):
    if token != "jessica":
        raise HTTPException(status_code=400, detail="No Jessica token provided")
```

예제를 단순하게 하려고 가짜 헤더/토큰을 쓴다. 실제 인증은 [보안 기초](../security/oauth2-password-flow.md)를 따른다.

## 라우터 수준의 prefix, tags, dependencies, responses

같은 접두사·태그·의존성을 모든 경로 작업에 반복하지 않도록 `APIRouter(...)` 생성 시 한 번에 지정한다.

```Python
# app/routers/items.py
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_token_header

router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)

fake_items_db = {"plumbus": {"name": "Plumbus"}, "gun": {"name": "Portal Gun"}}


@router.get("/")
async def read_items():
    return fake_items_db


@router.get("/{item_id}")
async def read_item(item_id: str):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"name": fake_items_db[item_id]["name"], "item_id": item_id}


@router.put(
    "/{item_id}",
    tags=["custom"],
    responses={403: {"description": "Operation forbidden"}},
)
async def update_item(item_id: str):
    if item_id != "plumbus":
        raise HTTPException(status_code=403, detail="You can only update the item: plumbus")
    return {"item_id": item_id, "name": "The great Plumbus"}
```

결과:

- 경로는 `/items/`, `/items/{item_id}`가 된다.
- 모든 경로 작업에 `items` 태그가 붙고, `update_item`은 `items`와 `custom` 두 태그를 모두 가진다.
- OpenAPI에는 라우터의 `404` 응답과 경로 작업의 `403` 응답이 함께 문서화된다([추가 응답](../responses/additional-responses.md)).
- 라우터의 `dependencies`가 먼저 실행되고, 그다음 데코레이터의 `dependencies`, 마지막으로 일반 파라미터 의존성이 실행된다([데코레이터·전역 의존성](../dependencies/decorator-and-global-dependencies.md)).

`prefix` 규칙: 반드시 `/`로 시작하고 `/`로 끝나면 안 된다. 위반하면 `AssertionError`("A path prefix must start with '/'", "A path prefix must not end with '/' …")가 발생한다. 접두사와 경로가 둘 다 비어 있는 경로 작업을 포함하려 하면 `FastAPIError`("Prefix and path cannot be both empty")가 발생한다.

## 상대 임포트

- `from .dependencies import ...` — 같은 패키지(`app/`)의 모듈
- `from ..dependencies import ...` — 한 단계 위 패키지(`app/routers/` → `app/`)
- `from ...dependencies import ...` — 두 단계 위(존재하지 않으면 오류)

## 메인 FastAPI 앱에서 포함하기

```Python
# app/main.py
from fastapi import Depends, FastAPI

from .dependencies import get_query_token, get_token_header
from .internal import admin
from .routers import items, users

app = FastAPI(dependencies=[Depends(get_query_token)])

app.include_router(users.router)
app.include_router(items.router)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_token_header)],
    responses={418: {"description": "I'm a teapot"}},
)


@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications!"}
```

- `FastAPI(dependencies=[...])`는 앱 전체 경로 작업에 적용되는 **전역 의존성**이다.
- `from .routers import items, users`처럼 **서브모듈을 임포트**하고 `items.router`, `users.router`로 접근하면 두 모듈의 `router` 변수 이름이 충돌하지 않는다.
- 원본 라우터를 수정할 수 없을 때(예: 다른 프로젝트와 공유하는 `internal/admin.py`), `include_router()`에 `prefix`, `tags`, `dependencies`, `responses`를 넘겨 포함 시점에 덧붙일 수 있다. 원본 `admin.router`는 그대로이므로 다른 프로젝트에서는 영향이 없다.
- `include_router()`가 받는 그 밖의 파라미터: `default_response_class`, `callbacks`, `deprecated`, `include_in_schema`, `generate_unique_id_function`.
- `@app.get(...)`으로 앱에 직접 경로 작업을 추가하는 것도 함께 쓸 수 있다.

## include_router의 동작 방식

이 버전의 FastAPI에서 라우터 포함은 **라이브(live)** 방식이다.

- `include_router()`는 경로를 복사하지 않고, 원본 라우터와 포함 컨텍스트(prefix, tags, dependencies 등)를 담은 항목을 부모 라우터의 `routes`에 추가한다. 요청 처리와 OpenAPI 생성 시 접두사·의존성·태그·응답 메타데이터가 합쳐진다.
- 그래서 라우터를 포함한 **뒤에** 그 라우터에 추가한 경로 작업도 앞선 포함을 통해 보인다.
- 라우터는 Starlette의 `Mount`처럼 "마운트"되어 격리되는 것이 아니므로, 모든 경로 작업이 하나의 OpenAPI 스키마와 문서 UI에 나타난다(격리된 앱이 필요하면 [서브 애플리케이션](./sub-applications-proxy-and-wsgi.md) 참고).
- 포함된 라우터의 `on_startup`/`on_shutdown` 핸들러와 `lifespan` 컨텍스트가 부모로 병합된다([수명 주기 이벤트](./lifespan-events.md)).
- `router.routes`를 직접 변경하지 말 것. 라우터 포함·경로 정의가 섞인 트리이므로 최종 경로 작업의 평면 목록으로 취급해서는 안 된다. 공식 API(데코레이터, `.include_router()`)만 사용한다.
- 자기 자신을 포함하거나 순환 포함(이미 자신을 포함한 라우터를 포함)하면 `AssertionError`가 발생한다.

### 라우터 중첩

```Python
router.include_router(other_router)
```

`router`를 앱에 포함하기 전이든 후든 상관없이 `other_router`의 경로 작업이 라우팅과 OpenAPI에 포함된다.

### 같은 라우터를 여러 접두사로 포함

같은 라우터에 대해 `include_router()`를 서로 다른 `prefix`로 여러 번 호출할 수 있다. 예: `/api/v1`과 `/api/latest`에 같은 API를 노출.

## pyproject.toml에 엔트리포인트 설정

앱이 `app/main.py`에 있으므로 다음처럼 설정하면 `fastapi` 명령(그리고 VS Code 확장, FastAPI Cloud)이 앱을 찾는다.

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

이는 `from app.main import app`과 같다. `fastapi dev app/main.py`처럼 경로를 직접 넘길 수도 있지만 매번 기억해야 한다([FastAPI CLI](../getting-started/fastapi-cli-and-debugging.md)).

`/docs`에 접속하면 모든 서브모듈의 경로가 올바른 접두사와 태그로 표시된다.

## 관련 페이지

- [경로 작업 설정](./path-operation-configuration.md) — `tags`, `responses`, `deprecated` 등 개별 설정
- [데코레이터 의존성과 전역 의존성](../dependencies/decorator-and-global-dependencies.md)
- [요청 처리 흐름](../internals/request-lifecycle.md)
