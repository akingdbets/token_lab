---
type: tutorial
title: "Security Basics: OAuth2 Password Flow and Current User"
description: Security concepts (OAuth2, OpenID Connect, OpenAPI security schemes), OAuth2PasswordBearer for reading bearer tokens, a get_current_user dependency chain, and a simple /token login with OAuth2PasswordRequestForm.
tags: [security, oauth2, oauth2passwordbearer, oauth2passwordrequestform, authentication, get_current_user, bearer-token]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-fb9e69d8e242c08bc89aa33c
    resource: repo://docs_src/security/tutorial001_an_py310.py
  - id: openwiki-source-037c5b7707676a7b7c4e5e65
    resource: repo://docs_src/security/tutorial002_an_py310.py
  - id: openwiki-source-eec355dc19b1ef3e0e4942e3
    resource: repo://docs_src/security/tutorial003_an_py310.py
  - id: openwiki-source-09d4f7c7883e3f49659031cf
    resource: repo://docs/en/docs/tutorial/security/index.md
  - id: openwiki-source-4fc063f5745a6985eaa6d7be
    resource: repo://fastapi/security/oauth2.py
  - id: openwiki-source-ec1dd8aadb7932faee06d4c0
    resource: repo://fastapi/security/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Security Basics: OAuth2 Password Flow and Current User

## Concepts

- **OAuth2** — a specification for authentication and authorization, including "flows" for third-party login ("Login with Google/GitHub/…"). It doesn't specify encryption; it expects HTTPS. (OAuth 1 was very different and is rarely used.)
- **OpenID Connect** — built on OAuth2; e.g. Google login. (Unrelated to the older "OpenID".)
- **OpenAPI security schemes** — OpenAPI can describe `apiKey` (header, query or cookie), `http` (Basic, Bearer, Digest), `oauth2` (flows: `implicit`, `clientCredentials`, `authorizationCode`, `password`) and `openIdConnect` (auto-discovery). The docs UI uses these to offer an **Authorize** button.

FastAPI provides tools for all of these in `fastapi.security`. They're just dependencies, so they integrate with the rest of your app. This page uses the OAuth2 **password** flow, where your own API handles username/password and issues a token — a good fit for first-party apps.

## Step 1: require a bearer token

`docs_src/security/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}
```

- `OAuth2PasswordBearer(tokenUrl="token")` declares that clients obtain a token by POSTing username/password to the relative URL `token` (resolved against the API root, so it keeps working behind a proxy prefix). It does **not** create that endpoint.
- As a dependency, it reads `Authorization: Bearer <token>` and returns the token string.
- Missing header or non-bearer scheme → **401** `{"detail": "Not authenticated"}` with `WWW-Authenticate: Bearer` (unless `auto_error=False`, which returns `None`).
- The docs UI now shows **Authorize** and lock icons.

The flow: the user enters credentials in the frontend → the frontend POSTs them to `tokenUrl` → the API returns a token → the frontend sends `Authorization: Bearer <token>` on later requests.

## Step 2: get the current user

Build a dependency that turns the token into a user, on top of `oauth2_scheme` (`tutorial002_an_py310.py`):

```python
from pydantic import BaseModel


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

Now any path operation can declare `current_user: Annotated[User, Depends(get_current_user)]`. Your user model can be anything (Pydantic, ORM objects, …), and you can protect thousands of endpoints with one line each — or a whole router with `dependencies=[Depends(get_current_user)]` ([Dependencies in Decorators](../dependencies/decorator-and-global-dependencies.md)).

## Step 3: a simple `/token` login

The OAuth2 password flow requires the client to send `username` and `password` as **form fields** (not JSON). `OAuth2PasswordRequestForm` is a class dependency that reads them (`tutorial003_an_py310.py`, abbreviated):

```python
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


class UserInDB(User):
    hashed_password: str


def fake_hash_password(password: str):
    return "fakehashed" + password


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

### `OAuth2PasswordRequestForm`

Form fields (attributes): `username`, `password`, `scope` (a space-separated string, exposed as the list `form_data.scopes`), optional `grant_type`, `client_id` and `client_secret`. `OAuth2PasswordRequestFormStrict` additionally **requires** `grant_type="password"`, as the spec says. Needs `python-multipart` ([Forms](../request/forms-and-files.md)).

### The token response

The token endpoint must return JSON with `access_token` and `token_type` (`"bearer"`). Here the "token" is just the username — **insecure**, only to show the flow. Real tokens are covered in [OAuth2 with JWT](oauth2-jwt.md).

### Status codes and headers

- Wrong credentials at `/token` → `400` (per OAuth2's error conventions in this tutorial).
- Invalid/missing token on protected endpoints → `401` with `WWW-Authenticate: Bearer` — required by the spec for 401s.
- Disabled users → `400 Inactive user` via the extra `get_current_active_user` dependency layered on `get_current_user`.

### Try it

In `/docs`, click **Authorize**, log in as `johndoe` / `secret`, then call `/users/me`. Log out and the endpoint returns 401. `alice` is disabled and gets "Inactive user".

## Other OAuth2 classes

- `OAuth2AuthorizationCodeBearer(authorizationUrl=..., tokenUrl=...)` — documents the authorization-code flow (e.g. with an external identity provider); reads the bearer token the same way.
- `OAuth2(flows=...)` — the generic base for custom flows.
- Scopes: `OAuth2PasswordBearer(tokenUrl=..., scopes={...})` with `Security()` and `SecurityScopes` — see [OAuth2 Scopes](oauth2-scopes.md).

## Related

- [OAuth2 with JWT Tokens and Password Hashing](oauth2-jwt.md)
- [HTTP Basic, Bearer, API Keys and OpenID Connect](http-basic-and-api-keys.md)
- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
