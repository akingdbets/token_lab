---
type: "참조"
title: "WebSocket"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-73c859b33be839276cbb1871
    resource: repo://docs_src/websockets_/tutorial001_py310.py
  - id: openwiki-source-cbecc08eab352f5375fcea34
    resource: repo://docs_src/websockets_/tutorial002_an_py310.py
  - id: openwiki-source-4bee90d37397371d9a4e0494
    resource: repo://docs_src/websockets_/tutorial003_py310.py
  - id: openwiki-source-1c53e08678276c3a6f86ce41
    resource: repo://docs/en/docs/advanced/websockets.md
  - id: openwiki-source-cd7d32cb20717b70ce7fd8ca
    resource: repo://fastapi/exception_handlers.py
  - id: openwiki-source-e4b00136116c0a84db1e2736
    resource: repo://fastapi/websockets.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# WebSocket

FastAPI에서 [WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)을 사용할 수 있다. 먼저 WebSocket 프로토콜 라이브러리를 설치한다(`uvicorn[standard]`를 설치했다면 이미 포함될 수 있다).

```console
$ uv add websockets
```

## 클라이언트

운영 환경에서는 React, Vue.js, Angular 같은 프런트엔드 프레임워크의 유틸리티나 네이티브 모바일 앱 코드가 WebSocket 클라이언트 역할을 한다. 아래 예제는 서버 측에 집중하기 위해 JavaScript가 포함된 HTML을 긴 문자열(`html`)로 두고 `HTMLResponse`로 반환한다. 운영용 방식은 아니다.

## WebSocket 엔드포인트 만들기

```Python
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

html = """..."""  # new WebSocket("ws://localhost:8000/ws") 를 사용하는 HTML/JS


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

- `@app.websocket(path)`(또는 `@router.websocket(path)`)로 선언하고, `WebSocket` 타입 파라미터를 받는다.
- `await websocket.accept()`로 연결을 수락한 뒤 메시지를 `await`로 받고 보낸다.
- 텍스트(`receive_text`/`send_text`), 바이너리(`receive_bytes`/`send_bytes`), JSON(`receive_json`/`send_json`) 데이터를 주고받을 수 있다.
- `fastapi.WebSocket`, `WebSocketDisconnect`, `WebSocketState`는 Starlette 클래스를 편의상 재노출한 것이다.

`fastapi dev`로 실행하고 `http://127.0.0.1:8000`을 열어 메시지를 보내면, 모든 메시지가 같은 WebSocket 연결을 사용한다.

## Depends 등 사용하기

WebSocket 엔드포인트에서도 `fastapi`의 다음 도구를 일반 경로 작업과 같은 방식으로 쓸 수 있다.

- `Depends`, `Security`, `Cookie`, `Header`, `Path`, `Query`

```Python
from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Query,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.responses import HTMLResponse

app = FastAPI()


async def get_cookie_or_token(
    websocket: WebSocket,
    session: Annotated[str | None, Cookie()] = None,
    token: Annotated[str | None, Query()] = None,
):
    if session is None and token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return session or token


@app.websocket("/items/{item_id}/ws")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
    item_id: str,
    q: int | None = None,
    cookie_or_token: Annotated[str, Depends(get_cookie_or_token)],
):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(
            f"Session cookie or query token value is: {cookie_or_token}"
        )
        if q is not None:
            await websocket.send_text(f"Query parameter q is: {q}")
        await websocket.send_text(f"Message text was: {data}, for item ID: {item_id}")
```

- WebSocket에서는 `HTTPException`이 의미가 없으므로 **`WebSocketException`**을 발생시킨다. 종료 코드는 [RFC 6455에 정의된 유효한 코드](https://tools.ietf.org/html/rfc6455#section-7.4.1) 중에서 고른다(예: `status.WS_1008_POLICY_VIOLATION`).
- 의존성은 `WebSocket` 객체 자체도 파라미터로 받을 수 있다.
- 파라미터 검증에 실패하면 `WebSocketRequestValidationError`가 발생하고, 기본 핸들러가 코드 1008로 연결을 닫는다([오류 처리](../errors/handling-errors.md)).
- 브라우저 예제에서는 "Item ID"(경로)와 "Token"(쿼리 파라미터, 의존성이 처리)을 입력해 연결한다.

## 연결 종료와 여러 클라이언트

연결이 닫히면 `await websocket.receive_text()`가 **`WebSocketDisconnect`** 예외를 발생시킨다. 이를 잡아 처리한다.

```Python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")
```

여러 브라우저 탭에서 메시지를 보낸 뒤 한 탭을 닫으면, 나머지 클라이언트가 `Client #1596980209979 left the chat` 같은 메시지를 받는다.

> 이 예제는 모든 연결을 **메모리의 리스트 하나**로 관리하므로 프로세스가 실행 중일 때만, 그리고 **단일 프로세스**에서만 동작한다([워커](../deployment/manual-deployment-and-workers.md)를 여러 개 쓰면 연결이 프로세스별로 나뉜다). Redis, PostgreSQL 등을 지원하는 더 견고한 방법이 필요하면 [encode/broadcaster](https://github.com/encode/broadcaster)를 참고한다.

## 텔레메트리

각 WebSocket 연결은 `WS /ws/{room}` 같은 OpenTelemetry span을 가지며, 정상 종료 코드(`1000`, `1001`)는 오류 로그를 남기지 않는다([OpenTelemetry](./graphql-and-opentelemetry.md)).

## 테스트

`TestClient.websocket_connect()`로 WebSocket을 테스트할 수 있다([테스트 기초](../testing/testing-basics.md)).

## 더 알아보기

- [Starlette `WebSocket` 클래스](https://starlette.dev/websockets/)
- [클래스 기반 WebSocket 처리(`WebSocketEndpoint`)](https://starlette.dev/endpoints/#websocketendpoint)
- 단방향 서버 푸시만 필요하다면 [Server-Sent Events](../responses/streaming-and-sse.md)도 고려한다.
