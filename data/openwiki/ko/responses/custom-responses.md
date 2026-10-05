---
type: guide
title: 응답 직접 반환과 커스텀 응답 클래스
description: Response/JSONResponse를 직접 반환할 때 검증·직렬화·문서화가 생략되는 점과 jsonable_encoder 사용, response_class로 HTMLResponse·PlainTextResponse·RedirectResponse·StreamingResponse·FileResponse를 쓰고 OpenAPI 미디어 타입을 문서화하는 방법, render()를 재정의한 사용자 정의 응답 클래스, default_response_class, deprecated된 UJSONResponse/ORJSONResponse와 응답 모델을 통한 최고 성능 JSON 직렬화를 설명한다.
tags: [responses, response-class, jsonresponse, htmlresponse, fileresponse, streamingresponse, redirectresponse]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-c6a3b927a5b8ad24f873613c
    resource: repo://docs_src/custom_response/tutorial002_py310.py
  - id: openwiki-source-0a2ba0b080b45e8a085c8e6a
    resource: repo://docs_src/custom_response/tutorial004_py310.py
  - id: openwiki-source-7eb058c6f5a7bdc244406ef4
    resource: repo://docs_src/custom_response/tutorial006b_py310.py
  - id: openwiki-source-0b106cc3b03610a537722008
    resource: repo://docs_src/custom_response/tutorial006c_py310.py
  - id: openwiki-source-d1e9b3143bbd2fd1f27c7a54
    resource: repo://docs_src/custom_response/tutorial007_py310.py
  - id: openwiki-source-ba8376ff7c7dc5c7135f3878
    resource: repo://docs_src/custom_response/tutorial009b_py310.py
  - id: openwiki-source-424afaf5d76185f840bc73d0
    resource: repo://docs_src/custom_response/tutorial009c_py310.py
  - id: openwiki-source-2efc19b1027a5823104316e7
    resource: repo://docs_src/custom_response/tutorial010_py310.py
  - id: openwiki-source-cc84216e9a97bdb96850505d
    resource: repo://docs_src/response_directly/tutorial001_py310.py
  - id: openwiki-source-dcdb34b4686892ea94b86f7e
    resource: repo://docs_src/response_directly/tutorial002_py310.py
  - id: openwiki-source-dd715a8bda39f15c790f4edf
    resource: repo://docs/en/docs/advanced/custom-response.md
  - id: openwiki-source-c5ccbe869fa7707548125db8
    resource: repo://docs/en/docs/advanced/response-directly.md
  - id: openwiki-source-6cd3cf9a04dba542dc04fb1e
    resource: repo://fastapi/responses.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 응답 직접 반환과 커스텀 응답 클래스

경로 작업은 보통 `dict`, `list`, Pydantic 모델, DB 모델 등 어떤 데이터든 반환할 수 있다. [응답 모델(반환 타입)](./response-model.md)을 선언하면 FastAPI가 Pydantic으로 JSON을 직렬화한다. 응답 모델이 없으면 [`jsonable_encoder`](../models/body-updates-and-encoder.md)로 JSON 호환 데이터로 바꾼 뒤 `JSONResponse`에 넣는다.

## Response 직접 반환

`Response`나 그 하위 클래스(`JSONResponse` 등)를 반환하면 FastAPI는 **그대로** 전달한다.

- Pydantic 모델로 데이터 변환을 하지 않고, 내용을 어떤 타입으로도 변환하지 않는다.
- 어떤 데이터 타입이든 반환하고 데이터 선언·검증을 무시할 수 있는 **유연성**을 준다.
- 반면 데이터가 올바르고 올바른 형식이며 직렬화 가능한지 보장할 **책임**도 진다.
- 직접 반환한 응답은 **검증·직렬화·문서화되지 않는다**. 문서화가 필요하면 [추가 응답(`responses`)](./additional-responses.md)을 쓴다.

### Response 안에서 jsonable_encoder 사용

Pydantic 모델을 그대로 `JSONResponse`에 넣을 수 없다. `datetime`, `UUID` 등을 JSON 호환 타입으로 먼저 바꿔야 한다.

```Python
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Item(BaseModel):
    title: str
    timestamp: datetime
    description: str | None = None


app = FastAPI()


@app.put("/items/{id}")
def update_item(id: str, item: Item):
    json_compatible_item_data = jsonable_encoder(item)
    return JSONResponse(content=json_compatible_item_data)
```

