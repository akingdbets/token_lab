---
type: guide
title: 백그라운드 작업
description: BackgroundTasks 파라미터와 add_task()로 응답을 보낸 뒤 실행할 작업(이메일 알림, 파일 처리 등)을 등록하는 방법, 의존성 여러 단계에서 같은 BackgroundTasks 객체 공유, Response를 직접 반환할 때의 동작, Starlette BackgroundTask와의 차이, Celery 같은 대안을 설명한다.
tags: [background-tasks, add-task, dependencies, celery]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-1cc99efb4a255c20ae28655e
    resource: repo://docs_src/background_tasks/tutorial001_py310.py
  - id: openwiki-source-84b400c1e155ab0fc9ca2054
    resource: repo://docs_src/background_tasks/tutorial002_an_py310.py
  - id: openwiki-source-d3c9d22ec2ffb7771384a96e
    resource: repo://docs/en/docs/tutorial/background-tasks.md
  - id: openwiki-source-aef05ad53d3c32b290b5dc5a
    resource: repo://fastapi/background.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 백그라운드 작업

응답을 반환한 **후**에 실행할 작업을 정의할 수 있다. 클라이언트가 작업 완료를 기다릴 필요가 없는 경우에 유용하다.

- 작업 후 **이메일 알림** 보내기: 메일 서버 연결과 전송은 몇 초씩 걸리므로 응답을 먼저 보내고 백그라운드에서 전송한다.
- **데이터 처리**: 느린 처리가 필요한 파일을 받으면 "Accepted"(HTTP 202)를 반환하고 백그라운드에서 처리한다.

## BackgroundTasks 사용

```Python
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


def write_notification(email: str, message=""):
    with open("log.txt", mode="w") as email_file:
        content = f"notification for {email}: {message}"
        email_file.write(content)


@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}
```

1. 경로 작업 함수에 `BackgroundTasks` 타입 파라미터를 선언한다. FastAPI가 객체를 만들어 넘겨준다(`Request`처럼 타입으로 인식되는 특수 파라미터).
2. **작업 함수**는 파라미터를 받을 수 있는 일반 함수다. `async def`든 `def`든 FastAPI가 올바르게 처리한다. 예제는 파일 쓰기가 `async`/`await`를 쓰지 않으므로 `def`로 정의했다.
3. `.add_task()`에 다음을 넘긴다.
   - 백그라운드에서 실행할 작업 함수(`write_notification`)
   - 순서대로 전달할 위치 인자(`email`)
   - 키워드 인자(`message="some notification"`)

등록된 작업들은 응답 전송 후 **등록 순서대로** 하나씩 `await`된다(동기 함수는 Starlette가 스레드풀에서 실행).

## 의존성과 함께 사용

`BackgroundTasks`는 경로 작업 함수, 의존성, 하위 의존성 등 **여러 단계**에서 선언할 수 있다. FastAPI는 한 요청 안에서 **같은 객체를 재사용**하므로 모든 작업이 합쳐져 응답 후 실행된다.

```Python
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI

app = FastAPI()


def write_log(message: str):
    with open("log.txt", mode="a") as log:
        log.write(message)


def get_query(background_tasks: BackgroundTasks, q: str | None = None):
    if q:
        message = f"found query: {q}\n"
        background_tasks.add_task(write_log, message)
    return q


@app.post("/send-notification/{email}")
async def send_notification(
    email: str, background_tasks: BackgroundTasks, q: Annotated[str, Depends(get_query)]
):
    message = f"message to {email}\n"
    background_tasks.add_task(write_log, message)
    return {"message": "Message sent"}
```

요청에 쿼리 `q`가 있으면 의존성에서 등록한 작업이 로그에 쓰고, 이어서 경로 작업 함수에서 등록한 작업이 `email`을 사용한 메시지를 쓴다. 모두 응답을 보낸 **뒤**에 실행된다.

## Response를 직접 반환할 때

경로 작업 함수가 `Response`(예: `JSONResponse`)를 직접 반환하면, FastAPI는 그 응답의 `background`가 **비어 있을 때만** 주입된 `BackgroundTasks`를 붙인다. 응답에 이미 `background=...`를 지정했다면 `BackgroundTasks` 파라미터로 등록한 작업은 실행되지 않으므로 둘을 섞지 않는다([응답 직접 반환](../responses/custom-responses.md)).

## 기술적 세부

- `fastapi.BackgroundTasks`는 `starlette.background.BackgroundTasks`를 상속한 클래스다. `fastapi`에서 바로 임포트할 수 있게 해, 실수로 `starlette.background`의 `BackgroundTask`(끝에 `s` 없음)를 임포트하는 일을 막는다.
- `BackgroundTasks`(복수형)만 경로 작업 파라미터로 쓸 수 있다. 단수형 `BackgroundTask`는 코드에서 직접 객체를 만들어 Starlette `Response`에 포함해 반환해야 한다.
- FastAPI의 `BackgroundTasks`는 각 작업 실행을 텔레메트리 작업(`background_task`)으로 감싼다([OpenTelemetry](./graphql-and-opentelemetry.md)).

## yield 의존성과의 관계

FastAPI 0.106.0 이후 yield 의존성의 리소스(예: DB 세션)를 백그라운드 작업에서 재사용하지 않아야 한다. 작업 안에서 새 세션을 만들고, 객체 대신 ID를 넘겨 다시 조회한다([고급 의존성](../dependencies/advanced-dependencies.md)).

## 주의: 무거운 작업에는 다른 도구

무거운 백그라운드 계산이 필요하고 같은 프로세스에서 실행할 필요가 없다면(메모리·변수 공유가 필요 없다면) [Celery](https://docs.celeryq.dev) 같은 큰 도구가 낫다. RabbitMQ나 Redis 같은 메시지/작업 큐가 필요해 설정이 복잡하지만, 여러 프로세스와 여러 서버에서 작업을 실행할 수 있다.

같은 FastAPI 앱의 변수와 객체에 접근해야 하거나, 이메일 알림처럼 작은 작업이라면 `BackgroundTasks`로 충분하다.

## 관련 페이지

- [수명 주기 이벤트](../app-structure/lifespan-events.md) — 앱 전체 리소스
- [고급 의존성](../dependencies/advanced-dependencies.md)
- [스트리밍과 SSE](../responses/streaming-and-sse.md)
