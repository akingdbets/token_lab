---
type: guide
title: 설정과 환경 변수(pydantic-settings)
description: pydantic-settings의 BaseSettings로 환경 변수를 타입 검증된 설정 객체로 읽고, 별도 모듈·의존성(Depends + @lru_cache)으로 제공하며, .env 파일(SettingsConfigDict(env_file=".env"))을 읽고, 테스트에서 dependency_overrides로 설정을 교체하는 방법을 설명한다.
tags: [settings, pydantic-settings, environment-variables, dotenv, lru-cache]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-188e99702cd491f53e3e07ce
    resource: repo://docs_src/settings/app02_an_py310/main.py
  - id: openwiki-source-cebb973f623815ed295b6cf7
    resource: repo://docs_src/settings/app02_an_py310/test_main.py
  - id: openwiki-source-1e385c4545f62f58e5fa9ba0
    resource: repo://docs_src/settings/app03_an_py310/config.py
  - id: openwiki-source-a1d76c3802220e582db0d953
    resource: repo://docs_src/settings/tutorial001_py310.py
  - id: openwiki-source-dd96f06e91bf8d1fb494d27b
    resource: repo://docs/en/docs/advanced/settings.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 설정과 환경 변수(pydantic-settings)

비밀 키, DB 접속 정보, 이메일 서비스 자격 증명처럼 바뀌거나 민감한 값은 코드 밖 **환경 변수**로 제공하는 것이 일반적이다. 환경 변수 기본 개념은 [환경 변수와 가상 환경](../getting-started/environment-and-virtualenvs.md)을 참고한다.

## 타입과 검증

환경 변수는 운영체제와 다른 프로그램과의 호환성 때문에 **항상 문자열**이다. Python에서 읽은 값은 `str`이므로 타입 변환과 검증은 코드에서 해야 한다. Pydantic의 Settings 관리 기능이 이를 대신해 준다.

## pydantic-settings 설치

```console
$ uv add pydantic-settings
```

`fastapi[all]` 추가 의존성을 설치해도 포함된다.

## Settings 객체 만들기

`BaseSettings`를 상속하고 Pydantic 모델처럼 타입 주석과 기본값으로 필드를 선언한다. `Field()` 등 Pydantic 검증 기능을 모두 쓸 수 있다.

```Python
from fastapi import FastAPI
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50


settings = Settings()
app = FastAPI()


@app.get("/info")
async def info():
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }
```

`Settings()` 인스턴스를 만들 때 환경 변수를 **대소문자 구분 없이** 읽는다. `APP_NAME`이라는 대문자 환경 변수도 `app_name` 필드로 읽히고, 값은 선언한 타입으로 변환·검증된다(`items_per_user`는 `int`). 기본값이 없는 `admin_email`은 필수이므로 환경 변수가 없으면 검증 오류가 난다.

## 서버 실행 시 환경 변수 전달

```console
$ ADMIN_EMAIL="deadpool@example.com" APP_NAME="ChimichangApp" uv run fastapi run main.py
```

PowerShell에서는:

```console
$ $Env:ADMIN_EMAIL = "deadpool@example.com"
$ $Env:APP_NAME = "ChimichangApp"
$ uv run fastapi run main.py
```

Bash에서는 여러 변수를 공백으로 구분해 명령 앞에 둔다.

## 다른 모듈에 설정 두기

```Python
# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50


settings = Settings()
```

```Python
# main.py
from fastapi import FastAPI

from .config import settings

app = FastAPI()


@app.get("/info")
async def info():
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }
```

패키지로 만들려면 `__init__.py`가 필요하다([큰 애플리케이션](./bigger-applications.md)).

## 의존성으로 설정 제공하기

전역 `settings` 객체 대신 의존성으로 제공하면 테스트에서 쉽게 바꿀 수 있다.

```Python
# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50
```

```Python
# main.py
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI

from .config import Settings

app = FastAPI()


@lru_cache
def get_settings():
    return Settings()


@app.get("/info")
async def info(settings: Annotated[Settings, Depends(get_settings)]):
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }
```

### 테스트에서 설정 오버라이드

```Python
# test_main.py
from fastapi.testclient import TestClient

from .config import Settings
from .main import app, get_settings

client = TestClient(app)


def get_settings_override():
    return Settings(admin_email="testing_admin@example.com")


app.dependency_overrides[get_settings] = get_settings_override


def test_app():
    response = client.get("/info")
    data = response.json()
    assert data == {
        "app_name": "Awesome API",
        "admin_email": "testing_admin@example.com",
        "items_per_user": 50,
    }
```

`app.dependency_overrides`는 [테스트 기초](../testing/testing-basics.md)에서 자세히 다룬다.

## .env 파일 읽기

변경이 잦은 설정을 `.env`("dotenv") 파일에 두는 관행이 흔하다. 파일 이름이 `.`으로 시작하므로 macOS/Linux에서 숨김 파일이다. 이 기능은 `python-dotenv` 외부 라이브러리를 사용한다.

```bash
ADMIN_EMAIL="deadpool@example.com"
APP_NAME="ChimichangApp"
```

```Python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Awesome API"
    admin_email: str
    items_per_user: int = 50

    model_config = SettingsConfigDict(env_file=".env")
```

```Python
# main.py
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI

from . import config

app = FastAPI()


@lru_cache
def get_settings():
    return config.Settings()


@app.get("/info")
async def info(settings: Annotated[config.Settings, Depends(get_settings)]):
    ...
```

`model_config`의 `SettingsConfigDict(env_file=".env")`가 읽을 dotenv 파일을 지정한다.

## @lru_cache로 Settings를 한 번만 만들기

`Settings()`를 만들 때마다 `.env` 파일을 다시 읽으므로, 의존성이 요청마다 호출되면 **요청마다 파일을 읽게 된다**. `functools.lru_cache`를 붙이면 첫 호출 때만 객체를 만들고 이후에는 같은 객체를 반환한다.

- `@lru_cache`는 같은 인자 조합에 대해 첫 호출 결과를 저장해 재사용한다. `get_settings()`는 인자가 없으므로 항상 같은 값을 반환한다.
- 결과적으로 **전역 변수처럼 동작하지만**, 의존성 함수이므로 테스트에서 `dependency_overrides`로 쉽게 교체할 수 있다.

## 정리

- `BaseSettings`로 환경 변수를 Pydantic 모델처럼 타입 검증하며 읽는다.
- 의존성으로 제공하면 테스트가 쉬워진다.
- `.env` 파일을 쓸 수 있고, `@lru_cache`로 요청마다 다시 읽지 않게 한다.

## 관련 페이지

- [메타데이터와 문서 URL, 조건부 OpenAPI](./metadata-and-docs-urls.md) — 설정으로 OpenAPI 끄기
- [의존성 주입 기초](../dependencies/dependency-injection-basics.md)
- [Docker와 클라우드 배포](../deployment/docker-and-cloud.md) — 컨테이너 환경 변수
