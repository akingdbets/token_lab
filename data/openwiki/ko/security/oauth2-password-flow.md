---
type: "참조"
title: "보안 기초: OAuth2 비밀번호 흐름과 현재 사용자"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-fb9e69d8e242c08bc89aa33c
    resource: repo://docs_src/security/tutorial001_an_py310.py
  - id: openwiki-source-037c5b7707676a7b7c4e5e65
    resource: repo://docs_src/security/tutorial002_an_py310.py
  - id: openwiki-source-eec355dc19b1ef3e0e4942e3
    resource: repo://docs_src/security/tutorial003_an_py310.py
  - id: openwiki-source-dabd79d7ea6e0f78b68a26ca
    resource: repo://docs/en/docs/tutorial/security/first-steps.md
  - id: openwiki-source-e4434424dcebf9cbd6cf566a
    resource: repo://docs/en/docs/tutorial/security/simple-oauth2.md
  - id: openwiki-source-4fc063f5745a6985eaa6d7be
    resource: repo://fastapi/security/oauth2.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---


# 보안 기초: OAuth2 비밀번호 흐름과 현재 사용자

FastAPI는 모든 보안 명세를 공부하지 않아도 보안을 표준 방식으로 쉽고 빠르게 다룰 수 있는 도구를 제공한다. 이 페이지는 개념을 정리하고, **OAuth2 비밀번호(password) 흐름 + Bearer 토큰**으로 사용자 이름/비밀번호 인증을 단계별로 만든다. 실제로 안전한 구현(JWT, 비밀번호 해싱)은 [JWT 토큰과 비밀번호 해싱](./oauth2-jwt.md)에서 완성한다.

## 보안 개념 요약

- **OAuth2**: 인증·권한 부여를 처리하는 여러 방법을 정의하는 명세. "Facebook, Google, X(Twitter), GitHub로 로그인" 같은 서드파티 인증에 쓰이며, 통신 암호화 방법은 규정하지 않고 HTTPS 사용을 전제한다. (OAuth 1은 매우 다르고 복잡하며 오늘날 거의 쓰이지 않는다.)
- **OpenID Connect**: OAuth2를 기반으로 일부 모호한 부분을 구체화해 상호운용성을 높인 명세(예: Google 로그인). 옛 "OpenID"와는 다르다.
- **OpenAPI 보안 스킴**: FastAPI는 OpenAPI 기반이므로 다음 스킴을 정의할 수 있다.
  - `apiKey`: 쿼리 파라미터·헤더·쿠키로 오는 앱 전용 키
  - `http`: `bearer`(`Authorization: Bearer <token>`, OAuth2에서 유래), HTTP Basic, HTTP Digest 등
  - `oauth2`: OAuth2의 여러 "흐름". 그중 **password** 흐름은 같은 앱에서 직접 인증을 처리하는 데 적합하다.
  - `openIdConnect`: OAuth2 인증 데이터를 자동으로 발견하는 방법

FastAPI는 `fastapi.security`에서 각 스킴의 도구를 제공하며, 이를 의존성으로 쓰면 OpenAPI와 대화형 문서에 보안이 자동 통합된다(HTTP Basic, API 키는 [HTTP Basic, API 키](./http-basic-and-api-keys.md) 참고).

## 1단계: OAuth2PasswordBearer

```Python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}
```

- OAuth2는 `username`과 `password`를 **폼 데이터**로 보내므로 `python-multipart`가 필요하다(`fastapi[standard]`에 포함, `uv add fastapi`만 했다면 `uv add python-multipart`).
- `/docs`에 "Authorize" 버튼이 생기고, 경로 작업에 자물쇠 아이콘이 표시된다.

### password 흐름

1. 사용자가 프런트엔드에서 `username`과 `password`를 입력한다.
2. 프런트엔드가 이를 API의 특정 URL(`tokenUrl="token"`)로 보낸다.
3. API가 검증 후 **토큰**을 반환한다. 토큰은 나중에 사용자를 확인하는 데 쓰이는 문자열이며, 보통 일정 시간 후 만료된다.
4. 프런트엔드는 토큰을 저장해 두고, 이후 요청마다 `Authorization: Bearer <token>` 헤더를 보낸다(토큰이 `foobar`면 `Bearer foobar`).

### tokenUrl

- `tokenUrl`은 클라이언트가 토큰을 얻기 위해 `username`/`password`를 보낼 URL이다. 이 엔드포인트를 **만들지는 않으며**, OpenAPI와 문서 UI에 정보를 제공할 뿐이다.
- `"token"`은 **상대 URL**(`./token`)이다. API가 `https://example.com/`에 있으면 `https://example.com/token`, `https://example.com/api/v1/`에 있으면 `https://example.com/api/v1/token`이 된다. 상대 URL은 [프록시 뒤 실행](../app-structure/sub-applications-proxy-and-wsgi.md) 같은 상황에서도 동작하게 해 준다.
- 파이썬답지 않은 `tokenUrl` 이름은 OpenAPI 명세의 이름을 그대로 따른 것이다.

### 동작

