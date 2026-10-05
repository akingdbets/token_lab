---
type: guide
title: FastAPI CLI와 디버깅
description: fastapi dev(개발 모드, 자동 리로드, 127.0.0.1)와 fastapi run(운영 모드, 0.0.0.0) 명령, FASTAPI_ENV 환경 변수, 앱 자동 탐지와 pyproject.toml의 [tool.fastapi] entrypoint, 경로·--entrypoint 옵션, uvicorn.run()으로 VS Code·PyCharm 디버거를 연결하는 방법을 설명한다.
tags: [cli, fastapi-dev, fastapi-run, entrypoint, debugging, uvicorn]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-a63798837acc79e7e4562614
    resource: repo://docs_src/debugging/tutorial001_py310.py
  - id: openwiki-source-9bc15a21c009b14775a3dd72
    resource: repo://docs/en/docs/fastapi-cli.md
  - id: openwiki-source-458ed7579bfde8c11398b9a4
    resource: repo://fastapi/__main__.py
  - id: openwiki-source-dc198b5a2f25036adad646d4
    resource: repo://fastapi/cli.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# FastAPI CLI와 디버깅

## FastAPI CLI

**FastAPI CLI**는 FastAPI 앱을 실행하고 프로젝트를 관리하는 명령줄 프로그램이다. `uv add "fastapi[standard]"`로 설치하면 `fastapi` 명령이 함께 설치된다(`fastapi-cli` 패키지가 제공하며, `fastapi` 콘솔 스크립트는 `fastapi.cli:main`을 호출한다). `fastapi-cli`가 없으면 `fastapi.cli.main()`이 `pip install "fastapi[standard]"`를 안내하고 `RuntimeError`를 발생시킨다. `python -m fastapi`도 같은 `main()`을 호출한다.

내부적으로 FastAPI CLI는 고성능 ASGI 서버 [Uvicorn](https://uvicorn.dev)을 사용한다.

### fastapi dev

```console
$ fastapi dev

   FastAPI   Starting development server 🚀

             Searching for package file structure from directories with
             __init__.py files
             Importing from /home/user/code/awesomeapp

    module   🐍 main.py

      code   Importing the FastAPI app object from the module with the
             following code:

             from main import app

       app   Using import string: main:app

    server   Server started at http://127.0.0.1:8000
    server   Documentation at http://127.0.0.1:8000/docs

       tip   Running in development mode, for production use:
             fastapi run
```

- **개발 모드**를 시작한다.
- **자동 리로드**가 기본으로 켜져 코드 변경 시 서버가 다시 시작된다. 자원을 많이 쓰고 덜 안정적이므로 개발에서만 쓴다.
- `127.0.0.1`(자기 자신만 접근 가능한 `localhost`)에서 리스닝한다.
- 앱을 임포트하기 **전에** `FASTAPI_ENV` 환경 변수를 `development`로 설정한다. 이미 설정되어 있으면 기존 값(예: `staging`)을 유지한다. 앱 시작 코드에서 개발용 동작을 선택할 때 활용할 수 있다.

### fastapi run

- **운영 모드**로 시작한다. 자동 리로드는 **꺼져** 있다.
- `0.0.0.0`(사용 가능한 모든 IP)에서 리스닝하므로 머신에 접근 가능한 누구나 접속할 수 있다. 컨테이너 등 운영 환경에서 일반적인 방식이다.
- `FASTAPI_ENV`는 **변경하지 않는다**. 앱이 운영 모드를 감지해야 한다면 `FASTAPI_ENV=production`을 직접 설정한다(관례적인 값은 `development`, `production`).
- 보통 그 앞에 HTTPS를 처리하는 종료 프록시를 둔다([배포 개념](../deployment/deployment-concepts-and-https.md)). 워커·프록시 옵션은 [수동 배포와 서버 워커](../deployment/manual-deployment-and-workers.md)를 참고한다.

## 앱 탐지와 엔트리포인트

`fastapi` 명령은 기본적으로 `main.py` 파일(또는 몇 가지 변형)의 `app` 객체를 자동으로 찾는다. `__init__.py`가 있는 디렉터리를 따라 올라가며 패키지 구조를 탐색해 올바른 임포트 문자열(예: `main:app`)을 만든다.

### pyproject.toml에서 엔트리포인트 설정(권장)

```toml
[tool.fastapi]
entrypoint = "main:app"
```

이는 `from main import app`과 같다. 다음과 같은 구조라면:

```
.
├── backend
│   ├── main.py
│   ├── __init__.py
```

```toml
[tool.fastapi]
entrypoint = "backend.main:app"
```

즉 `from backend.main import app`이다.

### 경로 또는 --entrypoint 옵션

```console
$ uv run fastapi dev main.py
$ uv run fastapi dev --entrypoint main:app
```

둘 다 동작하지만 매번 기억해서 넘겨야 하고, [VS Code 확장](../about/features-and-ecosystem.md)이나 FastAPI Cloud 같은 다른 도구는 이를 알 수 없다. 그래서 `pyproject.toml`의 `entrypoint`를 권장한다.

## 디버깅

VS Code나 PyCharm 같은 에디터의 디버거를 연결할 수 있다. 앱 파일에서 `uvicorn`을 직접 임포트해 실행한다.

```Python
import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    a = "a"
    b = "b" + a
    return {"hello world": b}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### `__name__ == "__main__"`의 의미

- `uv run python myapp.py`처럼 파일을 **직접 실행**하면 Python이 자동으로 만드는 `__name__` 변수가 `"__main__"`이 되어 `uvicorn.run(...)`이 실행된다.
- 다른 파일에서 `from myapp import app`으로 **임포트**하면 `__name__`이 `"__main__"`이 아니므로 서버가 시작되지 않는다.

### 디버거로 실행

Uvicorn을 코드에서 직접 실행하므로 디버거에서 Python 프로그램을 바로 실행할 수 있다.

- **VS Code**: "Debug" 패널 → "Add configuration..." → "Python" 선택 → "`Python: Current File (Integrated Terminal)`" 옵션으로 실행
- **PyCharm**: "Run" 메뉴 → "Debug..." → 디버그할 파일(`main.py`) 선택

서버가 시작되고 중단점에서 멈춘다.

## 관련 페이지

- [첫 단계](./first-steps.md)
- [환경 변수와 가상 환경](./environment-and-virtualenvs.md)
- [큰 애플리케이션](../app-structure/bigger-applications.md) — 패키지 구조와 entrypoint
- [수동 배포와 서버 워커](../deployment/manual-deployment-and-workers.md)
