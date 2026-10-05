---
type: "참조"
title: "테스트: TestClient, 의존성 오버라이드, 이벤트, WebSocket"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-252031fc006dbd553c56ddbf
    resource: repo://docs_src/app_testing/app_a_py310/test_main.py
  - id: openwiki-source-b4dc3eb56757a33b2aed4ee7
    resource: repo://docs_src/app_testing/app_b_an_py310/test_main.py
  - id: openwiki-source-495efc9c9a17fc0e77fcccf1
    resource: repo://docs_src/app_testing/tutorial001_py310.py
  - id: openwiki-source-59c9fd26e11b511bdb9a623d
    resource: repo://docs_src/app_testing/tutorial002_py310.py
  - id: openwiki-source-531954ed16fc7efe7e13db77
    resource: repo://docs_src/app_testing/tutorial003_py310.py
  - id: openwiki-source-1173922cb177b14322341b79
    resource: repo://docs_src/app_testing/tutorial004_py310.py
  - id: openwiki-source-bb553b0c924c015f7ad96484
    resource: repo://docs_src/dependency_testing/tutorial001_an_py310.py
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-c2aa67a6d15b272c485d017f
    resource: repo://fastapi/testclient.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 테스트: TestClient, 의존성 오버라이드, 이벤트, WebSocket

