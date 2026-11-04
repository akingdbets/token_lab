---
type: reference
title: HTTP Basic, Bearer, API Keys and OpenID Connect
description: Use FastAPI's non-OAuth2 security utilities — HTTPBasic with HTTPBasicCredentials and timing-safe secrets.compare_digest checks, HTTPBearer/HTTPDigest with HTTPAuthorizationCredentials, APIKeyHeader/APIKeyQuery/APIKeyCookie and OpenIdConnect — plus auto_error, 401 responses and WWW-Authenticate headers.
tags: [security, HTTP-Basic, HTTPBearer, API-key, APIKeyHeader, OpenIdConnect, auto_error, compare_digest]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-f04305db4b88ede0ab5c7b4f
    resource: repo://docs_src/security/tutorial007_an_py310.py
  - id: openwiki-source-699fc43e71296fb54b4bd611
    resource: repo://docs/en/docs/advanced/security/HTTP-Basic-auth.md
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

H1: HTTP Basic, Bearer, API Keys and OpenID Connect

`fastapi.security` CLASSES ARE **dependencies**: CONFIGURED INSTANCES WITH
`async def __call__(self, request)` THAT EXTRACT credentials FROM request
AND REGISTER OpenAPI SECURITY SCHEMES (DOCS SHOW "Authorize" BUTTON).
THEY ONLY **EXTRACT** credentials; YOUR CODE MUST **VERIFY** THEM.

AVAILABLE CLASSES (`fastapi/security/__init__.py`):

| Class | Reads | Returns |
|-------|-------|---------|
| `HTTPBasic` | `Authorization: Basic <base64>` | `HTTPBasicCredentials(username, password)` |
| `HTTPBearer` | `Authorization: Bearer <token>` | `HTTPAuthorizationCredentials(scheme, credentials)` |
| `HTTPDigest` | `Authorization: Digest ...` | `HTTPAuthorizationCredentials` |
| `APIKeyHeader(name=...)` | the named header | `str` |
| `APIKeyQuery(name=...)` | the named query parameter | `str` |
| `APIKeyCookie(name=...)` | the named cookie | `str` |
| `OpenIdConnect(openIdConnectUrl=...)` | the raw `Authorization` header | `str` |
| `OAuth2PasswordBearer`, `OAuth2AuthorizationCodeBearer`, `OAuth2` | Bearer token | `str` — see [Security Basics](oauth2-password-flow.md) |

COMMON CONSTRUCTOR OPTIONS: `scheme_name` (OpenAPI name; DEFAULTS TO CLASS
name), `description`, `auto_error`.

H2: MISSING credentials: `auto_error` AND 401

`auto_error=True` (DEFAULT): MISSING OR MALFORMED credentials → DEPENDENCY
RAISES `HTTPException(401, "Not authenticated")` WITH `WWW-Authenticate` HEADER:

- `HTTPBasic`: `Basic` (OR `Basic realm="..."` IF `realm` SET)
- `HTTPBearer` / `HTTPDigest`: `Bearer` / `Digest`
- API KEYS: `APIKey` (Not STANDARDIZED; INCLUDED PER HTTP SPEC 401 REQUIREMENT)
- `OpenIdConnect` AND OAUTH2: `Bearer`

SINCE FASTAPI 0.122.0: **401** (PREVIOUSLY 403). RESTORE 403 BY OVERRIDING
`make_not_authenticated_error()` — SEE [Handling Errors](../errors/handling-errors.md).

`auto_error=False`: DEPENDENCY RETURNS `None`; ENABLES OPTIONAL AUTHENTICATION
OR SEQUENTIAL ATTEMPTS WITH MULTIPLE SCHEMES:

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

NOTE: `HTTPBasic` HEADER PRESENT BUT INVALID base64 OR MISSING `:` STILL
RAISES 401, EVEN WITH `auto_error=False`.

H2: HTTP Basic AUTH

BROWSER SHOWS NATIVE username/password PROMPT AFTER 401 WITH
`WWW-Authenticate: Basic` (`docs_src/security/tutorial006_an_py310.py`):

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

H3: CHECK credentials SAFELY

COMPARE USING `secrets.compare_digest()` TO PREVENT **TIMING ATTACKS**
(`tutorial007_an_py310.py`):

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

REASON: NAIVE `==` RETURNS ON FIRST DIFFERING CHARACTER; RESPONSE TIME
LEAKS HOW MUCH OF GUESS WAS CORRECT (`"johndoe"` VS `"stanleyjobsox"` TAKES
MEASURABLY LONGER TO REJECT). `compare_digest` TAKES SAME TIME REGARDLESS.
ENCODE AS UTF-8 BYTES FIRST: `compare_digest` ACCEPTS ONLY ASCII `str` OR
BYTES. ALWAYS RETURN `WWW-Authenticate: Basic` WITH 401, SO BROWSERS
RE-PROMPT. REAL APPS: COMPARE AGAINST HASHED PASSWORDS
([OAuth2 with JWT](oauth2-jwt.md)).

H2: Bearer TOKENS WITHOUT OAUTH2: `HTTPBearer`

```python
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer()


@app.get("/me")
def read_me(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    return {"token": credentials.credentials}  # scheme == "Bearer"
```
`Authorization` VALUE SPLITS AT FIRST SPACE INTO `scheme` AND `credentials`; NON-`Bearer` scheme COUNTS AS MISSING. UNLIKE `OAuth2PasswordBearer`, IT DOESN'T DOCUMENT A token URL; USE IT FOR TOKENS ISSUED ELSEWHERE (API GATEWAYS, EXTERNAL IDENTITY PROVIDERS).

H2: API KEYS

```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")


@app.get("/items/")
async def read_items(api_key: Annotated[str, Depends(api_key_header)]):
    if not secrets.compare_digest(api_key, EXPECTED_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return [...]
```

`APIKeyQuery(name="api_key")` AND `APIKeyCookie(name="session")` WORK THE SAME WAY: READ `request.query_params` AND `request.cookies`. HEADERS ARE GENERALLY PREFERABLE TO QUERY PARAMETERS; QUERY PARAMETERS END UP IN LOGS AND BROWSER HISTORY.

H2: OPENID CONNECT

`OpenIdConnect(openIdConnectUrl="https://.../.well-known/openid-configuration")` DOCUMENTS AN OPENID CONNECT DISCOVERY URL IN OpenAPI AND RETURNS THE RAW `Authorization` HEADER VALUE (e.g. `"Bearer eyJ..."`). token VALIDATION IS UP TO YOU OR A LIBRARY.

H2: COMBINING AND SCOPING

- USE THESE AS PARAMETER dependencies, IN `dependencies=[...]`, OR ON
  ROUTERS/APPS TO PROTECT ROUTE GROUPS ([dependencies IN DECORATORS](../dependencies/decorator-and-global-dependencies.md)).
- MULTIPLE SCHEMES ON ONE OPERATION ALL APPEAR IN OpenAPI.
- FOR SCOPES (FINE-GRAINED PERMISSIONS), USE OAUTH2 WITH `Security()` —
  [OAUTH2 SCOPES](oauth2-scopes.md).

H2: RELATED

- [SECURITY BASICS: OAUTH2 password FLOW AND CURRENT USER](oauth2-password-flow.md)
- [HANDLING ERRORS](../errors/handling-errors.md) — 401 VS 403
- [HEADER AND COOKIE PARAMETERS](../request/headers-and-cookies.md)
