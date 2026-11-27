## Concepts
- **OAuth2** specifies authentication/authorization and flows such as third-party login; it does not specify encryption and expects HTTPS. OAuth 1 was very different and is rarely used.
- **OpenID Connect** is built on OAuth2 (e.g. Google login), and is unrelated to older “OpenID”.
- **OpenAPI security schemes** include `apiKey` (header, query, cookie), `http` (Basic, Bearer, Digest), `oauth2` (`implicit`, `clientCredentials`, `authorizationCode`, `password`) and `openIdConnect` (auto-discovery). Docs UI uses them for **Authorize**.
- FastAPI’s `fastapi.security` tools are dependencies. The password flow has your API handle username/password and issue a token; it suits first-party apps.

## Step 1: require a bearer token
- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")` declares that clients POST username/password to relative URL `token`, resolved against the API root (so it works behind a proxy prefix); it does **not** create the endpoint.
- `OAuth2PasswordBearer` reads `Authorization: Bearer <token>` and returns the token string. Missing header or non-bearer scheme returns **401**, `{"detail": "Not authenticated"}`, and `WWW-Authenticate: Bearer`, unless `auto_error=False`, which returns `None`.
- Docs UI shows **Authorize** and lock icons. Flow: frontend collects credentials, POSTs them to `tokenUrl`, receives a token, then sends `Authorization: Bearer <token>` on later requests.

## Step 2: get the current user
- `get_current_user(token: Annotated[str, Depends(oauth2_scheme)])` turns a token into a user; the example uses `fake_decode_token` and a Pydantic `User` with `username`, optional `email`, `full_name`, and `disabled`.
- Path operations can declare `current_user: Annotated[User, Depends(get_current_user)]`. The user model may be anything (Pydantic, ORM objects, …). Protect endpoints individually or a whole router with `dependencies=[Depends(get_current_user)]` ([Dependencies in Decorators](../dependencies/decorator-and-global-dependencies.md)).

## Step 3: a simple `/token` login
- OAuth2 password flow credentials must be form fields, **not JSON**. `OAuth2PasswordRequestForm` reads them; it needs `python-multipart`.
- `UserInDB(User)` adds `hashed_password`; the example’s `fake_hash_password(password)` returns `"fakehashed" + password`. `/token` looks up `fake_users_db` by `form_data.username`, checks the password hash, and returns `{"access_token": user.username, "token_type": "bearer"}`. Wrong username or password raises `HTTPException(status_code=400, detail="Incorrect username or password")`.
- `OAuth2PasswordRequestForm` attributes are `username`, `password`, `scope` (space-separated; exposed as list `form_data.scopes`), and optional `grant_type`, `client_id`, `client_secret`. `OAuth2PasswordRequestFormStrict` additionally **requires** `grant_type="password"`, as the spec says.
- Token response JSON must contain `access_token` and `token_type` (`"bearer"`). The example token is just the username and is **insecure**; real tokens are covered in [OAuth2 with JWT](oauth2-jwt.md).
- If `get_current_user` gets no user, it raises **401** with `detail="Not authenticated"` and `WWW-Authenticate: Bearer`; this header is required by the spec for 401s. Disabled users raise **400**, `Inactive user`, through `get_current_active_user`, layered on `get_current_user`.
- In `/docs`, authorize as `johndoe` / `secret`, then call `/users/me`; after logout it returns 401. `alice` is disabled and gets “Inactive user”.

## Other OAuth2 classes
- `OAuth2AuthorizationCodeBearer(authorizationUrl=..., tokenUrl=...)` documents authorization-code flow (e.g. external identity provider) and reads bearer tokens the same way.
- `OAuth2(flows=...)` is the generic base for custom flows. Scopes use `OAuth2PasswordBearer(tokenUrl=..., scopes={...})` with `Security()` and `SecurityScopes`; see [OAuth2 Scopes](oauth2-scopes.md).

## Related
- [OAuth2 with JWT Tokens and Password Hashing](oauth2-jwt.md)
- [HTTP Basic, Bearer, API Keys and OpenID Connect](http-basic-and-api-keys.md)
- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
