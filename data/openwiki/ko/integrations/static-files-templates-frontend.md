---
type: guide
title: 정적 파일, 템플릿, 프론트엔드
description: StaticFiles를 app.mount()로 마운트해 정적 파일을 제공하는 방법, Jinja2Templates와 TemplateResponse(request, name, context)·url_for로 HTML을 렌더링하는 방법, app.frontend()/router.frontend()로 Vite·Astro 등의 정적 프론트엔드 빌드를 낮은 우선순위 라우트로 제공하는 방법(fallback="auto"/"index.html"/"404.html"/None, check_dir, 의존성·미들웨어 적용)을 설명한다.
tags: [static-files, templates, jinja2, frontend, spa, mount]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-fbba5f548ebe256a7173926e
    resource: repo://docs_src/frontend/tutorial001_py310.py
  - id: openwiki-source-de9609b228fdc8999d60dc41
    resource: repo://docs_src/frontend/tutorial002_py310.py
  - id: openwiki-source-61cabf4804d33ca7cac37dd8
    resource: repo://docs_src/frontend/tutorial004_py310.py
  - id: openwiki-source-2141f1b39b70b1adf38edf87
    resource: repo://docs_src/frontend/tutorial005_py310.py
  - id: openwiki-source-f9d6fd286f37fcfc2238632a
    resource: repo://docs_src/frontend/tutorial006_py310.py
  - id: openwiki-source-1a1b474cd7a5d78df4df498e
    resource: repo://docs_src/static_files/tutorial001_py310.py
  - id: openwiki-source-ed1031cd9afb79ebd46b739a
    resource: repo://docs_src/templates/templates/item.html
  - id: openwiki-source-7fd958075fa7d6f7fa668120
    resource: repo://docs_src/templates/tutorial001_py310.py
  - id: openwiki-source-3edfa959d42b9f564280c905
    resource: repo://docs/en/docs/tutorial/frontend.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-a2658bf7fa1d2b96ae2bef15
    resource: repo://fastapi/staticfiles.py
  - id: openwiki-source-8d07ead49806eddd070fe43f
    resource: repo://fastapi/templating.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 정적 파일, 템플릿, 프론트엔드

## 정적 파일: StaticFiles

디렉터리의 정적 파일을 자동으로 제공한다.

```Python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
```

- 첫 번째 `"/static"`: 이 "서브 애플리케이션"이 마운트될 경로. `/static`으로 시작하는 모든 경로를 처리한다.
- `directory="static"`: 정적 파일이 들어 있는 디렉터리 이름
- `name="static"`: FastAPI 내부(예: 템플릿의 `url_for`)에서 사용할 이름
- 세 값 모두 앱에 맞게 바꿔도 된다.

