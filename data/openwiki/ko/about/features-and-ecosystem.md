---
type: overview
title: FastAPI 기능, 대안 비교, 프로젝트 생성
description: FastAPI가 제공하는 주요 기능(OpenAPI 기반 자동 문서, 타입 기반 검증, 의존성 주입, 보안), Starlette·Pydantic·Uvicorn과의 관계, 벤치마크 해석법, 풀스택 템플릿, 에디터 확장, 도움 받기와 기여 방법을 정리한다.
tags: [overview, features, starlette, pydantic, benchmarks, ecosystem]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-65385d28aa615ccf9c247795
    resource: repo://docs/en/docs/benchmarks.md
  - id: openwiki-source-84c2fb1bfb265caa7a5aec95
    resource: repo://docs/en/docs/editor-support.md
  - id: openwiki-source-150d8aa89aa20ce136f4a262
    resource: repo://docs/en/docs/features.md
  - id: openwiki-source-35afbe91457b82f255b61278
    resource: repo://docs/en/docs/project-generation.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# FastAPI 기능, 대안 비교, 프로젝트 생성

FastAPI는 **표준 Python 타입 힌트**만으로 API를 선언하면 검증·직렬화·문서화를 자동으로 해 주는 웹 프레임워크다. 이 페이지는 "FastAPI가 무엇을 해 주고, 무엇 위에 만들어졌는지"를 한눈에 정리한다.

## 주요 기능

