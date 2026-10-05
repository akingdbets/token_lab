---
type: guide
title: 메타데이터와 문서 URL, 조건부 OpenAPI
description: FastAPI() 생성자의 title·summary·description·version·terms_of_service·contact·license_info, openapi_tags로 태그 설명과 순서 지정, openapi_url·docs_url·redoc_url 변경 및 비활성화, pydantic-settings로 환경에 따라 OpenAPI를 끄는 방법을 다룬다.
tags: [metadata, openapi, docs-url, swagger-ui, redoc, conditional-openapi]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-d522d5ea7409258d151bf874
    resource: repo://docs_src/conditional_openapi/tutorial001_py310.py
  - id: openwiki-source-ebb59a8a93678406cad02490
    resource: repo://docs_src/metadata/tutorial001_1_py310.py
  - id: openwiki-source-5dc155895c2b4b1a0942a04e
    resource: repo://docs_src/metadata/tutorial001_py310.py
  - id: openwiki-source-4a9ed6fb9cecfaac688c0d72
    resource: repo://docs_src/metadata/tutorial004_py310.py
  - id: openwiki-source-62bed36ab9995da06c43fe2e
    resource: repo://docs/en/docs/how-to/conditional-openapi.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 메타데이터와 문서 URL, 조건부 OpenAPI

`FastAPI(...)` 생성자 파라미터로 OpenAPI 스키마와 자동 문서 UI(Swagger UI, ReDoc)에 나타나는 메타데이터와 URL을 설정한다.

## API 메타데이터

| 파라미터 | 타입 | 설명 |
| --- | --- | --- |
| `title` | `str` | API 제목. 기본값 `"FastAPI"` |
| `summary` | `str` | 짧은 요약(OpenAPI 3.1.0, FastAPI 0.99.0부터) |
| `description` | `str` | 설명. **Markdown** 사용 가능 |
| `version` | `str` | **여러분 애플리케이션의** 버전(OpenAPI 버전이 아님). 기본값 `"0.1.0"` |
| `terms_of_service` | `str` | 이용약관 URL |
| `contact` | `dict` | `name`, `url`, `email` |
| `license_info` | `dict` | `name`(필수), `identifier`(SPDX, `url`과 상호 배타) 또는 `url` |

```Python
from fastapi import FastAPI

description = """
ChimichangApp API helps you do awesome stuff. 🚀

## Items

You can **read items**.

## Users

You will be able to:

* **Create users** (_not implemented_).
* **Read users** (_not implemented_).
"""

app = FastAPI(
    title="ChimichangApp",
    description=description,
    summary="Deadpool's favorite app. Nuff said.",
    version="0.0.1",
    terms_of_service="http://example.com/terms/",
    contact={
        "name": "Deadpoolio the Amazing",
        "url": "http://x-force.example.com/contact/",
        "email": "dp@x-force.example.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)


@app.get("/items/")
async def read_items():
    return [{"name": "Katana"}]
```

### 라이선스 identifier

OpenAPI 3.1.0 / FastAPI 0.99.0부터 `url` 대신 SPDX `identifier`를 쓸 수 있다.

```Python
license_info={
    "name": "Apache 2.0",
    "identifier": "Apache-2.0",
},
```

### OpenAPI 버전 문자열

FastAPI는 OpenAPI **3.1.0** 스키마를 생성한다. 3.1.0을 인식하지 못하는 도구용으로 `app.openapi_version = "3.0.2"`처럼 속성만 바꿀 수 있지만, 실제 스키마 형식이 바뀌는 것은 아닌 "꼼수"다(생성자 파라미터로는 제공되지 않는다).

## 태그 메타데이터: openapi_tags

경로 작업을 묶는 태그마다 설명을 붙일 수 있다. 리스트의 각 딕셔너리는 다음 키를 가진다.

- `name` (**필수**): 경로 작업/`APIRouter`의 `tags`에 쓰는 이름과 동일한 문자열
- `description`: Markdown 가능한 설명
- `externalDocs`: `description`, `url`(**필수**)을 가진 외부 문서 정보

