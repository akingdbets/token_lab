- **Overview**
  - All classes in `fastapi.security` are dependencies: configured instances with `async def __call__(self, request)` that extract credentials and register an OpenAPI security scheme (including an “Authorize” button). They do **not** verify credentials; that is your code’s job.
  - `HTTPBasic` reads `Authorization: Basic <base64>` and returns `HTTPBasicCredentials(username, password)`. `HTTPBearer` reads `Authorization: Bearer <token>`; `HTTPDigest` reads `Authorization: Digest ...`; both return `HTTPAuthorizationCredentials(scheme, credentials)`. `APIKeyHeader(name=...)`, `APIKeyQuery(name=...)`, and `APIKeyCookie(name=...)` read the named header, query parameter, or cookie and return `str`. `OpenIdConnect(openIdConnectUrl=...)` reads the raw `Authorization` header and returns `str`. `OAuth2PasswordBearer`, `OAuth2AuthorizationCodeBearer`, and `OAuth2` return bearer-token `str` (see Security Basics).
  - Common options: `scheme_name` (OpenAPI name; defaults to class name), `description`, `auto_error`.

- **Missing credentials: `auto_error` and 401**
  - `auto_error=True` (default): missing or malformed credentials raise `HTTPException(401, "Not authenticated")` with `WWW-Authenticate`: `Basic` (or `Basic realm="..."` if `realm` is set), `Bearer`, `Digest`, `APIKey` (not standardized, but included per HTTP spec requirement for 401), or `Bearer` for `OpenIdConnect` and OAuth2.
  - Since FastAPI 0.122.0 this is **401**, previously **403**. Override `make_not_authenticated_error()` to restore 403.
  - `auto_error=False` returns `None`, allowing optional authentication or trying schemes in sequence. Exception: `HTTPBasic` still raises 401 if a present header has invalid base64 or no `:`.
  - Example configuration: `APIKeyHeader(name="X-API-Key", auto_error=False)` and `HTTPBearer(auto_error=False)`.

- **HTTP Basic auth**
  - A 401 with `WWW-Authenticate: Basic` prompts the browser for username/password. `HTTPBasic()` supplies `HTTPBasicCredentials`; fields are `credentials.username` and `credentials.password`.
  - Use `secrets.compare_digest()` to prevent timing attacks: naive `==` returns on the first differing character and leaks guess progress through response time. Encode credentials with `.encode("utf8")` first; `compare_digest` accepts only ASCII `str` or bytes. On failure, raise `HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"})`. Always return that header with 401 to make browsers re-prompt. In real apps, compare against hashed passwords.

- **Bearer tokens without OAuth2: `HTTPBearer`**
  - `Authorization` is split at the first space into `scheme` and `credentials`; a non-`Bearer` scheme is treated as missing. Unlike `OAuth2PasswordBearer`, it does not document a token URL; use for tokens issued elsewhere, such as API gateways or external identity providers.

- **API keys**
  - `APIKeyHeader(name="X-API-Key")` can protect a route; validate the key yourself, e.g. with `secrets.compare_digest`, and raise 401 for an invalid key. `APIKeyQuery(name="api_key")` and `APIKeyCookie(name="session")` read `request.query_params` and `request.cookies`. Headers are generally preferable to query parameters, which end up in logs and browser history.

- **OpenID Connect**
  - `OpenIdConnect(openIdConnectUrl="https://.../.well-known/openid-configuration")` documents the discovery URL in OpenAPI and returns the raw header value (e.g. `"Bearer eyJ..."`). Token validation is up to you or a library.

- **Combining and scoping**
  - Use as parameter dependencies, in `dependencies=[...]`, or on routers/apps to protect route groups. Multiple schemes on one operation all appear in OpenAPI. For fine-grained permissions, use OAuth2 with `Security()`.
