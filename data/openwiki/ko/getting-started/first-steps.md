---
type: "참조"
title: "첫 단계: FastAPI 앱과 경로 작업"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-e912e06b230ad432d81148c2
    resource: repo://docs_src/first_steps/tutorial001_py310.py
  - id: openwiki-source-0d5fbd2e5c9e1777ecbb618b
    resource: repo://docs_src/first_steps/tutorial003_py310.py
  - id: openwiki-source-95935867654abe313559916b
    resource: repo://docs/en/docs/tutorial/first-steps.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 첫 단계: FastAPI 앱과 경로 작업

## 가장 단순한 FastAPI 앱

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
```

`main.py`로 저장하고 개발 서버를 실행한다.

```console
$ uv run fastapi dev

   FastAPI   Starting development server 🚀
   ...
    server   Server started at http://127.0.0.1:8000
    server   Documentation at http://127.0.0.1:8000/docs
```

`http://127.0.0.1:8000`을 열면 `{"message": "Hello World"}` JSON 응답을 볼 수 있다. `fastapi dev`의 세부 동작은 [FastAPI CLI와 디버깅](./fastapi-cli-and-debugging.md)을 참고한다.

## 자동 문서

| URL | 내용 |
| --- | --- |
| `http://127.0.0.1:8000/docs` | [Swagger UI](https://github.com/swagger-api/swagger-ui) 대화형 API 문서(브라우저에서 직접 호출 가능) |
| `http://127.0.0.1:8000/redoc` | [ReDoc](https://github.com/Redocly/redoc) 대체 문서 |
| `http://127.0.0.1:8000/openapi.json` | 원본 OpenAPI 스키마(JSON) |

URL 변경·비활성화는 [메타데이터와 문서 URL](../app-structure/metadata-and-docs-urls.md)에서 다룬다.

### OpenAPI와 스키마

- **스키마**: 무언가를 구현하는 코드가 아니라 추상적인 정의·설명이다.
- **API 스키마**: [OpenAPI](https://github.com/OAI/OpenAPI-Specification)는 API 경로, 각 경로가 받는 파라미터 등을 정의하는 방식을 정한 명세다.
- **데이터 스키마**: JSON 같은 데이터의 형태(속성과 타입). OpenAPI는 API에서 주고받는 데이터를 **JSON Schema**로 정의한다.

`/openapi.json`은 다음과 같이 시작한다.

```JSON
{
    "openapi": "3.1.0",
    "info": {
        "title": "FastAPI",
        "version": "0.1.0"
    },
    "paths": {
        "/items/": {
            "get": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
...
```

이 OpenAPI 스키마가 두 가지 대화형 문서를 구동하며, OpenAPI 기반의 다른 도구를 추가하거나 프런트엔드·모바일·IoT용 [클라이언트 코드를 자동 생성](../openapi/generate-clients.md)하는 데도 쓰인다.

## 단계별 정리

### 1단계: FastAPI 임포트

`FastAPI`는 API의 모든 기능을 제공하는 Python 클래스이며, `Starlette`를 직접 상속한다. 따라서 Starlette의 모든 기능을 `FastAPI`에서도 쓸 수 있다.

### 2단계: FastAPI 인스턴스 만들기

`app = FastAPI()`로 만든 `app`이 API를 만드는 주요 상호작용 지점이다. 생성자 파라미터로 제목, 버전, 문서 URL, 전역 의존성, lifespan 등을 설정할 수 있다.

### 3단계: 경로 작업 만들기

- **경로(path)**: URL에서 첫 `/`부터 시작하는 마지막 부분. `https://example.com/items/foo`의 경로는 `/items/foo`다. "엔드포인트", "라우트"라고도 한다.
- **작업(operation)**: HTTP 메서드. `POST`, `GET`, `PUT`, `DELETE`와 `OPTIONS`, `HEAD`, `PATCH`, `TRACE`. 보통 `POST`는 생성, `GET`은 읽기, `PUT`은 수정, `DELETE`는 삭제에 쓴다. OpenAPI에서는 HTTP 메서드 각각을 "operation"이라 부른다.

`@app.get("/")`는 바로 아래 함수가 경로 `/`에 대한 `GET` 요청을 처리한다고 FastAPI에 알려 주는 **경로 작업 데코레이터**다. 다른 메서드는 `@app.post()`, `@app.put()`, `@app.delete()`, `@app.options()`, `@app.head()`, `@app.patch()`, `@app.trace()`를 쓴다.

FastAPI는 각 메서드에 특정 의미를 강제하지 않는다. 위의 용도는 지침일 뿐이며, 예를 들어 GraphQL은 보통 모든 작업을 `POST`로 처리한다.

### 4단계: 경로 작업 함수 정의

데코레이터 바로 아래의 함수가 **경로 작업 함수**다. FastAPI는 `/`로 `GET` 요청이 올 때마다 이 함수를 호출한다. `async def` 대신 일반 함수로도 정의할 수 있다.

```Python
@app.get("/")
def root():
    return {"message": "Hello World"}
```

차이는 [Python 타입 힌트와 async/await](./python-types-and-async.md)를 참고한다.

### 5단계: 내용 반환

`dict`, `list`, `str`·`int` 같은 단일 값, Pydantic 모델을 반환할 수 있다. ORM 객체 등 많은 객체가 자동으로 JSON으로 변환된다([jsonable_encoder](../models/body-updates-and-encoder.md), [응답 모델](../responses/response-model.md)).

### 6단계: 배포(선택)

`fastapi deploy` 한 명령으로 [FastAPI Cloud](https://fastapicloud.com)에 배포할 수 있다. 다른 클라우드 제공자나 자체 서버에도 배포할 수 있다([Docker와 클라우드 배포](../deployment/docker-and-cloud.md)).

## 엔트리포인트 설정

`pyproject.toml`에 앱 위치를 지정해 두면 `fastapi` 명령과 VS Code 확장, FastAPI Cloud가 앱을 찾는다.

```toml
[tool.fastapi]
entrypoint = "main:app"
```

## 다음 단계

- [경로 파라미터](../request/path-parameters.md)
- [쿼리 파라미터](../request/query-parameters.md)
- [요청 본문](../request/request-body.md)
- [경로 작업 설정](../app-structure/path-operation-configuration.md)
