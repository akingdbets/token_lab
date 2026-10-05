---
type: how-to
title: OpenAPI 확장과 문서 UI 커스터마이징
description: app.openapi()와 openapi_schema 캐시 동작, fastapi.openapi.utils.get_openapi로 스키마를 생성·수정해 app.openapi를 교체하는 방법(x-logo 등), Pydantic v2의 입력/출력 스키마 분리와 separate_input_output_schemas=False, swagger_ui_parameters로 Swagger UI 설정, get_swagger_ui_html/get_redoc_html로 사용자 지정 CDN·자체 호스팅 문서 자산을 쓰는 방법을 설명한다.
tags: [openapi, get-openapi, swagger-ui, redoc, json-schema, self-hosting]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-8a34a13a0fe026887f8f1736
    resource: repo://docs_src/configure_swagger_ui/tutorial001_py310.py
  - id: openwiki-source-669e5ec35aac527f7b1420f0
    resource: repo://docs_src/configure_swagger_ui/tutorial003_py310.py
  - id: openwiki-source-d15c086519783e6d49669186
    resource: repo://docs_src/custom_docs_ui/tutorial001_py310.py
  - id: openwiki-source-cbc675db4a850eabbf8ae464
    resource: repo://docs_src/custom_docs_ui/tutorial002_py310.py
  - id: openwiki-source-27218b8fe711ff478446fffa
    resource: repo://docs_src/extending_openapi/tutorial001_py310.py
  - id: openwiki-source-ee2a28566b2d27a7c248ea1c
    resource: repo://docs_src/separate_openapi_schemas/tutorial002_py310.py
  - id: openwiki-source-bad0099f9c0fe805c4d8d348
    resource: repo://docs/en/docs/how-to/separate-openapi-schemas.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-71c560a9294248da86954ddc
    resource: repo://fastapi/openapi/docs.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# OpenAPI 확장과 문서 UI 커스터마이징

## 기본 동작

- `FastAPI` 인스턴스는 OpenAPI 스키마를 반환하는 `.openapi()` 메서드를 가진다.
- 앱 생성 시 `/openapi.json`(또는 `openapi_url`) 경로 작업이 등록되며, 이 경로는 `.openapi()` 결과를 JSON으로 반환한다(프록시 `root_path`가 있으면 `servers`를 보정).
- `.openapi()`는 `.openapi_schema` 속성에 내용이 있으면 그대로 반환하고, 없으면 `fastapi.openapi.utils.get_openapi()`로 생성해 저장한다. 이 버전에서는 라우트가 변경되면(라우터의 routes version이 바뀌면) 다시 생성한다.

`get_openapi()`의 주요 파라미터:

| 파라미터 | 설명 |
| --- | --- |
| `title` | 문서에 표시되는 제목 |
| `version` | API 버전(예: `2.5.0`) |
| `openapi_version` | OpenAPI 명세 버전, 기본 `3.1.0` |
| `summary` | 짧은 요약(OpenAPI 3.1.0+, FastAPI 0.99.0+) |
| `description` | Markdown 가능한 설명 |
| `routes` | `app.routes`. 포함된 라우터의 경로 작업까지 수집한다 |

그 밖에 `webhooks`, `tags`, `servers`, `separate_input_output_schemas` 등도 받는다. `app.routes`는 포함된 라우터 후보를 포함하는 저수준 라우트 트리이며, `get_openapi()`가 이를 순회해 실제 경로 작업을 모은다.

## 스키마 덮어쓰기

