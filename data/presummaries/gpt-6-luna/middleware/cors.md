- **CORS and origins**
  - CORS applies when JavaScript in a **browser** calls a backend from a **different origin**; server-to-server calls, `curl`, mobile apps and tests are not subject to CORS.
  - An origin is **protocol + domain + port**. `http://localhost`, `https://localhost` and `http://localhost:8080` are different origins. For a frontend at `http://localhost:8080` calling a backend at `http://localhost` (port 80), the browser asks whether the origin is allowed; it lets the request and response through only if the backend returns the right headers.

- **Using `CORSMiddleware`**
  - `fastapi.middleware.cors.CORSMiddleware` is Starlette's `CORSMiddleware`, re-exported.
  - Example imports: `from fastapi import FastAPI` and `from fastapi.middleware.cors import CORSMiddleware`. Configure with `app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`; the example origins are `http://localhost.tiangolo.com`, `https://localhost.tiangolo.com`, `http://localhost` and `http://localhost:8080`.

- **Parameters and defaults**
  - Defaults are **restrictive**; enable what browsers may use.
  - `allow_origins=[]`: allowed origins; `["*"]` allows any.
  - `allow_origin_regex=None`: regex matched against origin.
  - `allow_methods=["GET"]`: allowed cross-origin methods; `["*"]` means all standard methods.
  - `allow_headers=[]`: allowed request headers; `["*"]` means all. `Accept`, `Accept-Language`, `Content-Language` and `Content-Type` are always allowed for simple requests.
  - `allow_credentials=False`: allow cookies / `Authorization` headers cross-origin.
  - `expose_headers=[]`: response headers browser JS may read.
  - `max_age=600`: seconds browsers may cache preflight responses.

- **Wildcards, credentials and responses**
  - `allow_origins=["*"]` allows any origin only for requests **without credentials** (no cookies, no `Authorization: Bearer ...`). With `allow_credentials=True`, docs say `allow_origins`, `allow_methods` and `allow_headers` should not be `["*"]`; list frontend origins explicitly for login.
  - Preflight `OPTIONS` requests with `Origin` and `Access-Control-Request-Method` are answered by middleware with CORS headers and `200` (allowed) or `400` (not allowed); endpoints never see them. Simple requests (any request with `Origin`) proceed normally and get CORS response headers.

- **Practical tips**
  - Last added middleware is outermost; add CORS last so error responses get CORS headers. Same-origin frontends, e.g. `app.frontend()`, need no CORS. Debug in browser dev-tools console: browser reports CORS failures; server may show success.
  - Custom headers must be listed in `expose_headers` to be readable by browser JS.
