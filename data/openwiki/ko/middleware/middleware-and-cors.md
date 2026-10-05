---
type: "참조"
title: "미들웨어와 CORS"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-539d8b9abc33736a7b2bf32d
    resource: repo://docs_src/advanced_middleware/tutorial002_py310.py
  - id: openwiki-source-babe0caa8e49e3e3763ac854
    resource: repo://docs_src/advanced_middleware/tutorial003_py310.py
  - id: openwiki-source-3ed00d832b86f38c6a7e25f5
    resource: repo://docs_src/cors/tutorial001_py310.py
  - id: openwiki-source-a1f421664c566814c997c663
    resource: repo://docs_src/middleware/tutorial001_py310.py
  - id: openwiki-source-871429548d01a3779623de44
    resource: repo://docs/en/docs/advanced/middleware.md
  - id: openwiki-source-816bc9cdb160c0ea26152bb0
    resource: repo://docs/en/docs/tutorial/cors.md
  - id: openwiki-source-8c4aeccd826b7d0f1407df40
    resource: repo://docs/en/docs/tutorial/middleware.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-3056900339d12e52175aa0b1
    resource: repo://fastapi/middleware/cors.py
  - id: openwiki-source-6f0e71e6c0cd9014f0b87c22
    resource: repo://fastapi/middleware/gzip.py
  - id: openwiki-source-9c5ece77a13062dbdc022b7d
    resource: repo://fastapi/middleware/httpsredirect.py
  - id: openwiki-source-d43bfb6553e982c9eeac16e3
    resource: repo://fastapi/middleware/trustedhost.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 미들웨어와 CORS

**미들웨어**는 특정 경로 작업이 처리하기 **전**에 모든 요청을, 그리고 반환하기 **전**에 모든 응답을 다루는 함수다.

1. 앱에 들어오는 각 **요청**을 받는다.
2. 요청에 무언가를 하거나 필요한 코드를 실행한다.
3. 요청을 나머지 앱(경로 작업)에 넘긴다.
4. 앱이 생성한 **응답**을 받는다.
5. 응답에 무언가를 하거나 코드를 실행한 뒤 반환한다.

> yield 의존성의 종료 코드는 미들웨어 **이후**에 실행되고, 백그라운드 작업도 모든 미들웨어 **이후**에 실행된다.

## HTTP 미들웨어 만들기: @app.middleware("http")

```Python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

미들웨어 함수는 다음을 받는다.

- `request`
- `call_next`: `request`를 받아 해당 경로 작업에 전달하고, 생성된 `response`를 반환하는 함수

`call_next` 호출 전에는 요청을 처리하는 코드를, 호출 후에는 응답을 수정하는 코드를 둔다. `time.time()`보다 정밀한 `time.perf_counter()`를 쓴다.

- 사용자 정의 독점 헤더는 [`X-` 접두사](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers)를 붙일 수 있다.
- 브라우저의 클라이언트가 사용자 정의 헤더를 읽어야 한다면 CORS 설정의 `expose_headers`에 추가해야 한다(아래 참고).
- `fastapi.Request`는 Starlette의 `Request`다.

## 여러 미들웨어의 실행 순서

`@app.middleware()`든 `app.add_middleware()`든, 새 미들웨어는 앱을 감싸 스택을 이룬다. **마지막에 추가한 미들웨어가 가장 바깥**, 처음 추가한 것이 가장 안쪽이다.

```Python
app.add_middleware(MiddlewareA)
app.add_middleware(MiddlewareB)
```

- **요청**: MiddlewareB → MiddlewareA → 라우트
- **응답**: 라우트 → MiddlewareA → MiddlewareB

FastAPI 내부적으로 사용자 미들웨어는 `ServerErrorMiddleware`(500/`Exception` 핸들러)와 `ExceptionMiddleware`(`HTTPException` 등 핸들러) **사이**에 놓인다. 따라서 경로 작업에서 발생한 `HTTPException`은 미들웨어에 도달하기 전에 응답으로 바뀌고, 미들웨어 안에서 발생한 처리되지 않은 예외는 `ServerErrorMiddleware`가 500으로 처리한다([요청 처리 흐름](../internals/request-lifecycle.md)).

## ASGI 미들웨어 추가: add_middleware

FastAPI는 Starlette 기반이며 ASGI 명세를 구현하므로, ASGI 명세를 따르는 **어떤 미들웨어든** 쓸 수 있다. ASGI 미들웨어는 보통 첫 인자로 ASGI 앱을 받는 클래스다.

```Python
from unicorn import UnicornMiddleware

app = SomeASGIApp()

new_app = UnicornMiddleware(app, some_config="rainbow")
```

하지만 직접 감싸는 대신 `app.add_middleware()`를 쓰면, 내부 미들웨어가 서버 오류를 처리하고 사용자 정의 예외 핸들러가 올바르게 동작하도록 보장된다.

```Python
from fastapi import FastAPI
from unicorn import UnicornMiddleware

app = FastAPI()

app.add_middleware(UnicornMiddleware, some_config="rainbow")
```

첫 인자는 미들웨어 클래스, 나머지는 미들웨어에 전달할 인자다. `fastapi.middleware.Middleware`는 Starlette의 `Middleware`이며, `FastAPI(middleware=[Middleware(...)])`로 생성 시 지정할 수도 있다.

## CORS(교차 출처 리소스 공유)

[CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)는 브라우저에서 실행되는 프런트엔드 JavaScript가 **다른 출처(origin)**의 백엔드와 통신하는 상황을 말한다.

### 출처(origin)

출처는 프로토콜(`http`, `https`) + 도메인(`myapp.com`, `localhost`) + 포트(`80`, `443`, `8080`)의 조합이다. `http://localhost`, `https://localhost`, `http://localhost:8080`은 모두 다른 출처다.

