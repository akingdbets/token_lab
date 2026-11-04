---
Type: guide
title: CORS (Cross-Origin Resource Sharing)
description: ALLOW BROWSER FRONTENDS ON OTHER ORIGINS TO CALL YOUR API WITH CORSMiddleware — ORIGINS, PREFLIGHT AND SIMPLE REQUESTS, allow_origins, allow_origin_regex, allow_methods, allow_headers, allow_credentials, expose_headers, max_age AND WILDCARD RESTRICTIONS.
tags: [cors, CORSMiddleware, middleware, origins, preflight, browser, frontend]
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

H1: CORS (Cross-Origin Resource Sharing)

CORS MATTERS WHEN JavaScript RUNNING IN A **BROWSER** CALLS YOUR BACKEND FROM A **DIFFERENT Origin**.
SERVER-TO-SERVER CALLS, `curl`, MOBILE APPS AND YOUR TESTS ARE NOT SUBJECT TO CORS.

H2: WHAT IS AN Origin

Origin = PROTOCOL + DOMAIN + PORT.
THESE ARE DIFFERENT ORIGINS:

- `http://localhost`
- `https://localhost`
- `http://localhost:8080`

IF FRONTEND AT `http://localhost:8080` CALLS BACKEND AT `http://localhost` (PORT 80),
BROWSER FIRST ASKS BACKEND WHETHER THAT Origin IS ALLOWED.
ONLY IF BACKEND ANSWERS WITH RIGHT HEADERS DOES BROWSER LET FRONTEND Request AND RESPONSE THROUGH.

H2: USING `CORSMiddleware`

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

`fastapi.middleware.cors.CORSMiddleware` IS Starlette's `CORSMiddleware`, RE-EXPORTED.

H2: PARAMETERS

DEFAULTS ARE **RESTRICTIVE**; ENABLE WHAT BROWSERS MAY USE.

| PARAMETER | MEANING | DEFAULT |
|-----------|---------|---------|
| `allow_origins` | ALLOWED-Origin LIST, e.g. `["https://example.org", "https://www.example.org"]`; `["*"]` ALLOWS ANY | `[]` |
| `allow_origin_regex` | REGEX MATCHED AGAINST Origin, e.g. `r"https://.*\.example\.org"` | `None` |
| `allow_methods` | METHODS ALLOWED FOR CROSS-Origin REQUESTS; `["*"]` ALLOWS ALL STANDARD METHODS | `["GET"]` |
| `allow_headers` | ALLOWED Request HEADERS; `["*"]` ALLOWS ALL. `Accept`, `Accept-Language`, `Content-Language` AND `Content-Type` ALWAYS ALLOWED FOR SIMPLE REQUESTS | `[]` |
| `allow_credentials` | ALLOW COOKIES / `Authorization` HEADERS CROSS-Origin | `False` |
| `expose_headers` | RESPONSE HEADERS BROWSER MAY READ FROM JS | `[]` |
| `max_age` | SECONDS BROWSERS MAY CACHE PREFLIGHT RESPONSES | `600` |

H2: WILDCARDS AND CREDENTIALS

`allow_origins=["*"]` ALLOWS ANY Origin, BUT ONLY FOR REQUESTS **WITHOUT CREDENTIALS**
(NO COOKIES, NO `Authorization: Bearer ...`).
PER CORS SPECIFICATION, CREDENTIALED REQUESTS REQUIRE EXPLICIT VALUES:
DOCS STATE `allow_origins`, `allow_methods` AND `allow_headers` SHOULD NOT BE `["*"]`
WHEN `allow_credentials=True`.
FOR ANYTHING INVOLVING LOGIN, **LIST YOUR FRONTEND ORIGINS EXPLICITLY**.

H2: HOW THE MIDDLEWARE RESPONDS

- **PREFLIGHT REQUESTS** — `OPTIONS` REQUESTS CARRYING `Origin` AND
  `Access-Control-Request-Method` HEADERS.
  MIDDLEWARE ANSWERS THEM ITSELF WITH CORS HEADERS AND `200` (ALLOWED)
  OR `400` (NOT ALLOWED); YOUR ENDPOINTS NEVER SEE THEM.
- **SIMPLE REQUESTS** — ANY Request WITH AN `Origin` HEADER.
  Request PROCEEDS NORMALLY; CORS HEADERS ARE ADDED TO RESPONSE.

H2: PRACTICAL TIPS

- ADD `CORSMiddleware` TO WRAP EVERYTHING:
  WITH `add_middleware`, **LAST ADDED MIDDLEWARE IS OUTERMOST**.
  ADDING CORS LAST ENSURES EVEN ERROR RESPONSES GET CORS HEADERS.
  SEE [MIDDLEWARE](middleware.md).
- IF YOUR FRONTEND IS SERVED BY THE SAME APP (SAME Origin), e.g. VIA
  [`app.frontend()`](../app-structure/static-files-templates-and-frontend.md),
  CORS IS UNNECESSARY.
- WHEN DEBUGGING, CHECK BROWSER DEV-TOOLS CONSOLE:
  BROWSER REPORTS CORS FAILURES, WHILE SERVER MAY SHOW A SUCCESSFUL RESPONSE.
H2: RELATED

- [MIDDLEWARE](middleware.md)
- [STATIC FILES, TEMPLATES AND FRONTENDS](../app-structure/static-files-templates-and-frontend.md)
- [SETTING RESPONSE HEADERS AND COOKIES](../responses/response-headers-and-cookies.md) — CUSTOM HEADERS MUST BE LISTED IN `expose_headers` FOR BROWSER JS READABILITY