[ReDoc의 `x-logo` 확장](https://github.com/Redocly/redoc/blob/main/docs/redoc-vendor-extensions.md#x-logo)을 추가하는 예:

```Python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI()


@app.get("/items/")
async def read_items():
    return [{"name": "Foo"}]


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Custom title",
        version="2.5.0",
        summary="This is a very custom OpenAPI schema",
        description="Here's a longer description of the custom **OpenAPI** schema",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
```

1. 평소처럼 앱을 작성한다.
2. `custom_openapi()` 안에서 `get_openapi()`로 스키마를 생성한다.
3. 생성된 딕셔너리를 수정한다(`info`에 `x-logo` 추가).
4. `app.openapi_schema`를 **캐시**로 사용해, 문서를 열 때마다 다시 생성하지 않게 한다.
5. `app.openapi = custom_openapi`로 메서드를 교체한다.

`/redoc`에 접속하면 사용자 지정 로고가 보인다. 경로 작업 하나만 수정하려면 `openapi_extra`가 더 간단하다([경로 작업 설정](../app-structure/path-operation-configuration.md)).

## 입력/출력 스키마 분리

Pydantic v2 이후 생성되는 OpenAPI가 더 정확해져, 기본값이 있는 모델은 **입력용과 출력용 두 개의 JSON Schema**를 가질 수 있다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None


app = FastAPI()


@app.post("/items/")
def create_item(item: Item):
    return item


@app.get("/items/")
def read_items() -> list[Item]:
    return [
        Item(
            name="Portal Gun",
            description="Device to travel through the multi-rick-verse",
        ),
        Item(name="Plumbus"),
    ]
```

- **입력**으로 쓸 때: `description`은 기본값 `None`이 있으므로 **필수가 아니다**.
- **출력**으로 쓸 때: 값을 주지 않아도 기본값이 들어가 항상 존재하므로 **필수**(값은 `null`일 수 있음)로 표시된다. 클라이언트는 필드 존재 여부를 확인할 필요가 없다.
- 그래서 OpenAPI의 스키마 목록에 `Item-Input`, `Item-Output` 두 개가 생긴다. 문서와 [자동 생성 클라이언트/SDK](./generate-clients.md)가 더 정확해진다.

### 분리하지 않기

이미 생성된 클라이언트 코드를 당장 바꾸고 싶지 않은 경우처럼, 입력과 출력에 **같은 스키마**가 필요하면 `separate_input_output_schemas=False`를 쓴다(FastAPI 0.102.0+).

```Python
app = FastAPI(separate_input_output_schemas=False)
```

이제 모델의 스키마는 `Item` 하나뿐이며 `description`은 필수가 아니다.

## Swagger UI 설정: swagger_ui_parameters

`FastAPI(swagger_ui_parameters=...)` 또는 `get_swagger_ui_html(swagger_ui_parameters=...)`에 [Swagger UI 설정](https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/) 딕셔너리를 넘긴다. FastAPI가 JSON으로 변환해 Swagger UI에 전달한다.

```Python
# 문법 강조 끄기
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": False})

# 문법 강조 테마 변경
app = FastAPI(swagger_ui_parameters={"syntaxHighlight": {"theme": "obsidian"}})

# 기본값 덮어쓰기: deepLinking 끄기
app = FastAPI(swagger_ui_parameters={"deepLinking": False})
```

FastAPI의 기본 설정(`fastapi.openapi.docs.swagger_ui_default_parameters`):

```Python
{
    "dom_id": "#swagger-ui",
    "layout": "BaseLayout",
    "deepLinking": True,
    "showExtensions": True,
    "showCommonExtensions": True,
}
```

`presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset]` 같은 **JavaScript 전용** 설정(함수·객체)은 Python에서 문자열로 넘길 수 없다. 필요하면 아래처럼 Swagger UI 경로 작업 전체를 직접 만들고 JavaScript를 작성한다. OAuth2 관련 초기화는 `swagger_ui_init_oauth`, 리다이렉트 경로는 `swagger_ui_oauth2_redirect_url`(기본 `/docs/oauth2-redirect`) 파라미터로 설정한다.

## 문서 UI 정적 자산: 사용자 지정 CDN과 자체 호스팅

Swagger UI와 ReDoc은 JavaScript·CSS 파일이 필요하며, 기본적으로 CDN(`cdn.jsdelivr.net`)에서 불러온다. 특정 URL이 막힌 환경이거나 오프라인·내부망에서 동작해야 하면 바꿀 수 있다.

### 사용자 지정 CDN

1. 자동 문서를 끈다: `FastAPI(docs_url=None, redoc_url=None)`
2. `fastapi.openapi.docs`의 내부 함수로 문서 경로 작업을 직접 만든다.

```Python
from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

app = FastAPI(docs_url=None, redoc_url=None)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://unpkg.com/redoc@2/bundles/redoc.standalone.js",
    )


@app.get("/users/{username}")
async def read_user(username: str):
    return {"message": f"Hello {username}"}
```

- `openapi_url`: 문서 HTML이 스키마를 가져올 URL. `app.openapi_url` 사용
- `title`: API 제목
- `oauth2_redirect_url`: 기본값을 쓰려면 `app.swagger_ui_oauth2_redirect_url`
- `swagger_js_url`, `swagger_css_url`, `redoc_js_url`: 자산 URL
- `swagger_ui_redirect` 경로 작업은 OAuth2 제공자와 연동해 인증 후 문서로 돌아올 때 Swagger UI가 사용하는 보조 경로다.

### 자체 호스팅

1. `static/` 디렉터리에 [`swagger-ui-bundle.js`](https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js), [`swagger-ui.css`](https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css), [`redoc.standalone.js`](https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js)를 내려받는다.

```
.
├── app
│   ├── __init__.py
│   ├── main.py
└── static
    ├── redoc.standalone.js
    ├── swagger-ui-bundle.js
    └── swagger-ui.css
```

2. `StaticFiles`를 마운트하고 자산 URL을 앱이 제공하는 경로로 바꾼다.

```Python
from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles

app = FastAPI(docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )
```

`http://127.0.0.1:8000/static/redoc.standalone.js`로 정적 파일이 제공되는지 확인한 뒤, 인터넷 연결 없이도 `/docs`가 동작하는지 확인한다([정적 파일](../integrations/static-files-templates-frontend.md)).

## 관련 페이지

- [메타데이터와 문서 URL](../app-structure/metadata-and-docs-urls.md)
- [스키마 예제 선언](../models/schema-examples.md)
- [OpenAPI 콜백과 웹훅](./callbacks-and-webhooks.md)
- [클라이언트 SDK 생성](./generate-clients.md)
