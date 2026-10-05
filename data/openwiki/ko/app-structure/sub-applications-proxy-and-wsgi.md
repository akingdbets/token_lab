---
type: guide
title: 서브 애플리케이션, 프록시 뒤 실행, WSGI 마운트
description: app.mount()로 독립된 FastAPI 서브 앱(자체 OpenAPI·문서)을 붙이는 방법, Traefik/Nginx 같은 프록시 뒤에서 --forwarded-allow-ips와 root_path(--root-path, FastAPI(root_path=...))를 쓰는 방법, OpenAPI servers와 root_path_in_servers, a2wsgi의 WSGIMiddleware로 Flask·Django를 마운트하는 방법을 설명한다.
tags: [mount, sub-application, proxy, root-path, servers, wsgi, flask]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-ed3d25118ab131bfc4b45b6f
    resource: repo://docs_src/behind_a_proxy/tutorial001_py310.py
  - id: openwiki-source-878a1965f619c0d9fe4e25ad
    resource: repo://docs_src/behind_a_proxy/tutorial002_py310.py
  - id: openwiki-source-99e68b93bef87d611c034629
    resource: repo://docs_src/behind_a_proxy/tutorial003_py310.py
  - id: openwiki-source-effe94f8043a35d0186d780a
    resource: repo://docs_src/behind_a_proxy/tutorial004_py310.py
  - id: openwiki-source-88f50dcab11ba0d187804a87
    resource: repo://docs_src/sub_applications/tutorial001_py310.py
  - id: openwiki-source-21bf9277556b9d32e99e0116
    resource: repo://docs_src/wsgi/tutorial001_py310.py
  - id: openwiki-source-d03ec1ead9cc2906107417f9
    resource: repo://docs/en/docs/advanced/behind-a-proxy.md
  - id: openwiki-source-b21ef06672269e7ba87c1e95
    resource: repo://docs/en/docs/advanced/sub-applications.md
  - id: openwiki-source-a260e848c29a17323d5b58da
    resource: repo://docs/en/docs/advanced/wsgi.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-8d245b8dfa52fb051edbd6f7
    resource: repo://fastapi/middleware/wsgi.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 서브 애플리케이션, 프록시 뒤 실행, WSGI 마운트

이 페이지는 "다른 경로 접두사 아래에서 앱을 동작시키는" 세 가지 상황을 다룬다. 공통 핵심 개념은 ASGI 명세의 **`root_path`**다.

## 서브 애플리케이션 마운트

자체 OpenAPI와 문서 UI를 가진 **완전히 독립된** FastAPI 앱 두 개가 필요하면, 메인 앱에 서브 앱을 "마운트"한다. 마운트된 앱은 해당 경로 아래의 모든 것을 직접 처리한다.

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/app")
def read_main():
    return {"message": "Hello World from main app"}


subapi = FastAPI()


@subapi.get("/sub")
def read_sub():
    return {"message": "Hello World from sub API"}


app.mount("/subapi", subapi)
```

- `http://127.0.0.1:8000/docs` — 메인 앱의 경로 작업만 표시
- `http://127.0.0.1:8000/subapi/docs` — 서브 앱의 경로 작업만 `/subapi` 접두사와 함께 표시

마운트 시 FastAPI(Starlette)는 마운트 경로를 `root_path`로 서브 앱에 전달하므로, 서브 앱의 문서 UI가 올바른 접두사를 사용한다. 서브 앱이 다시 서브 앱을 마운트해도 자동으로 처리된다.

`APIRouter`와의 차이: `include_router()`는 경로 작업을 **하나의** OpenAPI로 합치지만, `mount()`는 격리된 앱을 붙인다([큰 애플리케이션](./bigger-applications.md)). 또한 [lifespan 이벤트](./lifespan-events.md)는 메인 앱에서만 실행되고 마운트된 서브 앱에서는 실행되지 않는다. `StaticFiles`도 같은 `mount()` 메커니즘을 쓴다([정적 파일](../integrations/static-files-templates-frontend.md)).

## 프록시 뒤에서 실행

Traefik이나 Nginx 같은 프록시를 앱 앞에 두는 경우가 많다.

### 프록시 전달 헤더(Forwarded Headers)

프록시는 원래 요청 정보를 다음 헤더로 서버에 전달한다.

- `X-Forwarded-For`: 원래 클라이언트 IP
- `X-Forwarded-Proto`: 원래 프로토콜(`https`)
- `X-Forwarded-Host`: 원래 호스트(`mysuperapp.com`)

서버가 이 헤더를 신뢰하도록 `--forwarded-allow-ips`로 신뢰할 IP를 지정한다(`"*"`는 모든 IP 신뢰).

```console
$ uv run fastapi run --forwarded-allow-ips="*"
```

#### HTTPS 리다이렉트

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/")
def read_items():
    return ["plumbus", "portal gun"]
```

클라이언트가 `/items`로 접근하면 기본적으로 `/items/`로 리다이렉트된다. 전달 헤더를 신뢰하지 않으면 `http://localhost:8000/items/`로 잘못 리다이렉트될 수 있지만, 설정하면 `https://mysuperapp.com/items/`처럼 올바른 공개 URL로 리다이렉트된다. HTTPS 개념은 [배포 개념과 HTTPS](../deployment/deployment-concepts-and-https.md) 참고.

### 경로 접두사를 제거(strip)하는 프록시와 root_path

코드에서는 `/app`으로 선언했지만 프록시가 앱을 `/api/v1` 아래에 노출하고, 서버에 전달하기 전에 접두사를 **제거**하는 구성이 있다.

