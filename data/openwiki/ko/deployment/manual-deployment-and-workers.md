---
type: guide
title: 수동 배포와 서버 워커
description: fastapi run 명령으로 운영 서버를 실행하는 방법, ASGI 서버(Uvicorn, Hypercorn, Daphne, Granian) 선택, uvicorn[standard] 설치와 uvicorn main:app 직접 실행, 운영에서 --reload를 쓰지 말아야 하는 이유, --workers로 다중 워커 프로세스를 띄우는 방법을 설명한다.
tags: [deployment, fastapi-run, uvicorn, asgi-server, workers]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-8475fe88ce83cde8cb6ff8c8
    resource: repo://docs/en/docs/deployment/manually.md
  - id: openwiki-source-522eb3366590e7fcffb51437
    resource: repo://docs/en/docs/deployment/server-workers.md
  - id: openwiki-source-dc198b5a2f25036adad646d4
    resource: repo://fastapi/cli.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 수동 배포와 서버 워커

## fastapi run 명령

간단히 말하면, 운영 환경에서는 `fastapi run`으로 앱을 제공한다.

```console
$ fastapi run main.py

  FastAPI   Starting production server 🚀

             Searching for package file structure from directories
             with __init__.py files
             Importing from /home/user/code/awesomeapp

    module   🐍 main.py

      code   Importing the FastAPI app object from the module with
             the following code:

             from main import app

       app   Using import string: main:app

    server   Server started at http://0.0.0.0:8000
    server   Documentation at http://0.0.0.0:8000/docs
```

대부분의 경우 이것으로 충분하며, 컨테이너나 서버에서 앱을 시작할 때 그대로 쓸 수 있다. `fastapi dev`와의 차이(자동 리로드, 리스닝 주소)는 [FastAPI CLI와 디버깅](../getting-started/fastapi-cli-and-debugging.md)을 참고한다. `fastapi` 명령은 `fastapi[standard]`에 포함된 `fastapi-cli` 패키지가 제공한다.

## ASGI 서버

FastAPI는 **ASGI**(Asynchronous Server Gateway Interface) 웹 프레임워크다. 원격 머신에서 실행하려면 ASGI 서버 프로그램이 필요하며, `fastapi` 명령은 기본으로 **Uvicorn**을 사용한다.

| 서버 | 특징 |
| --- | --- |
| [Uvicorn](https://uvicorn.dev) | 고성능 ASGI 서버(기본) |
| [Hypercorn](https://hypercorn.readthedocs.io/) | HTTP/2, Trio 지원 등 |
| [Daphne](https://github.com/django/daphne) | Django Channels용 ASGI 서버 |
| [Granian](https://github.com/emmett-framework/granian) | Rust로 작성된 Python 앱용 HTTP 서버 |

### "서버"라는 용어

"서버"는 원격/클라우드 **머신**(물리·가상, VM, 노드)과 그 위에서 실행되는 **프로그램**(예: Uvicorn) 둘 다를 가리킬 수 있다.

## 서버 프로그램 직접 설치·실행

FastAPI를 `fastapi[standard]`로 설치하면 `uvicorn[standard]`가 함께 설치된다. 직접 추가하려면:

```console
$ uv add "uvicorn[standard]"
```

`standard` 추가 옵션은 `asyncio`의 고성능 대체제인 `uvloop` 등 권장 의존성을 설치한다.

ASGI 서버를 직접 실행할 때는 **임포트 문자열**을 넘긴다.

```console
$ uv run uvicorn main:app --host 0.0.0.0 --port 80
```

- `main`: `main.py` 파일(모듈)
- `app`: `main.py` 안에서 `app = FastAPI()`로 만든 객체
- 즉 `from main import app`과 같다.

> **주의:** `--reload`는 개발에는 유용하지만 자원을 훨씬 많이 쓰고 불안정하다. **운영 환경에서 사용하지 말 것.**

위 예시들은 모든 IP(`0.0.0.0`)의 지정 포트에서 **단일 프로세스**를 실행한다. HTTPS, 시작 시 실행, 재시작, 복제, 메모리, 시작 전 단계는 별도로 처리해야 한다([배포 개념](./deployment-concepts-and-https.md)).

## 서버 워커: --workers

여러 CPU 코어를 활용하고 더 많은 요청을 처리하려면 **워커 프로세스**를 여러 개 띄운다.

`fastapi` 명령:

```console
$ fastapi run --workers 4 main.py
```

`uvicorn` 명령:

```console
$ uv run uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

`--workers 4`는 Uvicorn이 워커 프로세스 4개를 시작하게 한다. 로그에 부모 프로세스(**프로세스 매니저**)의 PID와 각 워커 프로세스의 PID가 표시된다. 프로세스 매니저가 포트를 리스닝하고 워커들에게 요청을 전달한다.

### 워커가 해결하는 것과 해결하지 않는 것

- 주로 **복제**(병렬 실행)를 해결하고, 죽은 워커를 다시 띄우므로 **재시작**도 일부 도와준다.
- HTTPS, 시작 시 실행, 메모리(워커마다 메모리를 따로 사용), 시작 전 단계는 여전히 직접 처리해야 한다.
- 워커마다 [lifespan](../app-structure/lifespan-events.md)이 따로 실행된다는 점에 유의한다(프로세스 간 메모리를 공유하지 않음).

### 컨테이너와의 관계

Docker나 Kubernetes를 쓴다면 보통 **컨테이너당 Uvicorn 프로세스 하나**를 실행하고 복제는 클러스터 수준에서 처리한다. 즉 Kubernetes에서는 `--workers`를 쓰지 않는 것이 일반적이다([Docker와 클라우드 배포](./docker-and-cloud.md)).

## 관련 페이지

- [FastAPI CLI와 디버깅](../getting-started/fastapi-cli-and-debugging.md)
- [배포 개념, HTTPS, 버전 관리](./deployment-concepts-and-https.md)
- [Docker와 클라우드 배포](./docker-and-cloud.md)
- [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md) — `--forwarded-allow-ips`, `--root-path`
