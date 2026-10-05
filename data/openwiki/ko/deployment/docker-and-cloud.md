---
type: guide
title: Docker와 클라우드 배포
description: FastAPI 앱의 Docker 이미지를 처음부터 만드는 방법(Dockerfile, 레이어 캐시, exec 형식 CMD, --proxy-headers, 단일 파일 앱), 컨테이너 환경에서의 HTTPS·재시작·복제·메모리·시작 전 단계 전략, deprecated된 기본 이미지, fastapi deploy로 FastAPI Cloud에 배포하는 방법과 기타 클라우드를 정리한다.
tags: [deployment, docker, containers, kubernetes, fastapi-cloud, cloud]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-ed6347a02d439d7adb60c660
    resource: repo://docs/en/docs/deployment/docker.md
  - id: openwiki-source-05b2dcec8163d7ab916d681f
    resource: repo://docs/en/docs/deployment/fastapicloud.md
  - id: openwiki-source-dc198b5a2f25036adad646d4
    resource: repo://fastapi/cli.py
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# Docker와 클라우드 배포

FastAPI 앱은 보통 **Linux 컨테이너 이미지**(주로 Docker)로 만들어 배포한다. 보안, 재현성, 단순성 등의 장점이 있다. 배포 일반 개념은 [배포 개념, HTTPS, 버전 관리](./deployment-concepts-and-https.md)를 먼저 보면 좋다.

## 컨테이너 기본 개념

- **컨테이너**: 같은 시스템의 다른 컨테이너와 격리된 채 실행되는 경량 환경. 호스트 커널을 공유하므로 가상 머신보다 가볍다.
- **컨테이너 이미지**: 컨테이너에 들어갈 파일·환경 변수·기본 명령을 담은 정적 버전. Docker Hub에 Python 같은 공식 이미지가 있다.
- 컨테이너는 보통 **프로세스 하나**를 실행하며, 그 메인 프로세스가 살아 있는 동안만 실행된다.

## FastAPI용 Docker 이미지 만들기

### 패키지 요구사항

`uv`로 관리한다면 `pyproject.toml`과 `uv.lock`에 의존성이 기록된다.

```console
$ uv add "fastapi[standard]" pydantic
```

아래 Dockerfile은 컨테이너 안에서 `pip`를 쓰므로, 잠긴 의존성을 `requirements.txt`로 내보낸다(uv.lock이 바뀌면 다시 생성).

```console
$ uv export --format requirements-txt --no-dev --no-emit-project --output-file requirements.txt
```

`fastapi` 명령은 `fastapi[standard]`에 포함된 `fastapi-cli`가 제공한다. 설치되어 있지 않으면 `fastapi.cli.main()`이 `pip install "fastapi[standard]"`를 안내하며 `RuntimeError`를 발생시킨다.

### FastAPI 코드

```
.
├── app
│   ├── __init__.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```

```Python
# app/main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

### Dockerfile

```Dockerfile
# 1. 공식 Python 기본 이미지
FROM python:3.14

# 2. 작업 디렉터리
WORKDIR /code

# 3. 요구사항 파일만 먼저 복사 (자주 바뀌지 않아 캐시 활용)
COPY ./requirements.txt /code/requirements.txt

# 4. 의존성 설치 (--no-cache-dir: pip 다운로드 캐시 저장 안 함)
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 5. 가장 자주 바뀌는 앱 코드는 마지막에 복사
COPY ./app /code/app

# 6. fastapi run (내부적으로 Uvicorn 사용)
CMD ["fastapi", "run", "app/main.py", "--port", "80"]
```

#### CMD는 반드시 exec 형식

```Dockerfile
# ✅ 이렇게
CMD ["fastapi", "run", "app/main.py", "--port", "80"]

# ⛔️ 이렇게 하지 말 것 (shell 형식)
CMD fastapi run app/main.py --port 80
```

exec 형식을 써야 FastAPI가 정상적으로 종료(graceful shutdown)하고 [lifespan 이벤트](../app-structure/lifespan-events.md)가 실행된다. shell 형식은 `docker compose`에서 서비스 중지에 10초씩 걸리는 원인이 되기도 한다.

#### TLS 종료 프록시 뒤에서

Nginx나 Traefik 같은 TLS 종료 프록시(로드 밸런서) 뒤에서 실행한다면 `--proxy-headers`를 추가해, 프록시가 보낸 HTTPS 관련 헤더를 Uvicorn이 신뢰하게 한다([프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md)).

```Dockerfile
CMD ["fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80"]
```

#### Docker 캐시

Docker는 Dockerfile 명령마다 레이어를 쌓으며, 파일이 바뀌지 않았으면 이전 레이어를 재사용한다. 한 단계에서 캐시를 쓰면 **다음 단계도** 캐시를 쓸 수 있다. 그래서 자주 바뀌지 않는 `requirements.txt`만 먼저 복사하면, 몇 분 걸릴 수 있는 의존성 설치 단계가 몇 초로 줄어든다. 자주 바뀌는 앱 코드 복사는 Dockerfile 끝부분에 둔다.

### 빌드와 실행

```console
$ docker build -t myimage .
$ docker run -d --name mycontainer -p 80:80 myimage
```

`http://192.168.99.100/items/5?q=somequery`(또는 `http://127.0.0.1/items/5?q=somequery`)에서 `{"item_id": 5, "q": "somequery"}`를 확인하고, `/docs`와 `/redoc`에서 자동 문서를 볼 수 있다.