### 사용자 정의 내용 반환(XML 등)

```Python
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/legacy/")
def get_legacy_data():
    data = """<?xml version="1.0"?>
    <shampoo>
    <Header>
        Apply shampoo here.
    </Header>
    <Body>
        You'll have to use soap here.
    </Body>
    </shampoo>
    """
    return Response(content=data, media_type="application/xml")
```

> 성능 측면에서는 `JSONResponse`를 직접 반환하는 것보다 **응답 모델**을 쓰는 것이 훨씬 낫다. 응답 모델이 있고 `response_class`를 지정하지 않으면, FastAPI는 Pydantic(Rust)으로 바로 JSON 바이트를 만들어 올바른 미디어 타입(`application/json`)의 `Response`로 반환한다(`JSONResponse`를 거치지 않음).

## response_class: 응답 클래스 지정

경로 작업 데코레이터의 `response_class`로 사용할 `Response` 하위 클래스를 선언한다. `response_class`는 응답의 **미디어 타입**도 정의하며 OpenAPI에 그렇게 문서화된다.

- `response_class`가 JSON 미디어 타입(`JSONResponse` 등)이면, 반환 데이터는 응답 모델로 자동 변환·필터링된다.
- 미디어 타입이 없는 응답 클래스를 쓰면 FastAPI는 응답에 내용이 없다고 보고 OpenAPI에 응답 형식을 문서화하지 않는다.

### HTMLResponse

```Python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/items/", response_class=HTMLResponse)
async def read_items():
    return """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Look ma! HTML!</h1>
        </body>
    </html>
    """
```

직접 반환할 수도 있지만, 그러면 OpenAPI에 문서화되지 않는다(예: `Content-Type`).

```Python
@app.get("/items/")
async def read_items():
    html_content = """..."""
    return HTMLResponse(content=html_content, status_code=200)
```

### 문서화하면서 응답 덮어쓰기

`response_class`를 지정하고 **동시에** `Response`를 반환하면, `response_class`는 OpenAPI 문서화에만 쓰이고 반환한 `Response`가 그대로 사용된다.

```Python
def generate_html_response():
    html_content = """..."""
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/items/", response_class=HTMLResponse)
async def read_items():
    return generate_html_response()
```

## 사용 가능한 응답 클래스

`fastapi.responses`의 클래스는 대부분 `starlette.responses`를 그대로 재노출한 것이다. `Response`는 헤더·쿠키 설정에도 자주 쓰이므로 `fastapi.Response`로도 제공된다.

### Response

모든 응답의 기본 클래스. 파라미터:

- `content`: `str` 또는 `bytes`
- `status_code`: HTTP 상태 코드 `int`
- `headers`: 문자열 `dict`
- `media_type`: 미디어 타입 `str`(예: `"text/html"`)

`Content-Length` 헤더와 `media_type` 기반 `Content-Type`(텍스트 타입은 charset 추가)이 자동으로 포함된다.

### HTMLResponse / PlainTextResponse

텍스트 또는 바이트를 받아 HTML / 일반 텍스트 응답을 반환한다.

```Python
from fastapi.responses import PlainTextResponse


@app.get("/", response_class=PlainTextResponse)
async def main():
    return "Hello World"
```

### JSONResponse

데이터를 받아 `application/json` 응답을 반환한다. FastAPI의 기본 응답 클래스지만, 응답 모델/반환 타입이 있으면 위의 빠른 경로가 사용된다.

### RedirectResponse

HTTP 리다이렉트를 반환하며 기본 상태 코드는 **307**(Temporary Redirect)이다.

```Python
from fastapi.responses import RedirectResponse


@app.get("/typer")
async def redirect_typer():
    return RedirectResponse("https://typer.tiangolo.com")


# response_class로 지정하면 URL만 반환하면 된다 (기본 307)
@app.get("/fastapi", response_class=RedirectResponse)
async def redirect_fastapi():
    return "https://fastapi.tiangolo.com"


# status_code와 결합
@app.get("/pydantic", response_class=RedirectResponse, status_code=302)
async def redirect_pydantic():
    return "https://docs.pydantic.dev/"
```

### StreamingResponse