| 기능 | 내용 |
| --- | --- |
| 개방형 표준 | [OpenAPI](https://github.com/OAI/OpenAPI-Specification)로 경로 작업·파라미터·요청 본문·보안을 선언하고, 데이터 모델은 JSON Schema로 문서화한다. 덕분에 여러 언어로 클라이언트 코드 자동 생성이 가능하다([클라이언트 SDK 생성](../openapi/generate-clients.md)). |
| 자동 문서 | 기본으로 Swagger UI(`/docs`)와 ReDoc(`/redoc`) 두 가지 대화형 문서를 제공한다([첫 단계](../getting-started/first-steps.md)). |
| 현대적 Python | 새 문법 없이 표준 타입 선언만 사용한다([Python 타입 힌트와 async/await](../getting-started/python-types-and-async.md)). |
| 에디터 지원 | 모든 곳에서 자동 완성·타입 검사가 동작하도록 설계되었다. |
| 검증 | `dict`, `list`, `str`(길이), `int`/`float`(범위), URL, Email, UUID 등 대부분의 타입을 Pydantic이 검증한다. |
| 보안·인증 | HTTP Basic, OAuth2(JWT 포함), 헤더/쿼리/쿠키 API 키 등 OpenAPI의 모든 보안 스킴을 지원한다([보안 기초](../security/oauth2-password-flow.md)). |
| 의존성 주입 | 의존성이 다시 의존성을 가지는 그래프를 자동으로 해석하고, 의존성에서 선언한 파라미터도 검증·문서화된다([의존성 주입 기초](../dependencies/dependency-injection-basics.md)). |
| "무제한 플러그인" | 별도 플러그인 체계 없이 의존성으로 통합 기능을 만든다. |

Pydantic 모델을 쓰는 표준 Python 코드는 다음과 같다.

```Python
from datetime import date

from pydantic import BaseModel

# 변수를 str로 선언하면 함수 내부에서 에디터 지원을 받는다
def main(user_id: str):
    return user_id


# Pydantic 모델
class User(BaseModel):
    id: int
    name: str
    joined: date


my_user: User = User(id=3, name="John Doe", joined="2018-07-19")

second_user_data = {"id": 4, "name": "Mary", "joined": "2018-11-30"}
my_second_user: User = User(**second_user_data)
```

## 기반 라이브러리: Starlette, Pydantic, Uvicorn

FastAPI는 바닥부터 새로 만든 것이 아니라 세 가지 도구 위에 기능을 얹은 구조다.

- **Starlette** — 경량 ASGI 프레임워크. `FastAPI` 클래스는 `Starlette`를 **직접 상속**한다(`class FastAPI(Starlette)`). 따라서 WebSocket, 프로세스 내 백그라운드 작업, 시작/종료 이벤트, HTTPX 기반 테스트 클라이언트, CORS·GZip·정적 파일·스트리밍 응답, 세션·쿠키 등 Starlette 기능을 그대로 쓸 수 있고, 기존 Starlette 코드도 동작한다.
- **Pydantic** — 타입 힌트 기반 데이터 검증·직렬화·JSON Schema 생성. FastAPI는 이 JSON Schema를 OpenAPI 문서에 넣는다. Pydantic 기반 ORM/ODM과도 그대로 연동된다.
- **Uvicorn** — 권장 ASGI 서버. 라우팅 같은 프레임워크 기능은 없고, `--workers` 옵션으로 다중 프로세스 실행이 가능하다([수동 배포와 서버 워커](../deployment/manual-deployment-and-workers.md)).

이 저장소의 `pyproject.toml`이 선언한 런타임 의존성은 `starlette>=0.46.0`, `pydantic>=2.9.0`, `typing-extensions`, `typing-inspection`, `annotated-doc`, `opentelemetry-api`이며, Python 3.10 이상이 필요하다(`requires-python = ">=3.10"`). Pydantic v1은 지원하지 않는다([Pydantic v1에서 v2로](../models/pydantic-v1-to-v2.md)).

## 벤치마크를 읽는 법

TechEmpower 독립 벤치마크에서 Uvicorn 위의 FastAPI는 가장 빠른 Python 프레임워크 중 하나로, 내부적으로 사용하는 Starlette와 Uvicorn 바로 아래에 위치한다. 비교할 때는 계층을 구분해야 한다.

- **Uvicorn**(ASGI 서버) → Daphne, Hypercorn, uWSGI 같은 서버와 비교한다.
- **Starlette**(웹 마이크로프레임워크, Uvicorn 위에서 동작) → Sanic, Flask, Django와 비교한다.
- **FastAPI**(Starlette 위의 API 프레임워크) → 데이터 검증·직렬화·문서화를 통합한 Flask-apispec, NestJS, Molten 등과 비교한다.

FastAPI는 Starlette보다 빠를 수 없지만, Starlette만 쓰면 검증·직렬화를 직접 구현해야 하므로 결과적으로 비슷한 오버헤드가 생긴다. 자동 문서는 시작 시점에 생성되므로 요청 처리 오버헤드를 추가하지 않는다.

## 대안과 설계 역사 요약

FastAPI 문서(`alternatives.md`, `history-design-future.md`)는 Django, Django REST Framework, Flask, Requests, Swagger/OpenAPI, Marshmallow, Webargs, APISpec, Flask-apispec, NestJS, Sanic, Falcon, Molten, Hug, APIStar 등에서 받은 영감을 정리한다. 예를 들어 Requests에서 `get`, `post` 같은 HTTP 메서드 이름 기반의 단순한 API를, NestJS에서 의존성 주입을, APIStar에서 타입 힌트 기반 파라미터 선언과 자동 문서화를 가져왔다. 설계 단계에서 PyCharm, VS Code, Jedi 기반 에디터로 개발자 API를 미리 시험해 자동 완성과 타입 검사가 최대한 동작하도록 했다.

## 풀스택 템플릿(Full Stack FastAPI Template)

[Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)은 초기 설정·보안·DB·일부 API가 이미 구성된 시작점이다.

- 백엔드: FastAPI, SQLModel(ORM), Pydantic, PostgreSQL
- 프런트엔드: React + TypeScript + Vite, Tailwind CSS·shadcn/ui, 자동 생성 클라이언트, Playwright E2E 테스트
- 운영: Docker Compose, Traefik 리버스 프록시(자동 HTTPS), GitHub Actions CI/CD
- 보안: 기본 비밀번호 해싱, JWT 인증, 이메일 기반 비밀번호 복구, Pytest 테스트

관련 개념은 [SQL 데이터베이스](../integrations/sql-databases.md), [JWT 토큰](../security/oauth2-jwt.md), [Docker 배포](../deployment/docker-and-cloud.md)를 참고한다.

## 에디터 확장(FastAPI Extension)

FastAPI Labs가 배포하는 공식 확장은 VS Code·Cursor(및 vscode.dev, github.dev)에서 동작한다.

- 워크스페이스에서 `FastAPI()`를 인스턴스화하는 파일을 찾아 앱을 자동 탐지한다. 탐지가 안 되면 `pyproject.toml`의 `[tool.fastapi]` 또는 `fastapi.entryPoint` 설정에 `myapp.main:app` 형식으로 지정한다([FastAPI CLI](../getting-started/fastapi-cli-and-debugging.md)와 같은 엔트리포인트 개념).
- Path Operation Explorer, 경로 검색(<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>), 테스트 클라이언트 호출(`client.get('/items')`) 위의 CodeLens 이동, FastAPI Cloud 배포와 로그 스트리밍을 제공한다.

## 도움 받기와 기여

- 질문·기능 제안은 GitHub Discussions에 올린다. Discord 채팅은 일반 대화용이며 질문에는 적합하지 않다(검색되지 않고 묻히기 쉽다).
- 뉴스레터 구독, GitHub 스타·릴리스 Watch, 작성자 팔로우로 소식을 받을 수 있다.
- 코드 기여는 [tiangolo.com - Contributing](https://tiangolo.com/open-source/contributing/) 지침을 따른다.
- FastAPI의 주요 재정은 `fastapi deploy` 한 명령으로 배포하는 FastAPI Cloud에서 나온다([Docker와 클라우드 배포](../deployment/docker-and-cloud.md)).
