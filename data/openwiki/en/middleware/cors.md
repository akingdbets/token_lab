---
type: guide
title: CORS (Cross-Origin Resource Sharing)
description: Allow browser frontends on other origins to call your API with CORSMiddleware — origins, preflight and simple requests, allow_origins, allow_origin_regex, allow_methods, allow_headers, allow_credentials, expose_headers, max_age and wildcard restrictions.
tags: [cors, corsmiddleware, middleware, origins, preflight, browser, frontend]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-3ed00d832b86f38c6a7e25f5
    resource: repo://docs_src/cors/tutorial001_py310.py
  - id: openwiki-source-816bc9cdb160c0ea26152bb0
    resource: repo://docs/en/docs/tutorial/cors.md
  - id: openwiki-source-3056900339d12e52175aa0b1
    resource: repo://fastapi/middleware/cors.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# CORS (Cross-Origin Resource Sharing)

CORS matters when JavaScript running in a **browser** calls your backend from a **different origin**. Server-to-server calls, `curl`, mobile apps and your tests are not subject to CORS.

## What is an origin

An origin is **protocol + domain + port**. These are all different origins:

- `http://localhost`
- `https://localhost`
- `http://localhost:8080`

If a frontend on `http://localhost:8080` calls a backend on `http://localhost` (port 80), the browser first asks the backend whether that origin is allowed. Only if the backend answers with the right headers does the browser let the frontend's request (and response) through.

## Using `CORSMiddleware`

`docs_src/cors/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def main():
    return {"message": "Hello World"}
```

`fastapi.middleware.cors.CORSMiddleware` is Starlette's `CORSMiddleware`, re-exported.

## Parameters

The defaults are **restrictive**; you must enable what browsers may use.

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `allow_origins` | List of allowed origins, e.g. `["https://example.org", "https://www.example.org"]`; `["*"]` allows any | `[]` |
| `allow_origin_regex` | Regex matched against the origin, e.g. `r"https://.*\.example\.org"` | `None` |
| `allow_methods` | Allowed methods for cross-origin requests; `["*"]` for all standard methods | `["GET"]` |
| `allow_headers` | Allowed request headers; `["*"]` for all. `Accept`, `Accept-Language`, `Content-Language` and `Content-Type` are always allowed for simple requests | `[]` |
| `allow_credentials` | Allow cookies / `Authorization` headers cross-origin | `False` |
| `expose_headers` | Response headers the browser may read from JS | `[]` |
| `max_age` | Seconds browsers may cache preflight responses | `600` |

## Wildcards and credentials

`allow_origins=["*"]` allows any origin but only for requests **without credentials** (no cookies, no `Authorization: Bearer ...`). Per the CORS specification, credentialed requests require explicit values: the docs state that `allow_origins`, `allow_methods` and `allow_headers` should not be `["*"]` when `allow_credentials=True`. For anything involving login, **list your frontend origins explicitly**.

## How the middleware responds

- **Preflight requests** — `OPTIONS` requests carrying `Origin` and `Access-Control-Request-Method` headers. The middleware answers them itself with the CORS headers and `200` (allowed) or `400` (not allowed); your endpoints never see them.
- **Simple requests** — any request with an `Origin` header. The request goes through normally and CORS headers are added to the response.

## Practical tips

- Add `CORSMiddleware` so that it wraps everything: with `add_middleware`, the **last added middleware is the outermost**, so adding CORS last ensures even error responses get CORS headers. See [Middleware](middleware.md).
- If your frontend is served by the same app (same origin), e.g. via [`app.frontend()`](../app-structure/static-files-templates-and-frontend.md), you don't need CORS at all.
- When debugging, check the browser's dev-tools console: CORS failures are reported by the browser, while the server may show a successful response.

## Related

- [Middleware](middleware.md)
- [Static Files, Templates and Frontends](../app-structure/static-files-templates-and-frontend.md)
- [Setting Response Headers and Cookies](../responses/response-headers-and-cookies.md) — custom headers must be listed in `expose_headers` to be readable by browser JS
