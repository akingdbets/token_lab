---
type: "참조"
title: "고급 의존성: 파라미터화된 의존성"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-7811fd42dc79501daac1aed0
    resource: repo://docs_src/dependencies/tutorial011_an_py310.py
  - id: openwiki-source-653f9d7538d1f92321ebf90b
    resource: repo://docs_src/dependencies/tutorial013_an_py310.py
  - id: openwiki-source-f4d3e24f1d5c2b648dac6455
    resource: repo://docs_src/dependencies/tutorial014_an_py310.py
  - id: openwiki-source-8ae43a06e68950dd31ba2a17
    resource: repo://docs/en/docs/advanced/advanced-dependencies.md
  - id: openwiki-source-4ba318fa02e49c0255b400c4
    resource: repo://fastapi/param_functions.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 고급 의존성: 파라미터화된 의존성

## 파라미터화된 의존성

지금까지의 의존성은 고정된 함수나 클래스였다. 하지만 비슷한 함수를 여러 개 만들지 않고 의존성에 **설정값을 주입**하고 싶을 때가 있다. 예: 쿼리 파라미터 `q`가 특정 고정 문자열을 포함하는지 검사하되, 그 문자열을 바꿀 수 있게 하기.

### "호출 가능한" 인스턴스

Python에서는 클래스에 `__call__` 메서드를 정의하면 클래스 자체가 아닌 **인스턴스**를 호출할 수 있다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


class FixedContentQueryChecker:
    def __init__(self, fixed_content: str):
        self.fixed_content = fixed_content

    def __call__(self, q: str = ""):
        if q:
            return self.fixed_content in q
        return False


checker = FixedContentQueryChecker("bar")


@app.get("/query-checker/")
async def read_query_check(fixed_content_included: Annotated[bool, Depends(checker)]):
    return {"fixed_content_in_query": fixed_content_included}
```

동작 방식:

- **`__call__`**: FastAPI가 추가 파라미터와 하위 의존성을 찾는 대상이다. 여기서는 쿼리 파라미터 `q`를 요구한다. 요청 시 FastAPI는 `checker(q="somequery")`처럼 호출하고 반환값을 `fixed_content_included`에 넣는다.
- **`__init__`**: FastAPI는 전혀 관여하지 않는다. 우리가 코드에서 직접 호출해 인스턴스를 "파라미터화"한다(`checker.fixed_content == "bar"`).
- `Depends(FixedContentQueryChecker)`가 아니라 **`Depends(checker)`**(인스턴스)를 쓴다. 클래스를 넘기면 `__init__`이 의존성 시그니처가 된다([클래스를 의존성으로](./dependency-injection-basics.md)).

보안 유틸리티(`OAuth2PasswordBearer`, `HTTPBasic`, `APIKeyHeader` 등)가 바로 이 방식으로 구현되어 있다. 생성자에서 `tokenUrl`, `auto_error` 같은 설정을 받고, 인스턴스의 `__call__`이 요청에서 자격 증명을 꺼낸다([보안 기초](../security/oauth2-password-flow.md)).

## yield 의존성의 종료 시점: 기술적 세부 사항

> 대부분은 필요 없는 내용이다. FastAPI 0.121.0 이전 앱을 업그레이드하다 yield 의존성 문제를 겪을 때 유용하다.

yield 의존성의 기본 사용법은 [yield를 사용하는 의존성](./dependencies-with-yield.md)을 먼저 본다.

### scope (0.121.0+)

`Depends(scope=...)`는 `"function"` 또는 `"request"`를 받는다.

- `Depends(scope="function")`: `yield` 이후 종료 코드가 **경로 작업 함수가 끝난 직후, 응답을 보내기 전**에 실행된다.
- `Depends(scope="request")`(기본값): 종료 코드가 **응답을 보낸 후** 실행된다.

### StreamingResponse와 yield (0.118.0에서 복원)

0.106.0~0.117.x에서는 종료 코드가 응답 전송 직전에 실행되어, `StreamingResponse`를 반환하면 스트리밍 도중 이미 DB 세션이 닫혀 사용할 수 없었다. 0.118.0에서 다시 **응답 전송 후** 실행되도록 바뀌었다.

#### 일찍 해제하고 싶은 경우

DB 세션을 사용자 검증에만 쓰고, 응답은 DB를 쓰지 않는 느린 스트림이라면 세션이 불필요하게 오래 유지된다.

```Python
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Field, Session, SQLModel, create_engine

engine = create_engine("postgresql+psycopg://postgres:postgres@localhost/db")


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


app = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


def get_user(user_id: int, session: Annotated[Session, Depends(get_session)]):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=403, detail="Not authorized")


def generate_stream(query: str):
    for ch in query:
        yield ch
        time.sleep(0.1)


@app.get("/generate", dependencies=[Depends(get_user)])
def generate(query: str):
    return StreamingResponse(content=generate_stream(query))
```

여기서 `Session`의 자동 종료(`with` 블록 종료)는 느린 데이터 전송이 모두 끝난 뒤에야 실행된다. SQLModel/SQLAlchemy라면 필요 없어진 시점에 명시적으로 닫아 커넥션을 반환할 수 있다.

```Python
def get_user(user_id: int, session: Annotated[Session, Depends(get_session)]):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=403, detail="Not authorized")
    session.close()
```

`Depends(get_user, scope="function")` 같은 `scope` 설정도 대안이다.

### except와 yield (0.110.0 변경)

0.110.0 이전에는 yield 의존성에서 `except`로 예외를 잡고 다시 발생시키지 않아도 예외가 자동으로 예외 핸들러나 내부 서버 오류 핸들러로 전달되었다. 핸들러 없는 예외로 인한 메모리 소비 문제를 고치고 일반 Python 코드와 일관되게 하기 위해, 이제는 **직접 `raise`해야** 전달된다.

### 백그라운드 작업과 yield (0.106.0 변경)

0.106.0 이전에는 종료 코드가 응답 및 백그라운드 작업 완료 후에 실행되어, yield된 객체를 백그라운드 작업에서도 쓸 수 있었다(대신 종료 코드에서 예외를 발생시키면 이미 예외 핸들러가 실행된 뒤였다).

지금은 백그라운드 작업이 의존성 리소스에 의존하지 않도록 해야 한다.

- 백그라운드 작업 **안에서** 새 DB 세션을 만든다.
- DB 객체 자체 대신 **ID**를 넘기고, 작업 안에서 새 세션으로 다시 조회한다.

백그라운드 작업은 원래 자체 리소스를 가진 독립 로직이므로 이 방식이 더 깔끔하다([백그라운드 작업](../integrations/background-tasks.md)).

## 관련 페이지

- [의존성 주입 기초](./dependency-injection-basics.md)
- [yield를 사용하는 의존성](./dependencies-with-yield.md)
- [스트리밍과 SSE](../responses/streaming-and-sse.md)
- [OAuth2 스코프](../security/oauth2-scopes.md) — `SecurityScopes`를 받는 파라미터화된 보안 의존성
