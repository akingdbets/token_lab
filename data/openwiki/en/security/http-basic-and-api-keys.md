---
type: reference
title: HTTP Basic, Bearer, API Keys and OpenID Connect
description: Use FastAPI's non-OAuth2 security utilities — HTTPBasic with HTTPBasicCredentials and timing-safe secrets.compare_digest checks, HTTPBearer/HTTPDigest with HTTPAuthorizationCredentials, APIKeyHeader/APIKeyQuery/APIKeyCookie and OpenIdConnect — plus auto_error, 401 responses and WWW-Authenticate headers.
tags: [security, http-basic, httpbearer, api-key, apikeyheader, openidconnect, auto_error, compare_digest]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
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
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# HTTP Basic, Bearer, API Keys and OpenID Connect

All classes in `fastapi.security` are **dependencies**: configured instances with an `async def __call__(self, request)` that extract credentials from the request, and that register a security scheme in OpenAPI (so the docs show an "Authorize" button). They only **extract** credentials — **verifying** them is your code's job.

Available classes (`fastapi/security/__init__.py`):

| Class | Reads | Returns |
|-------|-------|---------|
| `HTTPBasic` | `Authorization: Basic <base64>` | `HTTPBasicCredentials(username, password)` |
| `HTTPBearer` | `Authorization: Bearer <token>` | `HTTPAuthorizationCredentials(scheme, credentials)` |
| `HTTPDigest` | `Authorization: Digest ...` | `HTTPAuthorizationCredentials` |
| `APIKeyHeader(name=...)` | the named header | `str` |
| `APIKeyQuery(name=...)` | the named query parameter | `str` |
| `APIKeyCookie(name=...)` | the named cookie | `str` |
| `OpenIdConnect(openIdConnectUrl=...)` | the raw `Authorization` header | `str` |
| `OAuth2PasswordBearer`, `OAuth2AuthorizationCodeBearer`, `OAuth2` | bearer token | `str` — see [Security Basics](oauth2-password-flow.md) |

Common constructor options: `scheme_name` (name in OpenAPI; defaults to the class name), `description`, and `auto_error`.

## Missing credentials: `auto_error` and 401

With `auto_error=True` (default), missing or malformed credentials make the dependency raise `HTTPException(401, "Not authenticated")` with a `WWW-Authenticate` header:

- `HTTPBasic`: `Basic` (or `Basic realm="..."` if `realm` is set)
- `HTTPBearer` / `HTTPDigest`: `Bearer` / `Digest`
- API keys: `APIKey` (not standardized, but included per the HTTP spec's requirement for 401)
- `OpenIdConnect` and OAuth2: `Bearer`

Since FastAPI 0.122.0 this is **401** (previously 403). To restore 403, override `make_not_authenticated_error()` — see [Handling Errors](../errors/handling-errors.md).

With `auto_error=False`, the dependency returns `None` instead, so you can make authentication optional or try several schemes in sequence:

```python
from fastapi.security import APIKeyHeader, HTTPBearer

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_identity(
    api_key: Annotated[str | None, Depends(api_key_scheme)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
):
    if api_key:
        return verify_api_key(api_key)
    if bearer:
        return verify_token(bearer.credentials)
    raise HTTPException(status_code=401, detail="Not authenticated")
```

(Note for `HTTPBasic`: a header that is present but has invalid base64 or no `:` still raises 401, even with `auto_error=False`.)

## HTTP Basic auth

The browser shows a native username/password prompt when it receives a 401 with `WWW-Authenticate: Basic` (`docs_src/security/tutorial006_an_py310.py`):

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()

security = HTTPBasic()


@app.get("/users/me")
def read_current_user(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    return {"username": credentials.username, "password": credentials.password}
```

### Checking credentials safely

Compare with `secrets.compare_digest()` to avoid **timing attacks** (`tutorial007_an_py310.py`):

```python
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

Why: a naive `==` returns as soon as the first character differs, so response time leaks how much of a guess was correct (`"johndoe"` vs `"stanleyjobsox"` takes measurably longer to reject). `compare_digest` takes the same time regardless. Encode to UTF-8 bytes first, because `compare_digest` only accepts ASCII `str` or bytes. Always return `WWW-Authenticate: Basic` with the 401 so browsers re-prompt. In real apps, compare against hashed passwords ([OAuth2 with JWT](oauth2-jwt.md)).

## Bearer tokens without OAuth2: `HTTPBearer`

```python
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer()


@app.get("/me")
def read_me(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    return {"token": credentials.credentials}  # scheme == "Bearer"
```

The `Authorization` value is split at the first space into `scheme` and `credentials`; a non-`Bearer` scheme is treated as missing. Unlike `OAuth2PasswordBearer`, it doesn't document a token URL — use it for tokens issued elsewhere (API gateways, external identity providers).

## API keys

```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")


@app.get("/items/")
async def read_items(api_key: Annotated[str, Depends(api_key_header)]):
    if not secrets.compare_digest(api_key, EXPECTED_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return [...]
```

`APIKeyQuery(name="api_key")` and `APIKeyCookie(name="session")` work the same way, reading `request.query_params` and `request.cookies`. Headers are generally preferable to query parameters (which end up in logs and browser history).

## OpenID Connect

`OpenIdConnect(openIdConnectUrl="https://.../.well-known/openid-configuration")` documents an OpenID Connect discovery URL in OpenAPI and returns the raw `Authorization` header value (e.g. `"Bearer eyJ..."`). Token validation is up to you (or a library).

## Combining and scoping

- Use these as parameter dependencies, in `dependencies=[...]`, or on routers/apps to protect groups of routes ([Dependencies in Decorators](../dependencies/decorator-and-global-dependencies.md)).
- Multiple schemes on one operation all appear in OpenAPI.
- For scopes (fine-grained permissions), use OAuth2 with `Security()` — [OAuth2 Scopes](oauth2-scopes.md).

## Related

- [Security Basics: OAuth2 Password Flow and Current User](oauth2-password-flow.md)
- [Handling Errors](../errors/handling-errors.md) — 401 vs 403
- [Header and Cookie Parameters](../request/headers-and-cookies.md)
