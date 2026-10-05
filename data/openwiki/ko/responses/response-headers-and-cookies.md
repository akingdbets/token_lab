---
type: guide
title: 응답 헤더와 쿠키 설정
description: 경로 작업이나 의존성에서 Response 타입 파라미터(임시 응답)로 헤더·쿠키를 설정하면 response_model 필터링을 유지한 채 최종 응답에 복사되는 방식, Response/JSONResponse를 직접 반환하며 headers와 set_cookie()를 쓰는 방식, X- 사용자 정의 헤더와 CORS expose_headers를 설명한다.
tags: [response-headers, cookies, set-cookie, response, cors]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-912bba61eb50f67721444396
    resource: repo://docs_src/response_cookies/tutorial001_py310.py
  - id: openwiki-source-73233b6f8ab3f64d371b20c9
    resource: repo://docs_src/response_cookies/tutorial002_py310.py
  - id: openwiki-source-7e4d080657afa3a823176eeb
    resource: repo://docs_src/response_headers/tutorial001_py310.py
  - id: openwiki-source-27383bc92276586dd41deb78
    resource: repo://docs_src/response_headers/tutorial002_py310.py
  - id: openwiki-source-36a474c74a81418c60b28eed
    resource: repo://docs/en/docs/advanced/response-cookies.md
  - id: openwiki-source-c21c031b09cf9ef3e4bbfeb0
    resource: repo://docs/en/docs/advanced/response-headers.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 응답 헤더와 쿠키 설정

응답에 헤더나 쿠키를 넣는 방법은 두 가지다.

1. **`Response` 파라미터**(임시 응답 객체)에 설정하고 평소처럼 데이터를 반환한다.
2. `Response`를 **직접 반환**하면서 헤더·쿠키를 넣는다.

`fastapi.Response`는 헤더·쿠키 설정에 자주 쓰여 `fastapi`에서 바로 임포트할 수 있게 제공되며, 실제로는 `starlette.responses.Response`다.

## 방법 1: Response 파라미터

경로 작업 함수에 `Response` 타입 파라미터를 선언하고, 이 **임시** 응답 객체에 헤더·쿠키를 설정한 뒤, `dict`나 DB 모델 등 원하는 객체를 반환한다.

### 헤더

```Python
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/headers-and-object/")
def get_headers(response: Response):
    response.headers["X-Cat-Dog"] = "alone in the world"
    return {"message": "Hello World"}
```

### 쿠키

```Python
from fastapi import FastAPI, Response

app = FastAPI()


@app.post("/cookie-and-object/")
def create_cookie(response: Response):
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return {"message": "Come to the dark side, we have cookies"}
```

동작 방식:

- `response_model`을 선언했다면 반환 객체는 여전히 그것으로 필터링·변환된다.
- FastAPI는 임시 응답에서 **헤더, 쿠키, 상태 코드**를 추출해, 반환값으로 만든 최종 응답에 넣는다. 내부적으로 임시 응답의 원시 헤더 목록(`Set-Cookie` 포함)이 최종 응답 헤더에 추가된다([요청 처리 흐름](../internals/request-lifecycle.md)).
- `Response` 파라미터는 **의존성**에서도 선언할 수 있다. 예를 들어 인증 의존성이 세션 쿠키를 갱신하거나 공통 헤더를 붙일 수 있다. 같은 요청의 모든 의존성과 경로 작업이 같은 임시 응답 객체를 공유한다.
- 상태 코드도 같은 방식으로 바꿀 수 있다([상태 코드](./status-codes.md)).

## 방법 2: Response 직접 반환

### 헤더

```Python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/headers/")
def get_headers():
    content = {"message": "Hello World"}
    headers = {"X-Cat-Dog": "alone in the world", "Content-Language": "en-US"}
    return JSONResponse(content=content, headers=headers)
```

### 쿠키

```Python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.post("/cookie/")
def create_cookie():
    content = {"message": "Come to the dark side, we have cookies"}
    response = JSONResponse(content=content)
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return response
```

`Response`를 직접 반환하면 FastAPI가 **그대로** 반환하므로:

- 데이터 타입이 올바른지 직접 보장해야 한다(예: `JSONResponse`면 JSON 호환).
- `response_model`이 걸러야 했을 데이터를 보내지 않도록 주의한다(직접 반환하면 필터링되지 않는다).
- 자세한 내용은 [응답 직접 반환](./custom-responses.md).

`set_cookie()`는 `max_age`, `expires`, `path`, `domain`, `secure`, `httponly`, `samesite` 등을 지원한다. 쿠키 삭제는 `delete_cookie()`. 전체 옵션은 [Starlette 문서](https://starlette.dev/responses/#set-cookie)를 참고한다.

## 사용자 정의 헤더와 CORS

- 독점 사용자 정의 헤더에는 [`X-` 접두사](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers)를 붙일 수 있다.
- 브라우저의 클라이언트(JavaScript)가 사용자 정의 응답 헤더를 읽어야 한다면 CORS 설정의 `expose_headers`에 추가해야 한다([미들웨어와 CORS](../middleware/middleware-and-cors.md)).

## 보안 참고

세션·인증 쿠키는 보통 `httponly=True`(JavaScript 접근 차단), `secure=True`(HTTPS 전용), 적절한 `samesite`를 설정한다. 쿠키로 인증하는 앱이라면 CSRF 대책도 고려한다([요청 본문: 엄격한 Content-Type](../request/request-body.md)). 요청에서 쿠키를 **읽는** 방법은 [헤더와 쿠키 파라미터](../request/headers-and-cookies.md)를 참고한다.

## 관련 페이지

- [상태 코드](./status-codes.md)
- [응답 직접 반환과 커스텀 응답](./custom-responses.md)
- [헤더와 쿠키 파라미터](../request/headers-and-cookies.md)
- [미들웨어](../middleware/middleware-and-cors.md) — 모든 응답에 헤더 추가(`X-Process-Time` 예제)