```Python
from fastapi import FastAPI

tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. The **login** logic is also here.",
    },
    {
        "name": "items",
        "description": "Manage items. So _fancy_ they have their own docs.",
        "externalDocs": {
            "description": "Items external docs",
            "url": "https://fastapi.tiangolo.com/",
        },
    },
]

app = FastAPI(openapi_tags=tags_metadata)


@app.get("/users/", tags=["users"])
async def get_users():
    return [{"name": "Harry"}, {"name": "Ron"}]


@app.get("/items/", tags=["items"])
async def get_items():
    return [{"name": "wand"}, {"name": "flying broom"}]
```

- 사용하는 모든 태그에 메타데이터를 넣을 필요는 없다.
- **리스트 순서가 문서 UI의 태그 표시 순서**가 된다(알파벳순이 아님).
- 태그 지정 방법은 [경로 작업 설정](./path-operation-configuration.md)을 참고한다.

## OpenAPI URL

기본적으로 스키마는 `/openapi.json`에서 제공된다.

```Python
app = FastAPI(openapi_url="/api/v1/openapi.json")
```

`openapi_url=None`으로 하면 OpenAPI 스키마가 완전히 비활성화되고, 이를 사용하는 **문서 UI도 함께 비활성화**된다. 내부적으로 `FastAPI.setup()`은 `openapi_url`이 설정된 경우에만 스키마 경로를 등록하고, `docs_url`/`redoc_url` 경로도 `openapi_url`이 있을 때만 등록한다. 이 경로들은 `include_in_schema=False`로 추가되어 스키마 자체에는 나타나지 않는다.

## 문서 URL

- **Swagger UI**: 기본 `/docs`. `docs_url`로 변경, `docs_url=None`으로 비활성화
- **ReDoc**: 기본 `/redoc`. `redoc_url`로 변경, `redoc_url=None`으로 비활성화

```Python
app = FastAPI(docs_url="/documentation", redoc_url=None)
```

Swagger UI 동작 옵션이나 CDN 대신 자체 호스팅 자산을 쓰는 방법은 [OpenAPI 확장과 문서 UI 커스터마이징](../openapi/customizing-openapi-and-docs-ui.md)에서 다룬다.

## 조건부 OpenAPI

### 보안에 대한 주의

운영 환경에서 문서 UI를 숨기는 것은 API를 보호하는 방법이 **아니다**. 경로 작업은 여전히 그 자리에 있고 보안 결함도 그대로 남는다(일종의 "모호함을 통한 보안"). 대신 다음을 하라.

- 요청 본문과 응답에 잘 정의된 Pydantic 모델 사용
- 의존성으로 권한·역할 구성
- 평문 비밀번호 대신 해시만 저장
- pwdlib, JWT 같은 검증된 암호화 도구 사용([JWT 토큰](../security/oauth2-jwt.md))
- 필요하면 [OAuth2 스코프](../security/oauth2-scopes.md)로 세밀한 권한 제어

### 설정·환경 변수로 끄기

그래도 특정 환경에서 문서를 꺼야 한다면 [pydantic-settings](./settings.md)로 `openapi_url`을 설정값으로 만든다.

```Python
from fastapi import FastAPI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openapi_url: str = "/openapi.json"


settings = Settings()

app = FastAPI(openapi_url=settings.openapi_url)


@app.get("/")
def root():
    return {"message": "Hello World"}
```

환경 변수 `OPENAPI_URL`을 빈 문자열로 실행하면 OpenAPI와 문서 UI가 모두 꺼진다.

```console
$ OPENAPI_URL= uvicorn main:app
```

이제 `/openapi.json`, `/docs`, `/redoc`에 접속하면 `404 Not Found`(`{"detail": "Not Found"}`)가 반환된다.

## 관련 페이지

- [설정과 환경 변수](./settings.md)
- [OpenAPI 확장과 문서 UI 커스터마이징](../openapi/customizing-openapi-and-docs-ui.md)
- [서브 애플리케이션과 프록시](./sub-applications-proxy-and-wsgi.md) — `root_path`가 문서 URL에 미치는 영향
