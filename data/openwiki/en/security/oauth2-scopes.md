---
type: guide
title: OAuth2 Scopes
description: Add fine-grained permissions with OAuth2 scopes — declare available scopes on OAuth2PasswordBearer, request them per dependency with Security(..., scopes=[...]), and verify the accumulated required scopes centrally with SecurityScopes in get_current_user.
tags: [security, oauth2, scopes, securityscopes, security, permissions, jwt]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-2546c0a51f64c41d8cdb4e1b
    resource: repo://docs_src/security/tutorial005_an_py310.py
  - id: openwiki-source-836a87afb462f04c920b7ec8
    resource: repo://docs/en/docs/advanced/security/oauth2-scopes.md
  - id: openwiki-source-c46ca1d7e534ec6d650bb745
    resource: repo://fastapi/dependencies/models.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
  - id: openwiki-source-4fc063f5745a6985eaa6d7be
    resource: repo://fastapi/security/oauth2.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# OAuth2 Scopes

**Scopes** are named permissions (strings without spaces) carried by a token — the mechanism behind "This app wants to read your profile" prompts at Google, GitHub, Facebook, etc. Common forms: `users:read`, `users:write`, `instagram_basic`, `https://www.googleapis.com/auth/drive`. To OAuth2 they're opaque strings; you decide their meaning.

FastAPI integrates scopes with dependency injection and OpenAPI: the docs' **Authorize** dialog lets users pick scopes, and each operation documents the scopes it needs.

This page extends [OAuth2 with JWT](oauth2-jwt.md). Full code: `docs_src/security/tutorial005_an_py310.py`.

## 1. Declare available scopes

```python
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"me": "Read information about the current user.", "items": "Read items."},
)
```

The dict maps scope names to descriptions (shown in the docs).

## 2. Put granted scopes in the token

`OAuth2PasswordRequestForm` reads the `scope` form field (space-separated) into `form_data.scopes`. Store them in the JWT:

```python
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
```

(For simplicity the example grants whatever was requested. A real app must only grant scopes the user is allowed to have.)

## 3. Require scopes with `Security()`

`Security` is like `Depends` but accepts `scopes` (it subclasses `Depends` in `fastapi.params`):

```python
from fastapi import Security


async def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


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

Required scopes **accumulate** down the dependency tree for each path operation:

| Path operation | Scopes required by `get_current_user` |
|----------------|----------------------------------------|
| `/users/me/` | `me` (from `get_current_active_user`) |
| `/users/me/items/` | `items` (path op) + `me` → `["items", "me"]` |
| `/status/` | none |

## 4. Verify centrally with `SecurityScopes`

Declare a parameter of type `SecurityScopes` in the dependency that checks the token. FastAPI fills it with all scopes required by this dependency and **all its dependants** for the current path operation:

```python
from fastapi.security import SecurityScopes
from pydantic import BaseModel, ValidationError


class TokenData(BaseModel):
    username: str | None = None
    scopes: list[str] = []


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
```

- `security_scopes.scopes` — list of required scopes; `security_scopes.scope_str` — the same, space-separated.
- Per the OAuth2 spec, the `WWW-Authenticate` header includes the required scopes: `Bearer scope="me items"`.
- `TokenData` validates the token's content (`ValidationError` is treated as invalid credentials).
- One function checks permissions for every endpoint; each endpoint just declares what it needs.

Because the dependency cache key includes the effective scopes, the same dependency used with different scopes in one request is resolved separately.

## Trying it

In `/docs` → **Authorize**, log in as `johndoe` / `secret` and tick scopes. Without `items`, `/users/me/items/` returns `401 Not enough permissions`; without `me`, `/users/me/` does too. This mirrors what a third-party app sees when a user grants limited permissions.

## Choosing a flow

The password flow is appropriate for **your own** frontend and API. If you're building an authentication provider that third-party apps connect to (like Google/GitHub), use another flow; the **authorization code** flow is the most secure (`OAuth2AuthorizationCodeBearer`). Scopes can also be set in decorators and routers with `dependencies=[Security(..., scopes=[...])]`.

## Related

- [OAuth2 with JWT Tokens and Password Hashing](oauth2-jwt.md)
- [Security Basics](oauth2-password-flow.md)
- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
