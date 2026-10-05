---
type: tutorial
title: JWT 토큰과 비밀번호 해싱
description: OAuth2 비밀번호 흐름에 PyJWT로 서명된 JWT 액세스 토큰(HS256, exp 만료, sub 주체)을 발급·검증하고, pwdlib(Argon2, PasswordHash.recommended())로 비밀번호를 해싱·검증하며, 존재하지 않는 사용자에도 DUMMY_HASH로 검증해 타이밍 공격을 막는 완전한 예제를 설명한다.
tags: [security, jwt, oauth2, pyjwt, pwdlib, argon2, password-hashing]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-8b7cc7b6bb4e026e4e77a49d
    resource: repo://docs_src/security/tutorial004_an_py310.py
  - id: openwiki-source-c7eecf90c63859db4ece2fb9
    resource: repo://docs/en/docs/tutorial/security/oauth2-jwt.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# JWT 토큰과 비밀번호 해싱

[OAuth2 비밀번호 흐름](./oauth2-password-flow.md)의 단순 예제를 실제로 안전하게 만든다. **JWT** 토큰과 안전한 **비밀번호 해싱**을 사용한다. 이 코드는 실제 앱에서 그대로 사용할 수 있으며, 해시된 비밀번호를 DB에 저장하면 된다.

## JWT

JWT는 "JSON Web Tokens"로, JSON 객체를 공백 없는 긴 문자열로 인코딩하는 표준이다.

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