### 동작 방식

`http://localhost:8080`의 프런트엔드가 `http://localhost`(포트 80)의 백엔드와 통신하려 하면, 브라우저가 먼저 백엔드에 HTTP `OPTIONS` 요청을 보낸다. 백엔드가 이 출처를 허용하는 적절한 헤더를 보내면 브라우저가 실제 요청을 허용한다. 따라서 백엔드는 "허용된 출처" 목록에 `http://localhost:8080`을 포함해야 한다.

### 와일드카드

`"*"`로 모든 출처를 허용할 수 있지만, 쿠키나 Bearer 토큰 같은 Authorization 헤더 등 **자격 증명(credentials)이 포함된 통신은 제외**된다. 모든 것이 제대로 동작하려면 허용 출처를 명시하는 것이 낫다.

### CORSMiddleware 사용

```Python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def main():
    return {"message": "Hello World"}
```

`CORSMiddleware`의 기본값은 **제한적**이므로, 브라우저가 교차 도메인에서 쓸 수 있도록 출처·메서드·헤더를 명시적으로 허용해야 한다.

| 파라미터 | 설명 | 기본값 |
| --- | --- | --- |
| `allow_origins` | 교차 출처 요청을 허용할 출처 목록. `['*']`는 모든 출처 | `[]` |
| `allow_origin_regex` | 허용할 출처와 매칭할 정규식(예: `'https://.*\.example\.org'`) | `None` |
| `allow_methods` | 허용할 HTTP 메서드. `['*']`는 모든 표준 메서드 | `['GET']` |
| `allow_headers` | 허용할 요청 헤더. `['*']`는 모든 헤더. `Accept`, `Accept-Language`, `Content-Language`, `Content-Type`은 단순 요청에서 항상 허용 | `[]` |
| `allow_credentials` | 교차 출처 요청에서 쿠키 지원 여부. `True`면 `allow_origins`, `allow_methods`, `allow_headers`에 `['*']`를 쓸 수 **없고** 명시해야 한다 | `False` |
| `expose_headers` | 브라우저에서 접근 가능하게 할 응답 헤더 | `[]` |
| `max_age` | 브라우저가 CORS 응답을 캐시할 최대 시간(초) | `600` |

미들웨어가 처리하는 두 가지 요청:

- **Preflight 요청**: `Origin`과 `Access-Control-Request-Method` 헤더가 있는 `OPTIONS` 요청. 미들웨어가 가로채 적절한 CORS 헤더와 함께 정보용 `200` 또는 `400` 응답을 반환한다.
- **단순 요청**: `Origin` 헤더가 있는 모든 요청. 요청은 그대로 통과시키고 응답에 CORS 헤더를 추가한다.

## 내장 미들웨어

`fastapi.middleware`의 미들웨어는 편의상 Starlette 미들웨어를 재노출한 것이다.

### HTTPSRedirectMiddleware

모든 요청이 `https` 또는 `wss`여야 하며, `http`/`ws` 요청은 보안 스킴으로 리다이렉트한다.

```Python
from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

app.add_middleware(HTTPSRedirectMiddleware)
```

TLS 종료 프록시 뒤에서 쓸 때는 프록시 헤더 신뢰 설정(`--forwarded-allow-ips`)이 필요하다([프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md)).

### TrustedHostMiddleware

HTTP Host 헤더 공격을 막기 위해 모든 요청의 `Host` 헤더가 올바른지 검사한다.

```Python
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()

app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["example.com", "*.example.com"]
)
```

- `allowed_hosts`: 허용할 호스트 이름 목록. `*.example.com` 같은 와일드카드로 서브도메인 매칭. 모든 호스트를 허용하려면 `["*"]` 또는 미들웨어를 생략한다.
- `www_redirect`: `True`면 허용 호스트의 non-www 요청을 www로 리다이렉트한다. 기본값 `True`.
- 검증에 실패하면 `400` 응답을 보낸다.

### GZipMiddleware

`Accept-Encoding` 헤더에 `"gzip"`이 있는 요청에 대해 응답을 GZip으로 압축한다. 일반 응답과 스트리밍 응답 모두 처리한다.

```Python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
```

- `minimum_size`: 이 크기(바이트)보다 작은 응답은 압축하지 않는다. 기본값 `500`.
- `compresslevel`: 1~9. 낮을수록 빠르지만 크고, 높을수록 느리지만 작다. 기본값 `9`.

### 기타 ASGI 미들웨어

[Uvicorn의 `ProxyHeadersMiddleware`](https://github.com/Kludex/uvicorn/blob/main/uvicorn/middleware/proxy_headers.py), [MessagePack](https://github.com/florimondmanca/msgpack-asgi) 등. 더 많은 목록은 [Starlette Middleware 문서](https://starlette.dev/middleware/)와 [ASGI Awesome List](https://github.com/florimondmanca/awesome-asgi)를 참고한다.

## 관련 페이지

- [Request 객체 직접 사용과 커스텀 APIRoute](../request/using-request-directly.md) — 특정 라우트에만 적용할 처리
- [응답 헤더와 쿠키](../responses/response-headers-and-cookies.md)
- [요청 처리 흐름](../internals/request-lifecycle.md)
