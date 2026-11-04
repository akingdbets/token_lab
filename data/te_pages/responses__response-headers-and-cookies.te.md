---
type: guide
title: Setting Response Headers and Cookies
description: Set Response headers and cookies either through an injected temporary Response parameter (keeping response_model filtering) or directly on a returned Response, with set_cookie/delete_cookie options and CORS expose_headers.
tags: [responses, headers, cookies, set_cookie, Response-parameter, CORS]
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
    resource: repo://docs/en/docs/advanced/Response-headers.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: SETTING Response HEADERS AND COOKIES

TWO METHODS, LIKE SETTING [STATUS CODES](status-codes.md).

H2: 1. A `Response` PARAMETER (RECOMMENDED WHEN RETURNING DATA)

DECLARE PARAMETER TYPE `Response`. FastAPI INJECTS A **TEMPORARY**
Response OBJECT; SET HEADERS/COOKIES ON IT, THEN RETURN DATA NORMALLY.
FastAPI COPIES TEMPORARY Response HEADERS, COOKIES, AND SET STATUS CODE
ONTO FINAL Response; FINAL Response USES RETURN value AND `response_model`
FILTERING.

HEADERS (`docs_src/response_headers/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/headers-and-object/")
def get_headers(response: Response):
    response.headers["X-Cat-Dog"] = "alone in the world"
    return {"message": "Hello World"}
```

COOKIES (`docs_src/response_cookies/tutorial002_py310.py`):

```python
from fastapi import FastAPI, Response

app = FastAPI()


@app.post("/cookie-and-object/")
def create_cookie(response: Response):
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return {"message": "Come to the dark side, we have cookies"}
```

`Response` PARAMETER ALSO WORKS IN **DEPENDENCIES**; e.g., DEPENDENCY
REFRESHES SESSION COOKIE FOR EVERY REQUEST.

INTERNALLY, INJECTED Response RAW HEADERS APPEND TO FINAL Response:
`response.headers.raw.extend(solved_result.response.headers.raw)` IN
`fastapi/routing.py`.

H2: 2. RETURNING A `Response` DIRECTLY

BUILD Response YOURSELF; SET HEADERS/COOKIES ON IT
(`docs_src/response_headers/tutorial001_py310.py`):

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

COOKIES (`docs_src/response_cookies/tutorial001_py310.py`):

```python
@app.post("/cookie/")
def create_cookie():
    content = {"message": "Come to the dark side, we have cookies"}
    response = JSONResponse(content=content)
    response.set_cookie(key="fakesession", value="fake-cookie-session-value")
    return response
```

NOTE: DIRECTLY RETURNED Response SKIPS `response_model`
VALIDATION/FILTERING; ENSURE CONTENT MATCHES INTENDED Response
([CUSTOM RESPONSES](custom-responses.md)).

H2: `set_cookie` OPTIONS

`Response.set_cookie()` (FROM Starlette) ACCEPTS:

| ARGUMENT | MEANING |
|----------|---------|
| `key`, `value` | COOKIE NAME AND value |
| `max_age` | LIFETIME IN SECONDS |
| `expires` | EXPIRY: SECONDS, `datetime`, OR DATE STRING |
| `path` | path SCOPE; DEFAULT `/` |
| `domain` | domain SCOPE |
| `secure` | SEND ONLY OVER HTTPS |
| `httponly` | NOT ACCESSIBLE TO JavaScript |
| `samesite` | `"lax"` (DEFAULT), `"strict"` OR `"none"` |

REMOVE ONE WITH `response.delete_cookie(key, ...)`. FOR SESSION/AUTH
COOKIES, SET `httponly=True`, `secure=True`, AND SUITABLE `samesite`.

H2: HEADERS AND BROWSERS

- CUSTOM PROPRIETARY HEADERS CONVENTIONALLY USE `X-` PREFIX.
- FOR JavaScript IN A BROWSER ON **ANOTHER ORIGIN** TO READ CUSTOM
  Response HEADER, LIST IT IN `CORSMiddleware(expose_headers=[...])`
  ([CORS](../middleware/cors.md)).

H2: RELATED

- [Response STATUS CODES](status-codes.md) — CHANGE STATUS VIA SAME
  `Response` PARAMETER.
- [HEADER AND COOKIE PARAMETERS](../request/headers-and-cookies.md) —
  READ HEADERS/COOKIES FROM REQUESTS.
- [MIDDLEWARE](../middleware/middleware.md) — ADD HEADERS TO EVERY Response.
