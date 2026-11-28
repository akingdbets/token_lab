- `Header` and `Cookie` work like `Query` and `Path`: they use the same validation and metadata parameters and are declared with `Annotated`. Without them, a scalar parameter is interpreted as a query parameter. Import `Header` and `Cookie` from `fastapi`; both are subclasses of internal `Param`.

- ## Headers: `Header()`
  - Example: `user_agent: Annotated[str | None, Header()] = None`; returns the `User-Agent` header. HTTP header names are case-insensitive.
  - By default, `Header` converts underscores to hyphens (`user_agent` reads `User-Agent`). Disable conversion with `Header(convert_underscores=False)`. Some HTTP proxies and servers reject headers containing underscores.
  - To receive duplicate headers, declare a list: `x_token: Annotated[list[str] | None, Header()] = None`. Sending `X-Token: foo` and `X-Token: bar` returns all values in a list, e.g. `{"X-Token values": ["bar", "foo"]}`.

- ## Cookies: `Cookie()`
  - Example: `ads_id: Annotated[str | None, Cookie()] = None`.
  - Browsers manage cookies and do not let JavaScript set arbitrary ones, so the docs UI “Try it out” cannot send cookies. Test with a real browser, `curl`, or `TestClient`. To set cookies, see [Setting Response Headers and Cookies](../responses/response-headers-and-cookies.md).

- ## Parameter models
  - Group related headers or cookies in a Pydantic model declared with `Header()` or `Cookie()`; FastAPI extracts each field from the request and validates the model.
  - Header model fields: `host: str`, `save_data: bool`, `if_modified_since: str | None = None`, `traceparent: str | None = None`, `x_tag: list[str] = []`. Underscore conversion also applies to fields (`save_data` ↔ `Save-Data`); disable with `Header(convert_underscores=False)`. List fields collect duplicate headers.
  - Cookie model fields: `session_id: str`, `fatebook_tracker: str | None = None`, `googall_tracker: str | None = None`.
  - Add `model_config = {"extra": "forbid"}` to reject undeclared values. An unexpected cookie (e.g. `santa_tracker`) or header produces a 422 error of type `extra_forbidden`. This can reject cookies clients send that were not declared, e.g. for cookie consent.
  - Parameter models also work for [query parameters](query-parameters.md) and [forms](forms-and-files.md).

- ## Related
  - [Query Parameters](query-parameters.md); [Security Basics](../security/oauth2-password-flow.md) (`Authorization` header via security utilities); [HTTP Basic, Bearer, API Keys](../security/http-basic-and-api-keys.md) (`APIKeyHeader`, `APIKeyCookie`).
