---
type: tutorial
title: OAuth2 with JWT Tokens and Password Hashing
description: Build a real login flow — hash passwords with pwdlib (Argon2), authenticate with a timing-safe dummy hash, issue signed JWT access tokens with PyJWT including exp and sub claims, and decode them in a get_current_user dependency.
tags: [security, oauth2, jwt, pyjwt, pwdlib, argon2, password-hashing, authentication]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-8b7cc7b6bb4e026e4e77a49d
    resource: repo://docs_src/security/tutorial004_an_py310.py
  - id: openwiki-source-c7eecf90c63859db4ece2fb9
    resource: repo://docs/en/docs/tutorial/security/oauth2-jwt.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# OAuth2 with JWT Tokens and Password Hashing

This completes the flow from [Security Basics](oauth2-password-flow.md) with real security: hashed passwords and signed, expiring **JWT** access tokens.

## Concepts

- **JWT** (JSON Web Token): a compact, signed string such as `eyJhbGciOi...`. It isn't encrypted — anyone can read the payload — but it's **signed**, so the server can verify it issued the token and that it wasn't modified. It can carry an expiry.
- **Password hashing**: store a one-way hash, never the password. If the database leaks, the passwords can't be recovered directly.

Install:

```bash
uv add pyjwt
uv add "pwdlib[argon2]"
```

`pwdlib` recommends **Argon2**; it also supports bcrypt (for legacy hashes, e.g. from Django, consider `passlib` to verify old hashes while hashing new ones with Argon2/bcrypt). If you use digital-signature algorithms like RSA/ECDSA, install `pyjwt[crypto]`.

## The full example

`docs_src/security/tutorial004_an_py310.py`:

```python
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
```

(`fake_users_db` stores `johndoe` with an Argon2 `hashed_password` of the password `secret`.)

## Walkthrough

### Password hashing

- `PasswordHash.recommended()` returns a hasher configured with the recommended algorithm (Argon2).
- `password_hash.hash(password)` creates a hash (store it at sign-up); `password_hash.verify(plain, hashed)` checks a login attempt.
- The plaintext `secret` never appears in the code or database.

### Timing-safe authentication

`authenticate_user` still runs `verify_password(password, DUMMY_HASH)` when the user **doesn't exist**. Without that, unknown usernames would be rejected noticeably faster than wrong passwords, letting attackers enumerate valid usernames by timing.

### Creating tokens

- Generate `SECRET_KEY` with `openssl rand -hex 32` and keep it out of source control (e.g. load it via [Settings](../app-structure/settings.md)).
- `ALGORITHM = "HS256"` (HMAC with SHA-256).
- `create_access_token` adds an `exp` claim (expiry, UTC); PyJWT rejects expired tokens on decode with an `InvalidTokenError` subclass.
- The login endpoint returns a `Token` response model `{"access_token": ..., "token_type": "bearer"}` — the shape the OAuth2 spec requires.

### The `sub` claim

JWT's `sub` (subject) identifies the token's subject. It should be a **string, unique across the whole application**. If tokens may identify different kinds of entities (users, cars, blog posts — e.g. for delegated permissions), prefix it, e.g. `"username:johndoe"`.

### Verifying tokens

`get_current_user` decodes with `jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])` (always pin the accepted algorithms), reads `sub`, and loads the user. Any problem — bad signature, expired token, missing `sub`, unknown user — results in the same `401` with `WWW-Authenticate: Bearer`. `get_current_active_user` additionally rejects disabled users.

## Trying it

In `/docs`, click **Authorize**, log in with `johndoe` / `secret`, then call `/users/me/`. The client sends `Authorization: Bearer <JWT>`; you can paste the token into a JWT debugger to see the readable (but signed) payload.

## Next steps

- Use real storage (e.g. [SQL Databases](../integrations/sql-databases.md)) instead of `fake_users_db`.
- Add permissions with [OAuth2 Scopes](oauth2-scopes.md).
- FastAPI doesn't force any particular libraries — `PyJWT` and `pwdlib` are simply well-maintained choices, used via ordinary dependencies.

## Related

- [Security Basics: OAuth2 Password Flow and Current User](oauth2-password-flow.md)
- [HTTP Basic, Bearer, API Keys](http-basic-and-api-keys.md)
