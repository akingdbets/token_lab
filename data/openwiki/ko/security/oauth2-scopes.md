---
type: guide
title: OAuth2 스코프
description: OAuth2PasswordBearer(scopes={...})로 사용 가능한 스코프를 선언하고, 토큰에 스코프를 담고, Security(dependency, scopes=[...])로 경로 작업·의존성별 필요 스코프를 선언하며, SecurityScopes로 의존성 트리 전체에 누적된 스코프를 검사하는 방법, 캐시 동작, 서드파티 연동용 다른 OAuth2 흐름을 설명한다.
tags: [security, oauth2, scopes, security-scopes, permissions, jwt]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-2546c0a51f64c41d8cdb4e1b
    resource: repo://docs_src/security/tutorial005_an_py310.py
  - id: openwiki-source-c46ca1d7e534ec6d650bb745
    resource: repo://fastapi/dependencies/models.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-4ba318fa02e49c0255b400c4
    resource: repo://fastapi/param_functions.py
  - id: openwiki-source-4fc063f5745a6985eaa6d7be
    resource: repo://fastapi/security/oauth2.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# OAuth2 스코프

> 다소 고급 내용이다. OAuth2 스코프 없이도 원하는 방식으로 인증·권한을 처리할 수 있다. 많은 경우 과할 수 있지만, OpenAPI와 문서에 깔끔하게 통합된다는 장점이 있다. 스코프든 다른 권한 요구든 실제 **강제는 여전히 코드에서** 해야 한다.

OAuth2 스코프는 Facebook, Google, GitHub, Microsoft, X(Twitter) 같은 큰 인증 제공자가 사용자와 앱에 특정 권한을 주는 메커니즘이다. 이들의 "~로 로그인"은 모두 스코프를 사용한다. FastAPI에서는 OAuth2 표준을 따르는 세밀한 권한 시스템을 OpenAPI·문서와 통합해 만들 수 있다.

## OAuth2 스코프와 OpenAPI

OAuth2 명세에서 "스코프"는 공백으로 구분된 문자열 목록이다. 각 스코프 문자열은 공백이 없을 뿐 형식은 자유로우며 보통 특정 보안 권한을 나타낸다. 예: `users:read`, `users:write`, Facebook/Instagram의 `instagram_basic`, Google의 `https://www.googleapis.com/auth/drive`. OAuth2에서는 그저 문자열일 뿐이다.

## 전체 예제

[JWT 토큰 예제](./oauth2-jwt.md)를 확장한다.

```Python
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, ValidationError

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# fake_users_db, Token, User, UserInDB, password_hash, DUMMY_HASH,
# verify_password, get_user, authenticate_user, create_access_token 은 JWT 예제와 동일


class TokenData(BaseModel):
    username: str | None = None
    scopes: list[str] = []


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"me": "Read information about the current user.", "items": "Read items."},
)

app = FastAPI()


async def get_current_user(
    security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]
):
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        scope: str = payload.get("scope", "")
        token_scopes = scope.split(" ")
        token_data = TokenData(scopes=token_scopes, username=username)
    except (InvalidTokenError, ValidationError):
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scope": " ".join(form_data.scopes)},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me/")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@app.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["items"])],
):
    return [{"item_id": "Foo", "owner": current_user.username}]


@app.get("/status/")
async def read_system_status(current_user: Annotated[User, Depends(get_current_user)]):
    return {"status": "ok"}
```

## 단계별 설명

### 1. OAuth2 보안 스킴에 스코프 선언

`OAuth2PasswordBearer(scopes={...})`의 `scopes`는 스코프 이름을 키, 설명을 값으로 하는 `dict`다. 이 스코프들은 OpenAPI에 등록되어, `/docs`에서 로그인할 때 부여할 스코프(`me`, `items`)를 선택할 수 있다. Facebook·Google 로그인 시 권한을 고르는 것과 같은 메커니즘이다.

### 2. 토큰에 스코프 담기

토큰 경로 작업에서 `OAuth2PasswordRequestForm`의 `scopes` 속성(받은 `scope` 폼 필드를 공백으로 나눈 리스트)을 JWT의 `"scope"` 클레임에 공백으로 이어 넣는다. 예제는 단순화를 위해 받은 스코프를 그대로 넣지만, **실제 앱에서는 사용자가 가질 수 있는(또는 미리 정의한) 스코프만** 추가해야 한다.

### 3. 경로 작업과 의존성에 스코프 선언: Security

`Security`는 `Depends`처럼 의존성을 선언하지만, 추가로 스코프 문자열 리스트 `scopes` 파라미터를 받는다.

- `/users/me/items/`는 `Security(get_current_active_user, scopes=["items"])`로 `items` 스코프를 요구한다.
- `get_current_active_user`는 `Security(get_current_user, scopes=["me"])`로 `me` 스코프를 요구한다.
- `get_current_user`는 스코프 요구가 없으므로 `oauth2_scheme`을 `Depends`로 쓴다. 스코프가 필요 없으면 `Security` 대신 `Depends`를 써도 된다.

