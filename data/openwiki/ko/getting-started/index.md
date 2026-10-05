# 파일

- [환경 변수와 가상 환경](environment-and-virtualenvs.md) - uv로 FastAPI 프로젝트와 가상 환경을 만들고 fastapi[standard]를 설치하는 방법, 설치 추가 옵션(standard, standard-no-fastapi-cloud-cli, all, opentelemetry)에 포함되는 패키지, 환경 변수의 개념과 PATH, 앱 설정에 환경 변수를 쓰는 방법을 정리한다.
- [FastAPI CLI와 디버깅](fastapi-cli-and-debugging.md) - fastapi dev(개발 모드, 자동 리로드, 127.0.0.1)와 fastapi run(운영 모드, 0.0.0.0) 명령, FASTAPI_ENV 환경 변수, 앱 자동 탐지와 pyproject.toml의 [tool.fastapi] entrypoint, 경로·--entrypoint 옵션, uvicorn.run()으로 VS Code·PyCharm 디버거를 연결하는 방법을 설명한다.
- [첫 단계: FastAPI 앱과 경로 작업](first-steps.md)
- [Python 타입 힌트와 async/await](python-types-and-async.md) - FastAPI가 기반으로 하는 Python 타입 힌트(단순 타입, list/tuple/set/dict 제네릭, | 유니언과 None, 클래스, Pydantic 모델, Annotated 메타데이터)와 Union vs Optional, FastAPI가 async def와 def 경로 작업·의존성을 어떻게 실행하는지(이벤트 루프 vs 스레드풀)와 언제 무엇을 써야 하는지 설명한다.
