---
type: guide
title: HTTP Basic, API 키, 기타 보안 스킴
description: fastapi.security의 HTTPBasic/HTTPBasicCredentials로 HTTP Basic 인증을 하고 secrets.compare_digest로 타이밍 공격을 막는 방법, APIKeyHeader·APIKeyQuery·APIKeyCookie, HTTPBearer/HTTPAuthorizationCredentials, HTTPDigest, OpenIdConnect 스텁, auto_error=False로 선택적 인증, 401 응답과 WWW-Authenticate 헤더, OpenAPI 보안 스킴 문서화를 설명한다.
tags: [security, http-basic, api-key, bearer, openid-connect, auto-error, timing-attack]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-7bf5fd73d6fb6fd9bed45c83
    resource: repo://docs_src/security/tutorial006_an_py310.py
  - id: openwiki-source-f04305db4b88ede0ab5c7b4f
    resource: repo://docs_src/security/tutorial007_an_py310.py
  - id: openwiki-source-699fc43e71296fb54b4bd611
    resource: repo://docs/en/docs/advanced/security/http-basic-auth.md
  - id: openwiki-source-0a67b8cf70cd1af161c29b71
    resource: repo://fastapi/security/__init__.py
  - id: openwiki-source-49bd73afdc3d5ffb141e5828
    resource: repo://fastapi/security/api_key.py
  - id: openwiki-source-c3a2665619211e35f840a799
    resource: repo://fastapi/security/http.py
  - id: openwiki-source-198af69fc823028291344cc6
    resource: repo://fastapi/security/open_id_connect_url.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# HTTP Basic, API 키, 기타 보안 스킴

`fastapi.security`의 보안 클래스들은 모두 **호출 가능한 인스턴스**로, `Depends()`에 넣으면 요청에서 자격 증명을 꺼내 반환하고 OpenAPI에 보안 스킴을 등록한다(문서 UI의 "Authorize" 버튼). 이 방식은 [파라미터화된 의존성](../dependencies/advanced-dependencies.md)과 같다.

`fastapi.security`가 제공하는 클래스: `APIKeyCookie`, `APIKeyHeader`, `APIKeyQuery`, `HTTPAuthorizationCredentials`, `HTTPBasic`, `HTTPBasicCredentials`, `HTTPBearer`, `HTTPDigest`, `OAuth2`, `OAuth2AuthorizationCodeBearer`, `OAuth2PasswordBearer`, `OAuth2PasswordRequestForm`, `OAuth2PasswordRequestFormStrict`, `SecurityScopes`, `OpenIdConnect`. OAuth2 계열은 [OAuth2 비밀번호 흐름](./oauth2-password-flow.md)에서 다룬다.

## HTTP Basic 인증

가장 단순한 경우 HTTP Basic 인증을 쓸 수 있다.

- 앱이 사용자 이름과 비밀번호가 담긴 헤더를 기대한다.
- 받지 못하면 HTTP 401 "Unauthorized" 오류와 함께 `WWW-Authenticate: Basic`(선택적 `realm` 포함) 헤더를 반환한다.
- 그러면 브라우저가 내장 사용자 이름/비밀번호 프롬프트를 띄우고, 입력값을 헤더에 자동으로 담아 보낸다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()

security = HTTPBasic()