`Security`(`fastapi.params.Security`)는 `Depends`의 하위 클래스로 `scopes` 파라미터 하나가 추가된 것이다. `Security`를 쓰면 FastAPI가 스코프를 선언하고 내부에서 사용하며 OpenAPI에 문서화한다. `fastapi`에서 임포트하는 `Security()`는 그 클래스를 반환하는 함수다.

### 4. SecurityScopes로 스코프 검사

의존성에 `SecurityScopes` 타입 파라미터를 선언하면(`Request`처럼 FastAPI가 채워 준다), **그 의존성을 사용하는 모든 의존성과 경로 작업이 요구한 스코프**를 얻는다.

- `security_scopes.scopes`: 필요한 스코프 리스트
- `security_scopes.scope_str`: 공백으로 이어 붙인 문자열(OAuth2 명세 형식)

`get_current_user`는 이를 사용해:

1. `WWW-Authenticate` 헤더에 필요한 스코프를 포함한다(`Bearer scope="me items"`, 명세의 일부).
2. 토큰을 디코딩해 `sub`와 `scope`를 꺼내고, `TokenData` Pydantic 모델로 형태를 검증한다(`ValidationError`도 401로 처리).
3. 필요한 모든 스코프가 토큰 스코프에 포함되는지 확인하고, 없으면 `401 Not enough permissions`.

### 의존성 트리와 스코프 누적

```
read_own_items           Security(..., scopes=["items"])
└─ get_current_active_user   Security(..., scopes=["me"])
   └─ get_current_user       SecurityScopes 파라미터
      └─ oauth2_scheme
```

| 경로 작업 | `get_current_user`의 `security_scopes.scopes` |
| --- | --- |
| `read_own_items` (`/users/me/items/`) | `["me", "items"]` |
| `read_users_me` (`/users/me/`) | `["me"]` (`get_current_active_user`에서 선언) |
| `read_system_status` (`/status/`) | `[]` (스코프 선언 없음, `get_current_user`를 바로 사용) |

같은 `get_current_user`가 경로 작업마다 다른 스코프 집합을 검사한다. `SecurityScopes`는 루트 의존성이 아니어도 어디서든, 여러 곳에서 쓸 수 있으며, 항상 현재 `Security` 의존성과 모든 상위 의존성의 스코프를 가진다.

### 캐시

같은 요청에서 같은 의존성은 캐시되지만, 스코프를 사용하는 의존성(스코프 선언, `SecurityScopes` 파라미터, 보안 스킴, 또는 그런 하위 의존성 포함)은 **필요 스코프 집합까지 캐시 키에 포함**된다. 따라서 서로 다른 스코프로 사용된 같은 의존성은 각각 따로 실행된다([의존성 주입 기초](../dependencies/dependency-injection-basics.md)).

## 확인

`/docs`에서 로그인하며 스코프를 고른다.

- 스코프를 하나도 선택하지 않으면 "인증"은 되지만 `/users/me/`나 `/users/me/items/`는 권한 부족 오류, `/status/`는 접근 가능.
- `me`만 선택하면 `/users/me/`는 되지만 `/users/me/items/`는 안 된다.

사용자가 서드파티 앱에 얼마나 많은 권한을 주었는지에 따라 그 앱이 받는 결과와 같다.

## 데코레이터 dependencies에서 Security

[데코레이터 의존성](../dependencies/decorator-and-global-dependencies.md)처럼 경로 작업 데코레이터의 `dependencies=[...]`에도 `Security(..., scopes=[...])`를 쓸 수 있다.

## 서드파티 연동과 다른 OAuth2 흐름

이 예제는 OAuth2 **password** 흐름을 쓴다. 자신의 프런트엔드로 자신의 앱에 로그인하는 경우, 즉 `username`과 `password`를 받아도 신뢰할 수 있는 경우에 적합하다.

다른 사람이 연결할 OAuth2 앱(Facebook, Google, GitHub 같은 인증 제공자)을 만든다면 다른 흐름을 써야 한다. 가장 흔한 것은 implicit 흐름이고, 가장 안전한 것은 authorization code 흐름이지만 단계가 많아 구현이 복잡하다. 제공자마다 흐름에 브랜드 이름을 붙이지만 결국 같은 OAuth2 표준이다. FastAPI는 `fastapi.security.oauth2`에 이러한 흐름의 도구(예: `OAuth2AuthorizationCodeBearer`, 사용자 정의 흐름을 위한 `OAuth2`)를 포함한다.

## 관련 페이지

- [JWT 토큰과 비밀번호 해싱](./oauth2-jwt.md)
- [보안 기초: OAuth2 비밀번호 흐름](./oauth2-password-flow.md)
- [고급 의존성](../dependencies/advanced-dependencies.md)
