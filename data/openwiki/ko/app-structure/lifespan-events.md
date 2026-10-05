---
type: guide
title: 수명 주기 이벤트(lifespan)
description: FastAPI(lifespan=...)에 비동기 컨텍스트 매니저를 넘겨 앱 시작 전·종료 후 로직(ML 모델 로드, 커넥션 풀 등)을 실행하는 방법과, 더 이상 권장되지 않는 on_event("startup"/"shutdown") 이벤트, 라우터 lifespan 병합, 서브 앱과의 관계를 설명한다.
tags: [lifespan, startup, shutdown, events, asgi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-3cec1b06c25d3cf1c240cc47
    resource: repo://docs_src/events/tutorial003_py310.py
  - id: openwiki-source-f3f5740af79e7e432255437e
    resource: repo://docs/en/docs/advanced/events.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 수명 주기 이벤트(lifespan)

앱이 **요청을 받기 시작하기 전에 한 번**, 그리고 **요청 처리를 모두 마친 뒤 종료 직전에 한 번** 실행할 코드를 정의할 수 있다. 앱 전체에서 공유하고 끝나면 정리해야 하는 리소스(데이터베이스 커넥션 풀, 공유 머신러닝 모델 등)를 다루기에 적합하다.

## 왜 필요한가

무거운 모델을 모듈 최상단에서 로드하면, 관련 없는 간단한 자동 테스트를 실행할 때도 모델 로드를 기다려야 한다. lifespan을 쓰면 **코드를 임포트할 때가 아니라 앱이 요청을 받기 직전**에 로드할 수 있다.

## lifespan 파라미터

```Python
from contextlib import asynccontextmanager

from fastapi import FastAPI


def fake_answer_to_everything_ml_model(x: float):
    return x * 42


ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ML 모델 로드 (시작 시)
    ml_models["answer_to_everything"] = fake_answer_to_everything_ml_model
    yield
    # ML 모델 정리 및 리소스 해제 (종료 시)
    ml_models.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/predict")
async def predict(x: float):
<!-- openwiki: broken internal link [x] file "x" does not exist. Fix the href or restore the target, then delete this comment. -->
    result = ml_models["answer_to_everything"](x)
    return {"result": result}
```

- `yield` **이전** 코드: 앱이 요청을 받기 전(startup)에 실행된다.
- `yield` **이후** 코드: 앱이 요청 처리를 끝낸 뒤(shutdown) 실행된다. 메모리나 GPU 같은 리소스를 해제한다.
- 구조는 [yield 의존성](../dependencies/dependencies-with-yield.md)과 매우 비슷하다.

### 비동기 컨텍스트 매니저

`@asynccontextmanager`(`contextlib`)는 함수를 `async with`로 쓸 수 있는 비동기 컨텍스트 매니저로 바꾼다.

```Python
async with lifespan(app):
    await do_stuff()
```

`with` 블록에 들어가기 전 `yield` 이전 코드를, 블록을 빠져나온 뒤 `yield` 이후 코드를 실행한다. `FastAPI`의 `lifespan` 파라미터는 이런 비동기 컨텍스트 매니저를 받는다.

이 버전의 FastAPI는 `lifespan`으로 받은 값을 다음처럼 처리한다.

- `None`(기본값): `on_startup`/`on_shutdown` 핸들러를 실행하는 기본 lifespan(`_DefaultLifespan`)을 사용한다.
- 데코레이터 없는 **async 제너레이터 함수**: 자동으로 `asynccontextmanager`로 감싼다.
- **동기 제너레이터 함수**: 내부 래퍼로 감싸서 사용한다.
- 그 외(이미 컨텍스트 매니저인 경우): 그대로 사용한다.

## lifespan 상태(state)

ASGI lifespan 프로토콜은 Starlette의 lifespan 처리를 따른다. `yield`에 딕셔너리를 넘기면(`yield {"model": ...}`) Starlette의 lifespan 상태로 쓰여 요청에서 `request.state`로 접근할 수 있다. 자세한 내용은 [Starlette Lifespan 문서](https://starlette.dev/lifespan/)를 참고한다.

## 라우터의 lifespan 병합

`APIRouter(lifespan=...)`에도 lifespan을 지정할 수 있다. `include_router()`는 포함된 라우터의 lifespan을 부모의 lifespan 안쪽에 중첩해 병합한다(부모 진입 → 자식 진입 → … → 자식 종료 → 부모 종료). 두 lifespan이 상태 딕셔너리를 yield하면 하나로 합쳐지며, 키가 겹치면 부모 쪽 값이 우선한다. 포함된 라우터의 `on_startup`/`on_shutdown` 핸들러도 부모에 추가된다([큰 애플리케이션](./bigger-applications.md)).

## 대체 이벤트: startup / shutdown (deprecated)

> 권장 방식은 `lifespan`이다. **`lifespan`을 제공하면 `startup`/`shutdown` 이벤트 핸들러는 호출되지 않는다.** 둘 중 하나만 쓴다.

`app.on_event()`는 `@deprecated`로 표시되어 있어 사용 시 경고가 발생한다. 핸들러는 `async def`나 `def` 모두 가능하다.

```Python
from fastapi import FastAPI

app = FastAPI()

items = {}


@app.on_event("startup")
async def startup_event():
    items["foo"] = {"name": "Fighters"}
    items["bar"] = {"name": "Tenders"}


@app.get("/items/{item_id}")
async def read_items(item_id: str):
    return items[item_id]
```

- 여러 개의 startup 핸들러를 추가할 수 있으며, 모두 끝나야 요청을 받기 시작한다.

```Python
@app.on_event("shutdown")
def shutdown_event():
    with open("log.txt", mode="a") as log:
        log.write("Application shutdown")
```

- `open()`은 async가 아니므로 일반 `def`로 선언했다.
- `FastAPI(on_startup=[...], on_shutdown=[...])` 파라미터로도 등록할 수 있다.

시작과 종료 로직은 보통 연결되어 있다(리소스 획득 → 해제). 별도 함수로 나누면 전역 변수 같은 꼼수가 필요하므로 lifespan을 권장한다.

## 기술적 배경

내부적으로 ASGI 명세의 [Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html)에 정의된 `startup`/`shutdown` 이벤트를 사용한다.

## 서브 애플리케이션 주의

lifespan 이벤트는 **메인 앱에서만** 실행되며, `app.mount()`로 마운트한 [서브 애플리케이션](./sub-applications-proxy-and-wsgi.md)에서는 실행되지 않는다.

## 테스트

`TestClient`를 `with` 문으로 사용하면 lifespan(startup/shutdown)이 실행된다. 자세한 내용은 [테스트 기초](../testing/testing-basics.md)를 참고한다.