```
Browser → Proxy (http://0.0.0.0:9999/api/v1/app) → Server (http://127.0.0.1:8000/app)
```

요청 처리 자체는 문제없지만, 문서 UI(브라우저에서 동작)는 `/api/v1/openapi.json`이 아니라 `/openapi.json`을 요청하려 해서 실패한다. 이를 `root_path`로 해결한다.

#### --root-path로 전달

```Python
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}
```

```console
$ uv run fastapi run main.py --forwarded-allow-ips="*" --root-path /api/v1
```

Hypercorn도 `--root-path` 옵션을 지원한다. 현재 `root_path`는 요청마다 ASGI `scope`(`request.scope.get("root_path")`)에서 확인할 수 있다.

#### FastAPI(root_path=...)로 설정

명령줄 옵션을 줄 수 없는 환경이면 앱 생성 시 지정한다. Uvicorn/Hypercorn에 `--root-path`를 넘기는 것과 같다.

```Python
from fastapi import FastAPI, Request

app = FastAPI(root_path="/api/v1")


@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}
```

#### 주의

- 서버(Uvicorn)는 `root_path`를 앱에 전달하는 것 외에는 사용하지 않는다. `http://127.0.0.1:8000/app`으로 직접 접속해도 정상 응답(`"root_path": "/api/v1"` 포함)이 오며, `/api/v1`을 붙이는 것은 프록시의 책임이다.
- 접두사를 제거하는 프록시는 여러 구성 중 하나일 뿐이다. 접두사를 제거하지 않는 프록시라면 `https://myawesomeapp.com/api/v1/app` → `http://127.0.0.1:8000/api/v1/app`처럼 같은 경로로 전달한다.

### Traefik으로 로컬 실험

Traefik 바이너리를 내려받아 `traefik.toml`(포트 9999, `routes.toml` 사용)과 `routes.toml`(`/api/v1` 접두사 제거 후 `http://127.0.0.1:8000`으로 전달)을 구성한 다음 `--root-path /api/v1`로 앱을 실행하면, `http://127.0.0.1:9999/api/v1/app`과 `http://127.0.0.1:9999/api/v1/docs`가 모두 정상 동작한다.

### OpenAPI servers

FastAPI는 `root_path`가 있으면 OpenAPI 스키마의 `servers`에 그 URL을 기본 서버로 넣는다. 그래서 프록시 뒤의 문서 UI가 `/api/v1` 접두사로 API를 호출한다. 실제 구현에서는 `/openapi.json` 요청 시점에 요청 scope의 `root_path`를 읽어, 같은 URL의 서버가 아직 없으면 목록 맨 앞에 `{"url": root_path}`를 삽입한다.

같은 문서 UI로 스테이징과 운영 환경을 모두 호출하려면 `servers`를 추가한다.

```Python
from fastapi import FastAPI, Request

app = FastAPI(
    servers=[
        {"url": "https://stag.example.com", "description": "Staging environment"},
        {"url": "https://prod.example.com", "description": "Production environment"},
    ],
    root_path="/api/v1",
)


@app.get("/app")
def read_main(request: Request):
    return {"message": "Hello World", "root_path": request.scope.get("root_path")}
```

생성된 스키마의 `servers`는 `/api/v1`(자동), `https://stag.example.com`, `https://prod.example.com` 순서가 된다. 문서 UI는 선택한 서버와 통신한다. `servers`를 지정하지 않고 `root_path`가 `/`이면 `servers` 속성은 생략된다(`url: "/"` 단일 서버와 동일).

#### root_path 자동 서버 끄기

```Python
app = FastAPI(
    servers=[
        {"url": "https://stag.example.com", "description": "Staging environment"},
        {"url": "https://prod.example.com", "description": "Production environment"},
    ],
    root_path="/api/v1",
    root_path_in_servers=False,
)
```

### 프록시 + 서브 앱

`root_path`를 쓰는 프록시 뒤에서도 서브 앱을 평소처럼 마운트하면 FastAPI가 `root_path`를 알아서 조합한다.

## WSGI 앱 포함하기(Flask, Django 등)

WSGI 앱은 `WSGIMiddleware`로 감싸서 마운트한다. 이제는 **`a2wsgi` 패키지**의 `WSGIMiddleware`를 사용한다(`uv add a2wsgi`).

```Python
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from flask import Flask, request
from markupsafe import escape

flask_app = Flask(__name__)


@flask_app.route("/")
def flask_main():
    name = request.args.get("name", "World")
    return f"Hello, {escape(name)} from Flask!"


app = FastAPI()


@app.get("/v2")
def read_main():
    return {"message": "Hello World"}


app.mount("/v1", WSGIMiddleware(flask_app))
```

- `/v1/` 아래 요청은 Flask가, 나머지는 FastAPI가 처리한다.
- `http://localhost:8000/v1/` → `Hello, World from Flask!`
- `http://localhost:8000/v2` → `{"message": "Hello World"}`

예전에 권장되던 `fastapi.middleware.wsgi.WSGIMiddleware`는 Starlette의 `WSGIMiddleware`를 그대로 재노출하는 것으로, 이제 **deprecated**다. 사용법은 같으므로 임포트만 `a2wsgi`로 바꾸면 된다.

## 관련 페이지

- [미들웨어와 CORS](../middleware/middleware-and-cors.md) — `TrustedHostMiddleware`, `HTTPSRedirectMiddleware`
- [FastAPI CLI](../getting-started/fastapi-cli-and-debugging.md) — `fastapi run` 옵션
- [Docker와 클라우드 배포](../deployment/docker-and-cloud.md) — 컨테이너를 프록시 뒤에서 실행