### 단일 파일 앱

```
.
├── Dockerfile
├── main.py
└── requirements.txt
```

```Dockerfile
FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./main.py /code/

CMD ["fastapi", "run", "main.py", "--port", "80"]
```

`fastapi run`에 파일을 넘기면 패키지가 아닌 단일 파일임을 자동으로 감지해 임포트한다.

## 컨테이너에서의 배포 개념

| 개념 | 컨테이너 환경에서 |
| --- | --- |
| HTTPS | 보통 외부에서 처리. 예: Traefik 컨테이너(Docker·Kubernetes 통합, 인증서 자동 발급) 또는 클라우드 제공자 |
| 시작 시 실행·재시작 | Docker, Docker Compose, Kubernetes, 클라우드 서비스가 담당. Docker는 `--restart` 옵션 |
| 복제 | 클러스터(Kubernetes, Docker Swarm Mode, Nomad 등)라면 **클러스터 수준**에서 복제 |
| 메모리 | 컨테이너당 단일 프로세스면 메모리 사용량이 안정적이라 Kubernetes 등에 메모리 제한·요청을 설정하기 쉽다 |
| 시작 전 단계 | 다중 컨테이너면 별도 컨테이너(Kubernetes Init Container), 단일 컨테이너면 앱 시작 직전에 같은 컨테이너에서 |

### 로드 밸런서와 컨테이너당 단일 프로세스

메인 포트를 리스닝하며 요청을 분배하는 컴포넌트를 **로드 밸런서**라 하며, 보통 TLS 종료 프록시가 이 역할도 한다. Kubernetes 같은 시스템에서는 로드 밸런서가 여러 **동일한 컨테이너**에 요청을 번갈아 분배하고, 각 컨테이너는 **Uvicorn 프로세스 하나**만 실행한다. 이미 클러스터 수준에서 복제하므로 컨테이너 안에 `--workers` 같은 프로세스 매니저를 두는 것은 불필요한 복잡성이다.

### 컨테이너 안에 여러 워커를 두는 특수한 경우

클러스터가 아닌 단일 서버에서 단순한 앱을 실행하거나, Docker Compose로 단일 서버에 배포해 컨테이너 복제와 로드 밸런싱을 쉽게 할 수 없는 경우에는 `--workers`를 쓸 수 있다.

```Dockerfile
FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["fastapi", "run", "app/main.py", "--port", "80", "--workers", "4"]
```

이때 워커 수 × 프로세스당 메모리가 가용 메모리를 넘지 않게 한다. 어느 것도 절대 규칙은 아니며, 각 배포 개념을 기준으로 판단한다.

### 기본 Docker 이미지는 쓰지 말 것

예전 공식 이미지 `tiangolo/uvicorn-gunicorn-fastapi`는 **deprecated**다. Uvicorn이 죽은 워커를 관리하지 못하던 시절 Gunicorn을 함께 쓰려고 만든 것이며, 이제 Uvicorn(과 `fastapi` 명령)이 `--workers`를 지원하므로 위처럼 공식 Python 이미지에서 직접 빌드하는 것이 낫다.

### 이미지 배포 방법

Docker Compose(단일 서버), Kubernetes 클러스터, Docker Swarm Mode, Nomad, 컨테이너 이미지를 받아 배포하는 클라우드 서비스 등. `uv`를 쓴다면 [uv Docker 가이드](https://docs.astral.sh/uv/guides/integration/docker/)도 참고한다.

## FastAPI Cloud

FastAPI를 만든 팀이 만든 [FastAPI Cloud](https://fastapicloud.com)에는 **명령 하나**로 배포할 수 있다.

```console
$ uv run fastapi deploy

Deploying to FastAPI Cloud...

✅ Deployment successful!

🐔 Ready the chicken! Your app is ready at https://myapp.fastapicloud.dev
```

- CLI가 FastAPI 앱을 자동으로 감지해 배포한다. 로그인되어 있지 않으면 브라우저가 열려 인증을 진행한다.
- 앱을 찾을 수 있도록 `pyproject.toml`의 `[tool.fastapi] entrypoint`를 설정해 두는 것이 좋다([큰 애플리케이션](../app-structure/bigger-applications.md)).
- HTTPS, 요청 기반 오토스케일링 복제 등 배포에 필요한 대부분을 처리한다.
- FastAPI Cloud는 *FastAPI and friends* 오픈소스 프로젝트의 주요 후원·자금원이다.

## 기타 클라우드 제공자

FastAPI는 오픈소스이고 표준 기반이므로 사실상 **모든 클라우드 제공자**에 배포할 수 있다. 주요 제공자 대부분이 FastAPI 배포 가이드를 제공한다. FastAPI를 후원하는 제공자로는 [Render](https://docs.render.com/deploy-fastapi), [Railway](https://docs.railway.com/guides/fastapi) 등이 있다.

## 관련 페이지

- [배포 개념, HTTPS, 버전 관리](./deployment-concepts-and-https.md)
- [수동 배포와 서버 워커](./manual-deployment-and-workers.md)
- [설정과 환경 변수](../app-structure/settings.md) — 컨테이너에 환경 변수로 설정 주입