@app.get("/users/me")
def read_current_user(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    return {"username": credentials.username, "password": credentials.password}
```

- `HTTPBasic` 인스턴스를 의존성으로 쓰면 `username`과 `password`를 가진 `HTTPBasicCredentials` 객체를 받는다.
- 내부적으로 `Authorization: Basic <base64>` 헤더를 디코딩하고 첫 `:`로 나눈다. 헤더가 없거나 스킴이 `basic`이 아니거나 디코딩·형식이 잘못되면 401을 발생시킨다.
- `HTTPBasic(realm="...")`을 주면 `WWW-Authenticate: Basic realm="..."`로 응답한다.
- 처음 URL을 열거나 문서의 "Execute"를 누르면 브라우저가 자격 증명을 묻는다.

### 사용자 이름 확인과 타이밍 공격 방지

```Python
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()

security = HTTPBasic()


def get_current_username(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = b"stanleyjobson"
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = b"swordfish"
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/users/me")
def read_current_user(username: Annotated[str, Depends(get_current_username)]):
    return {"username": username}
```

- 표준 라이브러리 `secrets.compare_digest()`로 비교한다. 이 함수는 `bytes` 또는 ASCII만 담긴 `str`을 받으므로, `á` 같은 문자를 처리하려고 먼저 UTF-8로 인코딩한다.
- 자격 증명이 틀리면 `401`과 `WWW-Authenticate: Basic` 헤더를 가진 `HTTPException`을 발생시켜 브라우저가 다시 묻게 한다.

#### 타이밍 공격

`if credentials.username == "stanleyjobson"` 같은 일반 비교는 첫 글자가 다르면 바로 `False`를 반환하고, 앞부분이 많이 일치할수록 조금 더 오래 걸린다. 공격자는 응답 시간의 미세한 차이(마이크로초)를 수천~수백만 번 측정해 올바른 문자를 하나씩 알아낼 수 있다. `secrets.compare_digest()`는 비교 시간이 내용과 무관해 이런 **타이밍 공격**을 막는다.

## API 키

헤더, 쿼리 파라미터, 쿠키로 전달되는 API 키를 받는다.

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader

app = FastAPI()

api_key_header = APIKeyHeader(name="X-API-Key")


async def get_api_key(api_key: Annotated[str, Depends(api_key_header)]):
    if api_key != "secret-key":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return api_key


@app.get("/items/")
async def read_items(api_key: Annotated[str, Depends(get_api_key)]):
    return {"api_key": api_key}
```

| 클래스 | 읽는 위치 |
| --- | --- |
| `APIKeyHeader(name=...)` | 요청 헤더 |
| `APIKeyQuery(name=...)` | 쿼리 파라미터 |
| `APIKeyCookie(name=...)` | 쿠키 |

- 인스턴스는 키 문자열(`str`)을 반환한다. **유효성 검사(DB 조회 등)는 직접** 해야 한다.
- 키가 없거나 비어 있으면 `401`, `detail="Not authenticated"`, `WWW-Authenticate: APIKey` 헤더를 반환한다. API 키용 `WWW-Authenticate`는 표준이 없지만 HTTP 명세가 401 응답에 이 헤더를 요구하므로 사용자 정의 챌린지 `APIKey`를 보낸다.
- 공통 파라미터: `name`, `scheme_name`(OpenAPI 스킴 이름, 기본은 클래스 이름), `description`, `auto_error`.

## HTTP Bearer

```Python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI()

security = HTTPBearer()


@app.get("/me")
def read_me(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    return {"scheme": credentials.scheme, "token": credentials.credentials}
```

- `Authorization: Bearer <token>` 헤더를 읽어 `HTTPAuthorizationCredentials(scheme, credentials)`를 반환한다.
- 헤더가 없거나 스킴이 `bearer`가 아니면 `401` + `WWW-Authenticate: Bearer`.
- `bearerFormat`(예: `"JWT"`)으로 OpenAPI에 토큰 형식을 문서화할 수 있다.
- OAuth2 흐름을 문서화하려면 `OAuth2PasswordBearer`가 더 적합하다([OAuth2 비밀번호 흐름](./oauth2-password-flow.md)).

`HTTPDigest`는 `Authorization: Digest ...` 헤더를 `HTTPAuthorizationCredentials`로 꺼내기만 하며, Digest 검증은 직접 구현해야 한다.

## OpenIdConnect

`OpenIdConnect(openIdConnectUrl=...)`는 OpenAPI에 OpenID Connect 스킴을 연결하는 **스텁**이다. `Authorization` 헤더 값을 그대로 반환할 뿐 OpenID Connect URL을 사용하는 등 전체 스킴을 구현하지 않으므로, 하위 클래스에서 직접 구현해야 한다.

## auto_error: 선택적 인증

모든 보안 클래스는 `auto_error`(기본 `True`)를 가진다.

- `True`: 자격 증명이 없거나 형식이 틀리면 자동으로 401 오류를 발생시킨다.
- `False`: 오류 대신 `None`을 반환한다. **선택적 인증**(로그인 여부에 따라 다른 응답)이나 **여러 방식 중 하나**(예: Bearer 토큰 또는 쿠키)로 인증할 때 유용하다.

```Python
optional_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


@app.get("/public")
async def public(api_key: Annotated[str | None, Depends(optional_api_key)]):
    return {"authenticated": api_key is not None}
```

`HTTPBasic`은 `auto_error=False`여도 헤더는 있지만 Base64 디코딩이 실패하는 등 형식이 잘못된 경우에는 401을 발생시킨다.

## 401 vs 403

FastAPI 0.122.0부터 보안 유틸리티는 인증 실패 시 `403` 대신 명세에 맞는 `401 Unauthorized` + `WWW-Authenticate`를 반환한다. 예전 동작이 필요하면 `make_not_authenticated_error()`를 재정의한다([오류 처리](../errors/handling-errors.md)).

## 관련 페이지

- [보안 기초: OAuth2 비밀번호 흐름](./oauth2-password-flow.md)
- [JWT 토큰과 비밀번호 해싱](./oauth2-jwt.md)
- [OAuth2 스코프](./oauth2-scopes.md)
- [헤더와 쿠키 파라미터](../request/headers-and-cookies.md)
