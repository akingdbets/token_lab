---
type: guide
title: OAuth2 scopes
description: Add fine-grained permissions with OAuth2 scopes — declare available scopes on OAuth2PasswordBearer, request them per dependency with Security(..., scopes=[...]), and verify the accumulated required scopes centrally with SecurityScopes in get_current_user.
tags: [security, oauth2, scopes, SecurityScopes, security, permissions, JWT]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-2546c0a51f64c41d8cdb4e1b
    resource: repo://docs_src/security/tutorial005_an_py310.py
  - id: openwiki-source-836a87afb462f04c920b7ec8
    resource: repo://docs/en/docs/advanced/security/oauth2-scopes.md
  - id: openwiki-source-c46ca1d7e534ec6d650bb745
    resource: repo://FastAPI/dependencies/models.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://FastAPI/params.py
  - id: openwiki-source-4fc063f5745a6985eaa6d7be
    resource: repo://FastAPI/security/oauth2.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: OAuth2 scopes

scopes= NAMED permissions (STRINGS WITHOUT SPACES) CARRIED BY TOKEN.
THEY POWER PROMPTS LIKE "This app wants to read your profile" AT
GOOGLE, GitHub, FACEBOOK, ETC.
COMMON FORMS: `users:read`, `users:write`, `instagram_basic`,
`https://www.googleapis.com/auth/drive`.
OAUTH2 TREATS THEM AS OPAQUE STRINGS; YOU DEFINE THEIR MEANING.

FastAPI INTEGRATES scopes WITH DEPENDENCY INJECTION ∧ OpenAPI.
docs' **Authorize** DIALOG LETS users PICK scopes; EACH OPERATION
DOCUMENTS ITS REQUIRED scopes.

EXTENDS [OAuth2 with JWT](oauth2-jwt.md).
FULL CODE: `docs_src/security/tutorial005_an_py310.py`.

H2: 1. Declare available scopes

```python
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"me": "Read information about the current user.", "items": "Read items."},
)
```

DICT MAPS scope NAMES TO DESCRIPTIONS, SHOWN IN docs.

H2: 2. Put granted scopes in the token

`OAuth2PasswordRequestForm` READS `scope` FORM FIELD (SPACE-SEPARATED)
INTO `form_data.scopes`.
STORE THEM IN JWT:

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

SIMPLICITY: EXAMPLE GRANTS WHATEVER WAS REQUESTED.
REAL APP MUST GRANT ONLY scopes USER IS ALLOWED TO HAVE.

H2: 3. Require scopes with `Security()`

`Security` ≈ `Depends`, BUT ACCEPTS `scopes`; IT SUBCLASSES `Depends`
IN `fastapi.params`:

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

REQUIRED scopes ACCUMULATE DOWN DEPENDENCY TREE FOR EACH PATH OPERATION:

| Path operation | scopes required by `get_current_user` |
|----------------|----------------------------------------|
| `/users/me/` | `me` (from `get_current_active_user`) |
| `/users/me/items/` | `items` (path op) + `me` → `["items", "me"]` |
| `/status/` | none |

H2: 4. Verify centrally with `SecurityScopes`

DECLARE `SecurityScopes` PARAMETER IN TOKEN-CHECKING DEPENDENCY.
FastAPI FILLS IT WITH ALL scopes REQUIRED BY THIS DEPENDENCY
∧ ALL ITS DEPENDANTS FOR CURRENT PATH OPERATION:

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

- `security_scopes.scopes`=REQUIRED-scopes LIST;
  `security_scopes.scope_str`=SAME scopes, SPACE-SEPARATED.
- OAUTH2 SPEC: `WWW-Authenticate` HEADER INCLUDES REQUIRED scopes:
  `Bearer scope="me items"`.
- `TokenData` VALIDATES TOKEN CONTENT;
  `ValidationError` COUNTS AS INVALID CREDENTIALS.
- ONE FUNCTION CHECKS permissions FOR EVERY ENDPOINT;
  EACH ENDPOINT DECLARES ONLY ITS REQUIRED scopes.

DEPENDENCY CACHE KEY INCLUDES EFFECTIVE scopes.
∴ SAME DEPENDENCY WITH DIFFERENT scopes IN ONE REQUEST
RESOLVES SEPARATELY.

H2: Trying it

IN `/docs` → **Authorize**, LOG IN AS `johndoe` / `secret` AND TICK scopes.
WITHOUT `items`, `/users/me/items/` RETURNS `401 Not enough permissions`;
WITHOUT `me`, `/users/me/` DOES TOO.
THIS MIRRORS THIRD-PARTY APP EXPERIENCE WHEN USER GRANTS LIMITED permissions.

H2: Choosing a flow

PASSWORD FLOW SUITS YOUR OWN FRONTEND ∧ API.
FOR AN AUTHENTICATION PROVIDER USED BY THIRD-PARTY APPS
(LIKE GOOGLE/GitHub), USE ANOTHER FLOW.
AUTHORIZATION CODE FLOW IS MOST SECURE (`OAuth2AuthorizationCodeBearer`).
scopes CAN ALSO BE SET IN DECORATORS ∧ ROUTERS WITH
`dependencies=[Security(..., scopes=[...])]`.

H2: Related
- [OAuth2 WITH JWT TOKENS AND PASSWORD HASHING](oauth2-jwt.md)
- [SECURITY BASICS](oauth2-password-flow.md)
- [DEPENDENCY INJECTION BASICS](../dependencies/dependency-injection-basics.md)