- **암호화되지 않았다**. 누구나 내용을 복원할 수 있다.
- **서명**되어 있다. 내가 발급한 토큰을 받으면 실제로 내가 발급했는지 검증할 수 있다.
- 예: 만료 기간이 1주인 토큰을 발급하면, 다음 날 사용자가 토큰을 가지고 돌아왔을 때 여전히 로그인 상태임을 안다. 1주 뒤에는 만료되어 다시 로그인해야 한다. 누군가 만료 시간을 바꾸려고 토큰을 수정하면 서명이 맞지 않아 발견할 수 있다.
- [https://jwt.io](https://jwt.io/)에서 직접 실험해 볼 수 있다.

## 패키지 설치

```console
$ uv add pyjwt
$ uv add "pwdlib[argon2]"
```

- `PyJWT`: JWT 생성·검증. RSA, ECDSA 같은 디지털 서명 알고리즘을 쓰려면 `pyjwt[crypto]`를 설치한다.
- `pwdlib`: 비밀번호 해시 처리. 권장 알고리즘은 **Argon2**. bcrypt도 지원하지만 레거시 알고리즘은 포함하지 않는다(오래된 해시는 passlib 권장). Django, Flask 보안 플러그인 등이 만든 비밀번호를 읽도록 구성할 수도 있어, 기존 앱과 DB를 공유하며 점진적으로 이전할 수 있다.

## 비밀번호 해싱

**해싱**은 내용(여기서는 비밀번호)을 알아볼 수 없는 바이트열(문자열)로 바꾸는 것이다. 같은 내용을 넣으면 항상 같은 결과가 나오지만, 결과를 다시 비밀번호로 되돌릴 수는 없다. DB가 도난당해도 도둑은 평문 비밀번호가 아니라 해시만 얻으므로, 같은 비밀번호를 다른 시스템에 쓰는 사용자를 보호할 수 있다.

```Python
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

DUMMY_HASH = password_hash.hash("dummypassword")


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user
```

- `PasswordHash.recommended()`는 권장 설정(Argon2)의 해셔를 만든다.
- 해시 예: `"$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc"`
- 사용자가 **없을 때도** `DUMMY_HASH`로 검증을 수행해, 사용자 이름이 유효하든 아니든 응답 시간이 비슷하게 만든다. 응답 시간으로 존재하는 사용자 이름을 알아내는 **타이밍 공격**을 막는다.

## JWT 토큰 처리

1. 무작위 비밀 키를 만든다: `openssl rand -hex 32`. 예제의 값을 그대로 쓰지 말 것.
2. 서명 알고리즘 `ALGORITHM = "HS256"`.
3. 토큰 만료 시간 `ACCESS_TOKEN_EXPIRE_MINUTES = 30`.
4. 토큰 엔드포인트 응답용 Pydantic 모델 `Token`을 정의한다.
5. 새 액세스 토큰을 만드는 유틸리티 함수를 만든다.

## 전체 예제

```Python
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc",
        "disabled": False,
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


password_hash = PasswordHash.recommended()

DUMMY_HASH = password_hash.hash("dummypassword")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me/")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@app.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return [{"item_id": "Foo", "owner": current_user.username}]
```

### 흐름

- **`/token`**: `OAuth2PasswordRequestForm`으로 폼 필드 `username`/`password`를 받아 `authenticate_user()`로 검증하고, `sub`에 사용자 이름을 담고 `exp`(UTC 기준 만료 시각)를 넣은 JWT를 `jwt.encode()`로 서명해 `Token(access_token=..., token_type="bearer")`으로 반환한다. 실패하면 `401` + `WWW-Authenticate: Bearer`.
- **`get_current_user`**: `OAuth2PasswordBearer`가 `Authorization: Bearer <token>`에서 꺼낸 토큰을 `jwt.decode(..., algorithms=[ALGORITHM])`로 검증·디코딩한다. 서명이 틀리거나 만료되면 `InvalidTokenError`가 발생하고, 이를 `401 Could not validate credentials`로 바꾼다. `sub`로 사용자를 조회한다.
- **`get_current_active_user`**: 비활성 사용자면 `400 Inactive user`.
- **`/users/me/`**: 반환 타입 `User`로 `hashed_password`가 응답에서 제외된다([응답 모델](../responses/response-model.md)).

`/docs`에서 "Authorize" 버튼을 눌러 `johndoe` / `secret`으로 로그인하면 이후 요청에 `Authorization: Bearer <JWT>` 헤더가 붙는다.

## JWT "subject" `sub`

JWT 명세에는 토큰의 주체를 나타내는 `sub` 키가 있다(선택 사항). 사용자 식별과 권한 부여에 쓴다. JWT는 사용자 식별 외에도 쓰일 수 있다(예: "자동차"나 "블로그 게시물"을 식별해 "drive", "edit" 같은 권한 부여). 다른 엔티티의 ID가 사용자 이름과 같을 수 있으므로, 충돌을 피하려면 `sub` 값에 접두사를 붙일 수 있다(예: `username:johndoe`). 중요한 것은 `sub`가 **앱 전체에서 고유한 식별자**이며 **문자열**이어야 한다는 점이다.

## 고급: 스코프

OAuth2에는 "스코프(scopes)" 개념이 있어 JWT 토큰에 특정 권한 집합을 담을 수 있다. 이를 사용자나 서드파티에 주어 제한된 범위에서 API와 상호작용하게 할 수 있다([OAuth2 스코프](./oauth2-scopes.md)).

## 정리

FastAPI는 데이터베이스, 데이터 모델, 사용자 모델에 대해 어떤 타협도 요구하지 않는다. 원하는 DB·모델을 쓰고, `pwdlib`, `PyJWT` 같은 널리 쓰이는 패키지를 그대로 통합할 수 있다. 이 유연성 덕분에 보안 표준 유연성을 유지하면서 높은 수준의 보안을 구현할 수 있다.

## 관련 페이지

- [보안 기초: OAuth2 비밀번호 흐름](./oauth2-password-flow.md)
- [OAuth2 스코프](./oauth2-scopes.md)
- [SQL 데이터베이스](../integrations/sql-databases.md) — 사용자와 해시된 비밀번호 저장
- [설정과 환경 변수](../app-structure/settings.md) — `SECRET_KEY`를 환경 변수로 관리