[Starlette](https://www.starlette.dev/testclient/) 덕분에 FastAPI 앱 테스트는 쉽고 즐겁다. `TestClient`는 Requests를 본떠 설계된 [HTTPX](https://www.python-httpx.org) 기반이라 익숙하고 직관적이며, [pytest](https://docs.pytest.org/)를 그대로 쓸 수 있다.

## TestClient 사용

```console
$ uv add httpx
$ uv add pytest
```

(`fastapi[standard]`에는 `httpx`가 포함되어 있다.)

```Python
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Hello World"}
```

- FastAPI 앱을 넘겨 `TestClient`를 만든다.
- 이름이 `test_`로 시작하는 함수를 만든다(pytest 관례).
- `TestClient` 객체를 `httpx`처럼 쓰고, 확인할 내용을 표준 `assert`로 작성한다.
- 테스트 함수는 `async def`가 아니라 **일반 `def`**이며, 클라이언트 호출에도 `await`가 필요 없다. 앱 요청 외에 async 함수(예: 비동기 DB)를 호출해야 한다면 [비동기 테스트](./async-tests-and-database.md)를 참고한다.
- `fastapi.testclient.TestClient`는 `starlette.testclient.TestClient`를 그대로 재노출한 것이다.

## 테스트 분리

실제 앱에서는 테스트를 별도 파일에 둔다.

```
.
├── app
│   ├── __init__.py
│   ├── main.py
│   └── test_main.py
```

```Python
# app/main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}
```

```Python
# app/test_main.py
from fastapi.testclient import TestClient

from .main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Hello World"}
```

같은 패키지(`__init__.py`)이므로 상대 임포트 `from .main import app`을 쓴다.

### 확장 예제: 헤더·본문·오류

```Python
# app/main.py
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

fake_secret_token = "coneofsilence"

fake_db = {
    "foo": {"id": "foo", "title": "Foo", "description": "There goes my hero"},
    "bar": {"id": "bar", "title": "Bar", "description": "The bartenders"},
}

app = FastAPI()


class Item(BaseModel):
    id: str
    title: str
    description: str | None = None


@app.get("/items/{item_id}", response_model=Item)
async def read_main(item_id: str, x_token: Annotated[str, Header()]):
    if x_token != fake_secret_token:
        raise HTTPException(status_code=400, detail="Invalid X-Token header")
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]


@app.post("/items/")
async def create_item(item: Item, x_token: Annotated[str, Header()]) -> Item:
    if x_token != fake_secret_token:
        raise HTTPException(status_code=400, detail="Invalid X-Token header")
    if item.id in fake_db:
        raise HTTPException(status_code=409, detail="Item already exists")
    fake_db[item.id] = item.model_dump()
    return item
```

```Python
# app/test_main.py
from fastapi.testclient import TestClient

from .main import app

client = TestClient(app)


def test_read_item():
    response = client.get("/items/foo", headers={"X-Token": "coneofsilence"})
    assert response.status_code == 200
    assert response.json() == {
        "id": "foo",
        "title": "Foo",
        "description": "There goes my hero",
    }


def test_read_item_bad_token():
    response = client.get("/items/foo", headers={"X-Token": "hailhydra"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid X-Token header"}


def test_create_item():
    response = client.post(
        "/items/",
        headers={"X-Token": "coneofsilence"},
        json={"id": "foobar", "title": "Foo Bar", "description": "The Foo Barters"},
    )
    assert response.status_code == 200


def test_create_existing_item():
    response = client.post(
        "/items/",
        headers={"X-Token": "coneofsilence"},
        json={"id": "foo", "title": "The Foo ID Stealers", "description": "There goes my stealer"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Item already exists"}
```

요청에 정보를 넣는 방법은 `httpx`(또는 `requests`)와 같다.

| 전달할 것 | 방법 |
| --- | --- |
| 경로·쿼리 파라미터 | URL에 직접 포함 |
| JSON 본문 | `json=`에 Python 객체(예: `dict`) |
| 폼 데이터 | `data=` |
| 헤더 | `headers=`에 `dict` |
| 쿠키 | `cookies=`에 `dict` |

`TestClient`는 Pydantic 모델이 아니라 JSON으로 변환 가능한 데이터를 받는다. 테스트에서 Pydantic 모델을 보내려면 [`jsonable_encoder`](../models/body-updates-and-encoder.md)를 쓴다.

```console
$ uv run pytest
```

## 의존성 오버라이드: app.dependency_overrides

테스트 중에 의존성을 바꿔야 할 때가 있다. 예: 외부 인증 제공자를 호출하는 의존성은 한 번은 테스트하되, 모든 테스트마다 호출하고 싶지 않다(느리거나 비용이 들 수 있다). 대신 테스트용 가짜 사용자를 반환하는 의존성으로 교체한다.

`app.dependency_overrides`는 원래 의존성을 키, 대체 의존성을 값으로 하는 단순한 `dict`다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


async def common_parameters(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return {"message": "Hello Items!", "params": commons}


@app.get("/users/")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return {"message": "Hello Users!", "params": commons}


client = TestClient(app)


async def override_dependency(q: str | None = None):
    return {"q": q, "skip": 5, "limit": 10}


app.dependency_overrides[common_parameters] = override_dependency


def test_override_in_items():
    response = client.get("/items/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Items!",
        "params": {"q": None, "skip": 5, "limit": 10},
    }


def test_override_in_items_with_params():
    response = client.get("/items/?q=foo&skip=100&limit=200")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Items!",
        "params": {"q": "foo", "skip": 5, "limit": 10},
    }
```

- FastAPI는 의존성을 해석할 때 원래 의존성 대신 대체 의존성을 호출한다. 대체 의존성은 자체 파라미터를 가질 수 있으며(`q`), 원래 의존성의 파라미터(`skip`, `limit`)는 더 이상 쓰이지 않는다.
- 경로 작업 함수, 데코레이터 `dependencies`, `.include_router()` 등 **앱 어디에서 쓰인 의존성이든** 교체할 수 있다.
- 되돌리려면 `app.dependency_overrides = {}`. 일부 테스트에서만 교체하려면 테스트 시작에서 설정하고 끝에서 초기화한다(pytest 픽스처를 쓰면 편하다).
- 설정 의존성 교체 예는 [설정과 환경 변수](../app-structure/settings.md), DB 세션 교체 예는 [데이터베이스 테스트](./async-tests-and-database.md)를 참고한다.

## lifespan과 startup/shutdown 이벤트 테스트

테스트에서 lifespan을 실행하려면 `TestClient`를 **`with` 문**으로 쓴다.

```Python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

items = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    items["foo"] = {"name": "Fighters"}
    items["bar"] = {"name": "Tenders"}
    yield
    # clean up items
    items.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/items/{item_id}")
async def read_items(item_id: str):
    return items[item_id]


def test_read_items():
    # lifespan 시작 전에는 items가 비어 있다
    assert items == {}

    with TestClient(app) as client:
        # with 블록 안에서 lifespan이 시작되어 items가 추가된다
        assert items == {"foo": {"name": "Fighters"}, "bar": {"name": "Tenders"}}

        response = client.get("/items/foo")
        assert response.status_code == 200
        assert response.json() == {"name": "Fighters"}

    # with 블록 종료는 앱 종료를 흉내 내므로 lifespan이 끝나고 items가 정리된다
    assert items == {}
```

deprecated된 `startup`/`shutdown` 이벤트도 같은 방식이다.

```Python
@app.on_event("startup")
async def startup_event():
    items["foo"] = {"name": "Fighters"}
    items["bar"] = {"name": "Tenders"}


def test_read_items():
    with TestClient(app) as client:
        response = client.get("/items/foo")
        assert response.status_code == 200
        assert response.json() == {"name": "Fighters"}
```

`with` 없이 `TestClient(app)`만 만들면 lifespan/시작 이벤트가 **실행되지 않는다**. 자세한 내용은 [Starlette의 lifespan 테스트 문서](https://starlette.dev/lifespan/#running-lifespan-in-tests)를 참고한다([수명 주기 이벤트](../app-structure/lifespan-events.md)).

## WebSocket 테스트

같은 `TestClient`로 WebSocket을 테스트한다. `websocket_connect()`를 `with` 문에서 써서 연결한다.

```Python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@app.websocket("/ws")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"msg": "Hello WebSocket"})
    await websocket.close()


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data == {"msg": "Hello WebSocket"}
```

`send_text`/`receive_text`, `send_json`/`receive_json` 등으로 메시지를 주고받는다. 자세한 내용은 [Starlette WebSocket 테스트 문서](https://starlette.dev/testclient/#testing-websocket-sessions)와 [WebSocket](../integrations/websockets.md)을 참고한다.

## 관련 페이지

- [비동기 테스트와 데이터베이스 테스트](./async-tests-and-database.md)
- [의존성 주입 기초](../dependencies/dependency-injection-basics.md)
- [설정과 환경 변수](../app-structure/settings.md)
- [배포 개념: 버전 업그레이드 전 테스트](../deployment/deployment-concepts-and-https.md)