`fastapi.staticfiles.StaticFiles`는 편의상 `starlette.staticfiles.StaticFiles`를 그대로 재노출한 것이다. 자세한 옵션은 [Starlette Static Files 문서](https://starlette.dev/staticfiles/)를 참고한다.

### 마운트란

"마운트"는 특정 경로에 완전히 **독립된** 애플리케이션을 붙여 그 아래 모든 하위 경로를 처리하게 하는 것이다. `APIRouter`와 달리 메인 앱의 OpenAPI와 문서에는 마운트된 앱의 내용이 포함되지 않는다([서브 애플리케이션](../app-structure/sub-applications-proxy-and-wsgi.md)).

> 프론트엔드를 호스팅하려면 `StaticFiles` 대신 아래의 `app.frontend()`를 쓴다. 내부적으로 `StaticFiles`를 사용하면서 클라이언트 라우팅 처리 같은 이점이 있다.

## 템플릿: Jinja2Templates

FastAPI는 어떤 템플릿 엔진이든 쓸 수 있으며, Flask 등에서 쓰는 Jinja2를 쉽게 설정하는 도구(Starlette 제공)가 있다.

```console
$ uv add jinja2
```

```Python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/items/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse(
        request=request, name="item.html", context={"id": id}
    )
```

1. `Jinja2Templates`를 임포트하고 재사용할 `templates` 객체를 만든다.
2. 템플릿을 반환할 경로 작업에 `Request` 파라미터를 선언한다.
3. `templates.TemplateResponse()`에 `request`, 템플릿 이름 `name`, 템플릿에서 쓸 키-값 `context` 딕셔너리를 넘겨 반환한다.

- `response_class=HTMLResponse`를 선언하면 문서 UI가 응답이 HTML임을 안다([커스텀 응답](../responses/custom-responses.md)).
- FastAPI 0.108.0/Starlette 0.29.0 이전에는 `name`이 첫 번째 인자였고, 더 이전에는 `request`를 context 딕셔너리 안에 넣었다.
- `fastapi.templating.Jinja2Templates`는 `starlette.templating.Jinja2Templates`의 재노출이다.

### 템플릿 작성

`templates/item.html`:

```jinja
<html>
<head>
    <title>Item Details</title>
    <link href="{{ url_for('static', path='/styles.css') }}" rel="stylesheet">
</head>
<body>
    <h1><a href="{{ url_for('read_item', id=id) }}">Item ID: {{ id }}</a></h1>
</body>
</html>
```

- `{{ id }}`: context의 `{"id": id}` 값. ID가 `42`면 `Item ID: 42`로 렌더링된다.
- `url_for('read_item', id=id)`: 경로 작업 함수 이름과 그 함수의 인자로 URL을 만든다. `read_item(id=42)`가 처리할 URL, 즉 `/items/42` 링크가 생성된다.
- `url_for('static', path='/styles.css')`: `name="static"`으로 마운트한 `StaticFiles`의 `/static/styles.css` URL을 만든다.

```css
/* static/styles.css */
h1 {
    color: green;
}
```

템플릿 테스트 등은 [Starlette Templates 문서](https://starlette.dev/templates/)를 참고한다.

## 프론트엔드: app.frontend()

React+Vite, TanStack Router, Astro, Vue, Svelte, Angular, Solid처럼 `npm run build`로 정적 파일(예: `./dist/`)을 생성하는 프론트엔드를 `app.frontend()`(또는 `router.frontend()`)로 제공한다.

```text
.
├── pyproject.toml
├── app
│   ├── __init__.py
│   └── main.py
└── dist
    ├── index.html
    └── assets
        └── app.js
```

```Python
from fastapi import FastAPI

app = FastAPI()

app.frontend("/", directory="dist")
```

- `/assets/app.js` 요청은 `dist/assets/app.js`를 제공한다.
- 프론트엔드 라우트는 **낮은 우선순위**로 등록된다. FastAPI는 경로 작업을 먼저 확인하고, 일반 라우트가 하나도 일치하지 않을 때만 프론트엔드 파일을 찾는다. 그래서 같은 경로의 경로 작업이 있으면 **경로 작업이 이긴다**.
- 서버 사이드 렌더링은 하지 않는다. 이미 빌드된 정적 파일만 제공한다.

### 시그니처

```Python
app.frontend(
    path: str,
    *,
    directory: str | os.PathLike[str],
    fallback: Literal["auto", "index.html", "404.html"] | None = "auto",
    check_dir: bool | Literal["auto"] = "auto",
)
```

### fallback: 없는 경로 처리

| 값 | 동작 |
| --- | --- |
| `"auto"`(기본) | 디렉터리에 `404.html`이 있으면 그것을 404 상태로 제공. 없고 `index.html`이 있으면 브라우저 탐색 요청에 `index.html` 제공 |
| `"index.html"` | 클라이언트 라우팅(SPA)용. `/dashboard/settings` 같은 가상 경로에 `index.html` 제공 |
| `"404.html"` | 정적 `404.html`을 **상태 코드 404**로 제공(Astro처럼 페이지별 HTML을 생성하는 도구용) |
| `None` | 폴백 없음, 일반 404 |

```Python
app.frontend("/", directory="dist", fallback="index.html")
app.frontend("/", directory="dist", fallback="404.html")
app.frontend("/", directory="dist", fallback=None)
```

`index.html` 폴백은 `Accept: text/html` 또는 `Accept: application/xhtml+xml`을 명시한 `GET`/`HEAD` 요청(일반적인 브라우저 탐색)에만 적용된다. 없는 JavaScript·CSS·이미지는 여전히 `404`이며, 프론트엔드 폴백에만 일치하는 `POST`/`PUT` 등도 `404`를 반환한다.

### check_dir: 디렉터리 존재 확인

- `"auto"`(기본): `FASTAPI_ENV`가 `development`이면 빌드 디렉터리가 없어도 **경고만** 한다(`fastapi dev`가 이 값을 설정하므로 프론트엔드 빌드 전에 백엔드를 띄울 수 있다). 그 밖의 환경에서는 앱 생성 시 **오류**를 발생시켜, 프론트엔드 파일 없이 배포하는 실수를 조기에 잡는다([FastAPI CLI](../getting-started/fastapi-cli-and-debugging.md)).
- `True`: 항상 앱 생성 시 확인한다.
- `False`: 앱 생성 시 확인하지 않는다(앱 객체 생성 후 별도 빌드 단계에서 파일이 만들어지는 경우). 요청 처리 시점에도 디렉터리가 없으면 그때 오류가 난다.

```Python
app.frontend("/", directory="dist", check_dir=False)
```

### APIRouter와 함께

```Python
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

router.frontend("/", directory="dist", fallback="index.html")
app.include_router(router, prefix="/app")
```

프론트엔드가 `/app` 아래에서 제공된다. 다른 라우터의 경로 작업을 포함해 일반 경로 작업이 여전히 우선한다.

### 의존성과 미들웨어

프론트엔드 응답도 일반 FastAPI 앱 안에서 실행되므로 HTTP [미들웨어](../middleware/middleware-and-cors.md)가 적용된다. 앱·`APIRouter`·`include_router()`의 [의존성](../dependencies/decorator-and-global-dependencies.md)도 적용되어, 쿠키 인증 등으로 프론트엔드를 보호할 수 있다. 의존성에서 응답 헤더를 바꾸거나 백그라운드 작업을 추가할 수도 있다.

## 관련 페이지

- [서브 애플리케이션과 마운트](../app-structure/sub-applications-proxy-and-wsgi.md)
- [커스텀 응답](../responses/custom-responses.md) — `HTMLResponse`, `FileResponse`
- [Request 객체 직접 사용](../request/using-request-directly.md)