async 제너레이터나 일반 제너레이터/이터레이터를 받아 응답 본문을 스트리밍한다.

```Python
import anyio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


async def fake_video_streamer():
    for i in range(10):
        yield b"some fake video bytes"
        await anyio.sleep(0)


@app.get("/")
async def main():
    return StreamingResponse(fake_video_streamer())
```

- async 작업은 `await` 지점에서만 취소될 수 있다. `await`가 없으면 제너레이터가 취소 요청 후에도 계속 실행될 수 있으므로 `await anyio.sleep(0)`으로 이벤트 루프에 취소 처리 기회를 준다. 크거나 무한한 스트림일수록 중요하다.
- 파일 같은 객체(예: `open()` 결과)는 그것을 순회하는 제너레이터로 감싸 스트리밍한다.

```Python
some_file_path = "large-video-file.mp4"


@app.get("/")
def main():
    def iterfile():
        with open(some_file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="video/mp4")
```

직접 `StreamingResponse`를 반환하기보다 `yield`를 쓰는 경로 작업 방식이 더 편리하고 취소도 알아서 처리한다([스트리밍과 SSE](./streaming-and-sse.md)).

### FileResponse

파일을 비동기로 스트리밍한다. 다른 응답과 생성 인자가 다르다.

- `path`: 스트리밍할 파일 경로
- `headers`: 사용자 정의 헤더 `dict`
- `media_type`: 미디어 타입. 지정하지 않으면 파일 이름/경로로 추론한다.
- `filename`: 지정하면 `Content-Disposition`에 포함된다.

`Content-Length`, `Last-Modified`, `ETag` 헤더가 적절히 포함된다.

```Python
from fastapi.responses import FileResponse

some_file_path = "large-video-file.mp4"


@app.get("/")
async def main():
    return FileResponse(some_file_path)


# response_class로 지정하면 파일 경로만 반환하면 된다
@app.get("/", response_class=FileResponse)
async def main():
    return some_file_path
```

### EventSourceResponse

Server-Sent Events용 응답 클래스(`fastapi.sse`)도 `fastapi.responses`에서 임포트할 수 있다([스트리밍과 SSE](./streaming-and-sse.md)).

## 사용자 정의 응답 클래스

`Response`를 상속하고 내용을 `bytes`로 반환하는 `render(content)`를 구현한다. 예: [`orjson`](https://github.com/ijl/orjson)으로 들여쓴 JSON 반환.

```Python
from typing import Any

import orjson
from fastapi import FastAPI, Response

app = FastAPI()


class CustomORJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        assert orjson is not None, "orjson must be installed"
        return orjson.dumps(content, option=orjson.OPT_INDENT_2)


@app.get("/", response_class=CustomORJSONResponse)
async def main():
    return {"message": "Hello World"}
```

`{"message": "Hello World"}` 대신 들여쓰기된 JSON이 반환된다.

### UJSONResponse / ORJSONResponse (deprecated)

`fastapi.responses.UJSONResponse`와 `ORJSONResponse`는 **deprecated**이며 사용 시 `FastAPIDeprecationWarning`이 발생한다. 각각 `ujson`, `orjson`을 별도로 설치해야 한다. 성능이 목적이라면 응답 모델을 쓰는 편이 낫다. 응답 모델이 있으면 FastAPI가 `jsonable_encoder` 같은 중간 단계 없이 Pydantic으로 바로 JSON을 직렬화하며, Pydantic은 `orjson`과 같은 Rust 메커니즘을 사용한다.

## 기본 응답 클래스: default_response_class

`FastAPI` 인스턴스나 `APIRouter`를 만들 때 기본 응답 클래스를 지정할 수 있다.

```Python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(default_response_class=HTMLResponse)


@app.get("/items/")
async def read_items():
    return "<h1>Items</h1><p>This is a list of items.</p>"
```

경로 작업에서 `response_class`로 여전히 덮어쓸 수 있다. `include_router(default_response_class=...)`도 지원한다.

## 관련 페이지

- [응답 모델](./response-model.md)
- [상태 코드](./status-codes.md)
- [응답 헤더와 쿠키](./response-headers-and-cookies.md)
- [추가 응답](./additional-responses.md)
- [템플릿](../integrations/static-files-templates-frontend.md) — `TemplateResponse`
