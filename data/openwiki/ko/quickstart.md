---
type: quickstart
title: 빠른 시작과 위키 길잡이
description: FastAPI를 설치하고 첫 앱(경로·쿼리 파라미터, 요청 본문)을 실행해 자동 문서를 확인하는 최소 절차와, 하고 싶은 작업(요청 받기, 응답 다루기, 의존성, 보안, DB, 미들웨어, 테스트, 배포 등)별로 이 위키의 어느 페이지를 읽으면 되는지 안내하는 라우팅 맵이다.
tags: [quickstart, getting-started, installation, routing-map, overview]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-e912e06b230ad432d81148c2
    resource: repo://docs_src/first_steps/tutorial001_py310.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 빠른 시작과 위키 길잡이

FastAPI는 표준 Python 타입 힌트로 API를 만드는 현대적이고 빠른(고성능) 웹 프레임워크다. 웹 부분은 [Starlette](https://starlette.dev/), 데이터 부분은 [Pydantic](https://pydantic.dev/docs/) 위에 만들어졌다. 이 위키는 이 저장소의 사용자 문서(`docs/en/docs`), 예제 코드(`docs_src`), 소스(`fastapi/`)를 바탕으로 **사용법 중심**으로 정리했다.

## 5분 시작

### 1. 설치

[uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치하고 프로젝트를 만든다(Python 3.10+).

```console
$ uv init awesome-project --bare
$ cd awesome-project
$ uv add "fastapi[standard]"
```

`"fastapi[standard]"`는 모든 터미널에서 동작하도록 따옴표로 감싼다. `standard`에는 `fastapi` CLI, Uvicorn, httpx(TestClient), python-multipart(폼·파일), jinja2, pydantic-settings 등이 포함된다. `pip`를 쓴다면 가상 환경 안에서 설치한다. 자세한 내용: [환경 변수와 가상 환경](./getting-started/environment-and-virtualenvs.md).

### 2. 앱 작성

`main.py`:

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

코드가 `async`/`await`를 쓴다면 `async def`로 선언한다. 잘 모르겠다면 [async/await](./getting-started/python-types-and-async.md)를 참고한다.

### 3. 실행

```console
$ uv run fastapi dev
```

- `http://127.0.0.1:8000/items/5?q=somequery` → `{"item_id": 5, "q": "somequery"}`
- `item_id`는 경로 파라미터(`int`로 변환·검증), `q`는 선택적 쿼리 파라미터다.
- `http://127.0.0.1:8000/docs`(Swagger UI), `http://127.0.0.1:8000/redoc`(ReDoc)에서 자동 대화형 문서를 볼 수 있다.

`fastapi dev`는 개발 모드(자동 리로드, `127.0.0.1`), 운영에서는 `fastapi run`을 쓴다([FastAPI CLI와 디버깅](./getting-started/fastapi-cli-and-debugging.md)). `pyproject.toml`에 `[tool.fastapi] entrypoint = "main:app"`를 설정해 두면 CLI·VS Code 확장·FastAPI Cloud가 앱을 찾는다.

### 4. 요청 본문 추가

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_id": item_id}
```

`fastapi dev` 서버가 자동으로 다시 로드되고, `/docs`에 새 본문이 반영된다. 이 짧은 선언만으로 FastAPI는 JSON 본문 읽기, 타입 변환, 검증(오류 시 명확한 422 응답), 에디터 자동 완성, OpenAPI 문서화를 해 준다.

## 작업별 길잡이

### 시작하기

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 첫 앱의 구조와 자동 문서 이해 | [첫 단계](./getting-started/first-steps.md) |
| `fastapi dev`/`run`, 엔트리포인트, 디버거 연결 | [FastAPI CLI와 디버깅](./getting-started/fastapi-cli-and-debugging.md) |
| 타입 힌트·`Annotated`·Pydantic 기초, `async def` vs `def` | [Python 타입 힌트와 async/await](./getting-started/python-types-and-async.md) |
| 설치 옵션, 가상 환경, 환경 변수 | [환경 변수와 가상 환경](./getting-started/environment-and-virtualenvs.md) |
| FastAPI의 기능·배경·생태계 | [기능, 대안 비교, 프로젝트 생성](./about/features-and-ecosystem.md) |

### 요청 데이터 받기

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 경로 파라미터, Enum, `Path()` 숫자 검증 | [경로 파라미터와 숫자 검증](./request/path-parameters.md) |
| 쿼리 파라미터, `Query()` 문자열 검증, 리스트, 쿼리 모델 | [쿼리 파라미터](./request/query-parameters.md) |
| JSON 본문, 여러 본문, `Body(embed=True)`, `Field`, Content-Type | [요청 본문](./request/request-body.md) |
| 중첩 모델, `HttpUrl`, UUID/datetime 등, base64 bytes | [중첩 모델과 추가 데이터 타입](./request/nested-models-and-data-types.md) |
| 헤더·쿠키와 그 모델 | [헤더와 쿠키 파라미터](./request/headers-and-cookies.md) |
| 폼, 파일 업로드(`UploadFile`) | [폼 데이터와 파일 업로드](./request/forms-and-files.md) |
| `Request` 직접 사용, 커스텀 Request/APIRoute | [Request 객체 직접 사용](./request/using-request-directly.md) |

### 모델과 데이터

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 입력/출력/DB 모델 분리, Union 응답, dataclasses | [추가 모델, Union 응답, dataclasses](./models/extra-models-and-dataclasses.md) |
| 문서에 요청 예제 표시 | [스키마 예제 선언](./models/schema-examples.md) |
| PUT/PATCH 업데이트, `jsonable_encoder` | [본문 업데이트와 jsonable_encoder](./models/body-updates-and-encoder.md) |
| Pydantic v1 코드 이전 | [Pydantic v1에서 v2로](./models/pydantic-v1-to-v2.md) |

### 응답 다루기

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 반환 타입·`response_model`로 출력 필터링 | [응답 모델과 반환 타입](./responses/response-model.md) |
| 201 등 상태 코드, 동적 변경 | [상태 코드](./responses/status-codes.md) |
| HTML·파일·리다이렉트·사용자 정의 응답 | [응답 직접 반환과 커스텀 응답 클래스](./responses/custom-responses.md) |
| 응답 헤더·쿠키 설정 | [응답 헤더와 쿠키 설정](./responses/response-headers-and-cookies.md) |
| 스트리밍, JSON Lines, SSE | [스트리밍, JSON Lines, Server-Sent Events](./responses/streaming-and-sse.md) |
| 추가 응답을 OpenAPI에 문서화 | [OpenAPI 추가 응답 선언](./responses/additional-responses.md) |
| 오류 반환, 예외 핸들러 | [오류 처리와 예외 핸들러](./errors/handling-errors.md) |

### 의존성 주입

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| `Depends`, 클래스 의존성, 하위 의존성, 캐시 | [의존성 주입 기초](./dependencies/dependency-injection-basics.md) |
| 데코레이터·라우터·앱 전역 의존성 | [데코레이터 의존성과 전역 의존성](./dependencies/decorator-and-global-dependencies.md) |
| DB 세션처럼 정리가 필요한 리소스(`yield`, `scope`) | [yield를 사용하는 의존성](./dependencies/dependencies-with-yield.md) |
| 설정값을 받는 의존성, 버전별 동작 변화 | [고급 의존성](./dependencies/advanced-dependencies.md) |

### 보안

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 로그인(OAuth2 password + Bearer), 현재 사용자 | [보안 기초: OAuth2 비밀번호 흐름](./security/oauth2-password-flow.md) |
| JWT 발급·검증, 비밀번호 해싱 | [JWT 토큰과 비밀번호 해싱](./security/oauth2-jwt.md) |
| 권한(스코프) | [OAuth2 스코프](./security/oauth2-scopes.md) |
| HTTP Basic, API 키, Bearer, 선택적 인증 | [HTTP Basic, API 키, 기타 보안 스킴](./security/http-basic-and-api-keys.md) |

### 앱 구조와 설정

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 여러 파일로 나누기(`APIRouter`) | [큰 애플리케이션](./app-structure/bigger-applications.md) |
| tags, summary, operation_id, openapi_extra | [경로 작업 설정](./app-structure/path-operation-configuration.md) |
| 제목·버전·문서 URL, 문서 끄기 | [메타데이터와 문서 URL](./app-structure/metadata-and-docs-urls.md) |
| 시작/종료 시 리소스 로드(lifespan) | [수명 주기 이벤트](./app-structure/lifespan-events.md) |
| 환경 변수·`.env` 설정 | [설정과 환경 변수](./app-structure/settings.md) |
| 서브 앱 마운트, 프록시·`root_path`, Flask/Django 포함 | [서브 애플리케이션, 프록시, WSGI](./app-structure/sub-applications-proxy-and-wsgi.md) |
| 미들웨어, CORS, GZip | [미들웨어와 CORS](./middleware/middleware-and-cors.md) |

### 통합

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| SQL DB(SQLModel) | [SQL 데이터베이스](./integrations/sql-databases.md) |
| 응답 후 작업(이메일 등) | [백그라운드 작업](./integrations/background-tasks.md) |
| 정적 파일, Jinja2 템플릿, SPA 프론트엔드 | [정적 파일, 템플릿, 프론트엔드](./integrations/static-files-templates-frontend.md) |
| 실시간 양방향 통신 | [WebSocket](./integrations/websockets.md) |
| GraphQL, OpenTelemetry 관측 | [GraphQL과 OpenTelemetry](./integrations/graphql-and-opentelemetry.md) |

### OpenAPI

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| 스키마 수정, Swagger UI 설정, 문서 자산 자체 호스팅 | [OpenAPI 확장과 문서 UI](./openapi/customizing-openapi-and-docs-ui.md) |
| 콜백·웹훅 문서화 | [OpenAPI 콜백과 웹훅](./openapi/callbacks-and-webhooks.md) |
| TypeScript 등 클라이언트 SDK 생성 | [클라이언트 SDK 생성](./openapi/generate-clients.md) |

### 테스트와 배포

| 하고 싶은 것 | 읽을 페이지 |
| --- | --- |
| `TestClient`, 의존성 오버라이드, lifespan·WebSocket 테스트 | [테스트 기초](./testing/testing-basics.md) |
| async 테스트, DB 테스트 | [비동기 테스트와 데이터베이스 테스트](./testing/async-tests-and-database.md) |
| HTTPS, 재시작, 복제, 버전 고정 개념 | [배포 개념, HTTPS, 버전 관리](./deployment/deployment-concepts-and-https.md) |
| `fastapi run`, Uvicorn, `--workers` | [수동 배포와 서버 워커](./deployment/manual-deployment-and-workers.md) |
| Docker 이미지, FastAPI Cloud | [Docker와 클라우드 배포](./deployment/docker-and-cloud.md) |

### 동작 원리가 궁금할 때

[요청 처리 흐름(사용자 관점의 내부 구조)](./internals/request-lifecycle.md) — 미들웨어 스택, 라우팅, 의존성 해석, 검증·직렬화 순서, 정리(exit stack) 시점.

## 추천 학습 순서

1. [첫 단계](./getting-started/first-steps.md) → [경로 파라미터](./request/path-parameters.md) → [쿼리 파라미터](./request/query-parameters.md) → [요청 본문](./request/request-body.md)
2. [응답 모델](./responses/response-model.md) → [오류 처리](./errors/handling-errors.md)
3. [의존성 주입 기초](./dependencies/dependency-injection-basics.md) → [보안 기초](./security/oauth2-password-flow.md) → [JWT](./security/oauth2-jwt.md)
4. [SQL 데이터베이스](./integrations/sql-databases.md) → [큰 애플리케이션](./app-structure/bigger-applications.md) → [테스트](./testing/testing-basics.md)
5. [배포 개념](./deployment/deployment-concepts-and-https.md) → [Docker](./deployment/docker-and-cloud.md)
