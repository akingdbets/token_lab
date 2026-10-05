---
type: guide
title: 환경 변수와 가상 환경
description: uv로 FastAPI 프로젝트와 가상 환경을 만들고 fastapi[standard]를 설치하는 방법, 설치 추가 옵션(standard, standard-no-fastapi-cloud-cli, all, opentelemetry)에 포함되는 패키지, 환경 변수의 개념과 PATH, 앱 설정에 환경 변수를 쓰는 방법을 정리한다.
tags: [virtual-environment, uv, installation, environment-variables, extras]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-2a4258075d06ec0b26b7e5f9
    resource: repo://docs/en/docs/environment-variables.md
  - id: openwiki-source-7ee7d971f429ba15850f3e46
    resource: repo://docs/en/docs/virtual-environments.md
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 환경 변수와 가상 환경

## 가상 환경

Python 프로젝트마다 설치 패키지를 격리하려면 **가상 환경**을 사용한다. FastAPI 문서는 프로젝트·의존성·가상 환경 관리를 위해 [uv](https://docs.astral.sh/uv/)를 권장한다.

### 프로젝트 만들기

[공식 설치 가이드](https://docs.astral.sh/uv/getting-started/installation/)로 `uv`를 설치한 뒤:

```console
$ uv init awesome-project --bare
$ cd awesome-project
$ uv add "fastapi[standard]"
```

- `uv`는 프로젝트용 가상 환경(`.venv`)을 **자동으로** 만든다. 직접 만들거나 활성화할 필요가 없다.
- 프로젝트 환경 안에서 명령을 실행할 때는 `uv run`을 쓴다.

```console
$ uv run fastapi dev
```

- 직접 의존성은 `pyproject.toml`에, 정확히 해석된 버전은 `uv.lock`에 기록된다([Docker 배포](../deployment/docker-and-cloud.md)에서 `requirements.txt`로 내보내는 방법 참고).

`uv` 대신 표준 `python -m venv .venv`로 가상 환경을 만들고 활성화(Linux/macOS: `source .venv/bin/activate`, Windows PowerShell: `.venv\Scripts\Activate.ps1`)한 뒤 `pip install "fastapi[standard]"`로 설치하는 방법도 있다. 내부 동작은 [Virtual Environments 가이드](https://tiangolo.com/guides/virtual-environments/)에 자세히 설명되어 있다.

### 설치 추가 옵션(extras)

FastAPI 자체의 필수 의존성은 `starlette`, `pydantic`, `typing-extensions`, `typing-inspection`, `annotated-doc`, `opentelemetry-api`뿐이며, Python 3.10 이상이 필요하다. 자주 쓰는 기능의 의존성은 추가 옵션으로 설치한다.

| 추가 옵션 | 포함 내용 |
| --- | --- |
| `fastapi[standard]` | `fastapi-cli[standard]`(`fastapi` 명령, FastAPI Cloud CLI 포함), `uvicorn[standard]`, `httpx`(TestClient), `jinja2`(템플릿), `python-multipart`(폼·파일), `email-validator`, `pydantic-settings`, `pydantic-extra-types`, OpenTelemetry SDK/OTLP exporter 등 |
| `fastapi[standard-no-fastapi-cloud-cli]` | `standard`와 같지만 FastAPI Cloud CLI 제외 |
| `fastapi[all]` | `standard` 구성 + `itsdangerous`(Starlette `SessionMiddleware`), `pyyaml` |
| `fastapi[opentelemetry]` | OpenTelemetry SDK와 OTLP HTTP exporter만 |

`fastapi` 콘솔 스크립트는 `fastapi.cli:main`을 가리키며, `fastapi-cli`가 없으면 `fastapi[standard]` 설치를 안내하는 오류를 낸다([FastAPI CLI](./fastapi-cli-and-debugging.md)).

필요한 기능별로:

- 폼/파일 업로드 → `python-multipart` ([폼과 파일](../request/forms-and-files.md))
- `TestClient` → `httpx` ([테스트](../testing/testing-basics.md))
- `Jinja2Templates` → `jinja2` ([템플릿](../integrations/static-files-templates-frontend.md))
- `EmailStr` → `email-validator`
- `BaseSettings` → `pydantic-settings` ([설정](../app-structure/settings.md))

## 환경 변수

**환경 변수**(env var)는 Python 코드 밖, 운영체제에 존재하며 애플리케이션과 다른 프로그램이 읽을 수 있는 값이다. FastAPI 앱은 DB URL, 이메일 자격 증명, 비밀 키 같은 설정을 환경 변수로 받는 경우가 많다.

```console
# Linux/macOS (Bash): 명령 하나에만 적용
$ MY_NAME="Wade Wilson" uv run python main.py

# Windows PowerShell
$ $Env:MY_NAME = "Wade Wilson"
```

```Python
import os

name = os.getenv("MY_NAME", "World")
print(f"Hello {name} from Python")
```

- 환경 변수 값은 항상 **문자열**이다. 타입 변환·검증은 코드에서 해야 하며, FastAPI 앱에서는 pydantic-settings의 `BaseSettings`가 이를 처리한다([설정과 환경 변수](../app-structure/settings.md)).
- **`PATH`**는 운영체제가 실행 파일(예: `python`, `fastapi`)을 찾을 디렉터리 목록이다. 가상 환경을 활성화하면 가상 환경의 `bin`(Windows는 `Scripts`) 디렉터리가 `PATH` 앞에 추가되어, 그 환경의 `python`과 `fastapi`가 먼저 실행된다. `uv run`은 활성화 없이 같은 효과를 낸다.

크로스 플랫폼 상세 설명은 [Environment Variables 가이드](https://tiangolo.com/guides/environment-variables/)를 참고한다.

## 관련 페이지

- [빠른 시작](../quickstart.md)
- [FastAPI CLI와 디버깅](./fastapi-cli-and-debugging.md)
- [설정과 환경 변수(pydantic-settings)](../app-structure/settings.md)