`oauth2_scheme`은 호출 가능한 인스턴스다. 요청의 `Authorization` 헤더에서 `Bearer ` 뒤의 토큰을 `str`로 반환한다. 헤더가 없거나 `Bearer` 토큰이 아니면 바로 **401**(`WWW-Authenticate: Bearer`)을 반환한다. 토큰이 유효한지는 아직 확인하지 않는다. `OAuth2PasswordBearer`는 `fastapi.security.oauth2.OAuth2`를 거쳐 `SecurityBase`를 상속하므로 FastAPI가 OpenAPI 보안 스킴으로 인식한다. `auto_error=False`로 선택적 인증을 만들 수 있고, `scopes`, `refreshUrl`, `scheme_name`, `description` 파라미터도 있다.

## 2단계: 현재 사용자 가져오기

```Python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


def fake_decode_token(token):
    return User(
        username=token + "fakedecoded", email="john@example.com", full_name="John Doe"
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    return user


@app.get("/users/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
```

- `get_current_user` 의존성은 `oauth2_scheme`이라는 하위 의존성으로 토큰을 받아 사용자를 반환한다([하위 의존성](../dependencies/dependency-injection-basics.md)).
- 경로 작업은 `current_user: User`를 받아 에디터 지원과 타입 검사를 받는다.
- 보안 시스템이 의존성 시스템 위에 만들어졌으므로, 어떤 사용자 모델(Pydantic 모델, DB 객체 등)이든 쓸 수 있고, 수천 개의 엔드포인트가 같은 의존성을 재사용할 수 있다.

## 3단계: 사용자 이름/비밀번호로 토큰 받기

```Python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

app = FastAPI()


def fake_hash_password(password: str):
    return "fakehashed" + password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def fake_decode_token(token):
    # This doesn't provide any security at all
    # Check the next version
    user = get_user(fake_users_db, token)
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user_dict = fake_users_db.get(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserInDB(**user_dict)
    hashed_password = fake_hash_password(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user
```

### OAuth2PasswordRequestForm

명세상 password 흐름의 클라이언트는 `username`과 `password`를 **폼 데이터**(JSON 아님)로 보내야 한다. `OAuth2PasswordRequestForm`은 다음 폼 본문을 선언하는 **클래스 의존성**이다(`Depends()`로 사용).

| 필드 | 설명 |
| --- | --- |
| `username` | 필수 |
| `password` | 필수 |
| `scope` | 선택. 공백으로 구분된 스코프 문자열(예: `"users:read items:write"`). 인스턴스의 `scopes` 속성에 리스트로 분리되어 들어간다 |
| `grant_type` | 선택. 명세상 필수이며 값은 `password`여야 하지만, 이 클래스는 강제하지 않는다(값이 있으면 `^password$` 패턴 검사). 강제하려면 **`OAuth2PasswordRequestFormStrict`** |
| `client_id`, `client_secret` | 선택. 명세는 HTTP Basic으로 보내기를 권장 |

OAuth2에서 "스코프"는 필요한 특정 권한을 선언하는 문자열이다. `:`를 포함해도 된다(예: `users:read`, `instagram_basic`, `https://www.googleapis.com/auth/drive`). 자세한 사용은 [OAuth2 스코프](./oauth2-scopes.md).

### 비밀번호 검사

예제의 `fake_hash_password`는 보안이 전혀 없는 예시용이다. 실제로는 [pwdlib 등으로 해싱](./oauth2-jwt.md)하며, 평문 비밀번호는 절대 저장하지 않는다. 사용자가 없거나 비밀번호가 틀리면 `HTTPException(400, "Incorrect username or password")`를 발생시킨다. `UserInDB(**user_dict)`는 딕셔너리를 언패킹해 모델을 만든다([추가 모델](../models/extra-models-and-dataclasses.md)).

### 토큰 반환 형식

토큰 엔드포인트 응답은 JSON 객체여야 하며, 명세에 따라 **`access_token`**(토큰 문자열)과 **`token_type`**(Bearer면 `"bearer"`)을 포함해야 한다. 명세 준수를 위해 직접 챙겨야 하는 거의 유일한 부분이다. 이 예제는 사용자 이름을 그대로 토큰으로 반환하는 완전히 안전하지 않은 방식이다.

### 의존성 업데이트: 활성 사용자

`get_current_active_user`는 `get_current_user`에 의존하며, 사용자가 비활성이면 `400 Inactive user`를 반환한다. 경로 작업은 존재하고, 인증되었고, 활성인 사용자만 받는다.

401 응답에 `WWW-Authenticate: Bearer` 헤더를 넣는 것도 명세의 일부다. 모든 401 "UNAUTHORIZED" 응답은 이 헤더를 반환해야 하며, Bearer 토큰이면 값은 `Bearer`다. 생략해도 동작은 하지만 명세 준수와 도구 호환을 위해 넣는다.

### 확인

`/docs`에서 "Authorize"를 눌러 `johndoe` / `secret`으로 로그인하면 `/users/me`가 사용자 정보를 반환한다. 로그아웃 후 호출하면 `401 {"detail": "Not authenticated"}`, `alice` / `secret2`(비활성 사용자)로 로그인하면 `400 {"detail": "Inactive user"}`.

## 관련 페이지

- [JWT 토큰과 비밀번호 해싱](./oauth2-jwt.md) — 실제 안전한 구현
- [OAuth2 스코프](./oauth2-scopes.md)
- [HTTP Basic, API 키, 기타 보안 스킴](./http-basic-and-api-keys.md)
- [폼 데이터](../request/forms-and-files.md)
- [오류 처리](../errors/handling-errors.md) — 401 vs 403
