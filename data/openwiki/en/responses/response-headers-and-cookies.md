---
type: guide
title: Setting Response Headers and Cookies
description: Set response headers and cookies either through an injected temporary Response parameter (keeping response_model filtering) or directly on a returned Response, with set_cookie/delete_cookie options and CORS expose_headers.
tags: [responses, headers, cookies, set_cookie, response-parameter, cors]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-912bba61eb50f67721444396
    resource: repo://docs_src/response_cookies/tutorial001_py310.py
  - id: openwiki-source-73233b6f8ab3f64d371b20c9
    resource: repo://docs_src/response_cookies/tutorial002_py310.py
  - id: openwiki-source-7e4d080657afa3a823176eeb
    resource: repo://docs_src/response_headers/tutorial001_py310.py
  - id: openwiki-source-27383bc92276586dd41deb78
    resource: repo://docs_src/response_headers/tutorial002_py310.py
  - id: openwiki-source-c21c031b09cf9ef3e4bbfeb0
    resource: repo://docs/en/docs/advanced/response-headers.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Setting Response Headers and Cookies

There are two ways, mirroring how [status codes](status-codes.md) can be set.

## 1. A `Response` parameter (recommended when returning data)

Declare a parameter of type `Response`. FastAPI injects a **temporary** response object; you set headers/cookies on it and return your data normally. FastAPI then copies the temporary response's headers, cookies (and status code, if you set one) onto the final response, which is still built from your return value and filtered by your `response_model`.

Headers (`docs_src/response_headers/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/headers-and-object/")
def get_headers(response: Response):
    response.headers["X-Cat-Dog"] = "alone in the world"
    return {"message": "Hello World"}
```

Cookies (`docs_src/response_cookies/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Response

app = FastAPI()


@app.post("/cookie-and-object/")
def create_cookie(response: Response):
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return {"message": "Come to the dark side, we have cookies"}
```

The `Response` parameter also works in **dependencies** — e.g. a dependency that refreshes a session cookie for every request.

Internally, the injected response's raw headers are appended to the final response (`response.headers.raw.extend(solved_result.response.headers.raw)` in `fastapi/routing.py`).

## 2. Returning a `Response` directly

Build the response yourself and set headers/cookies on it (`docs_src/response_headers/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/headers/")
def get_headers():
    content = {"message": "Hello World"}
    headers = {"X-Cat-Dog": "alone in the world", "Content-Language": "en-US"}
    return JSONResponse(content=content, headers=headers)
```

Cookies (`docs_src/response_cookies/tutorial001_py310.py`):

```python
@app.post("/cookie/")
def create_cookie():
    content = {"message": "Come to the dark side, we have cookies"}
    response = JSONResponse(content=content)
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return response
```

Remember: a directly returned response skips `response_model` validation/filtering — make sure the content is what you intend to send ([Custom Responses](custom-responses.md)).

## `set_cookie` options

`Response.set_cookie()` (from Starlette) accepts:

| Argument | Meaning |
|----------|---------|
| `key`, `value` | Cookie name and value |
| `max_age` | Lifetime in seconds |
| `expires` | Expiry as seconds, `datetime`, or date string |
| `path` | Path scope (default `/`) |
| `domain` | Domain scope |
| `secure` | Only send over HTTPS |
| `httponly` | Not accessible to JavaScript |
| `samesite` | `"lax"` (default), `"strict"` or `"none"` |

Use `response.delete_cookie(key, ...)` to remove one. For session/auth cookies, set `httponly=True`, `secure=True` and a suitable `samesite`.

## Headers and browsers

- Custom proprietary headers conventionally use the `X-` prefix.
- For JavaScript in a browser on **another origin** to read a custom response header, list it in `CORSMiddleware(expose_headers=[...])` ([CORS](../middleware/cors.md)).

## Related

- [Response Status Codes](status-codes.md) — changing the status via the same `Response` parameter
- [Header and Cookie Parameters](../request/headers-and-cookies.md) — reading them from requests
- [Middleware](../middleware/middleware.md) — adding headers to every response
