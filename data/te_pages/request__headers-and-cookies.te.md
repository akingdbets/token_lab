---
type: guide
title: Header and Cookie Parameters
description: Read request headers with Header() (automatic underscore-to-hyphen conversion, convert_underscores, duplicate headers as lists) and cookies with Cookie(), and group them in Pydantic Header/Cookie parameter models with extra='forbid'.
tags: [headers, Header, cookies, Cookie, parameters, convert_underscores, parameter-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-271b7b386e680a403ae9c8fa
    resource: repo://docs_src/cookie_param_models/tutorial002_an_py310.py
  - id: openwiki-source-77f5b306ccc4bddccb0a42cd
    resource: repo://docs_src/cookie_params/tutorial001_an_py310.py
  - id: openwiki-source-5a73b75e06fb149013513757
    resource: repo://docs_src/header_param_models/tutorial001_an_py310.py
  - id: openwiki-source-70dcd567830447381dd927d1
    resource: repo://docs_src/header_param_models/tutorial002_an_py310.py
  - id: openwiki-source-ecd3aca0ab3476cf99a5f88b
    resource: repo://docs_src/header_params/tutorial001_an_py310.py
  - id: openwiki-source-14c4faaaab7b5cb2487b7da0
    resource: repo://docs_src/header_params/tutorial002_an_py310.py
  - id: openwiki-source-3755bb50687e08f4a8baa3db
    resource: repo://docs_src/header_params/tutorial003_an_py310.py
  - id: openwiki-source-156fb14d5ad8ae2e714b915d
    resource: repo://docs/en/docs/tutorial/Cookie-Param-models.md
  - id: openwiki-source-92b8161cd107b8fe2397b104
    resource: repo://docs/en/docs/tutorial/Cookie-params.md
  - id: openwiki-source-018921fd9b7328bb4c81647c
    resource: repo://docs/en/docs/tutorial/Header-params.md
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Header and Cookie Parameters

`Header` AND `Cookie` WORK LIKE `Query` AND `Path`: SAME VALIDATION AND METADATA PARAMETERS; DECLARE WITH `Annotated`. WITHOUT THEM, SCALAR PARAMETERS ARE Query PARAMETERS.

H2: Headers: `Header()`

`docs_src/header_params/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI()


@app.get("/items/")
async def read_items(user_agent: Annotated[str | None, Header()] = None):
    return {"User-Agent": user_agent}
```

H3: Automatic conversion

MOST HTTP HEADERS USE HYPHENS (`User-Agent`), INVALID IN PYTHON NAMES. BY DEFAULT, `Header` CONVERTS UNDERSCORES TO HYPHENS: `user_agent` READS THE `User-Agent` Header. HEADERS ARE CASE-INSENSITIVE; snake_case NAMES WORK.

DISABLE CONVERSION (`tutorial002_an_py310.py`):

```python
@app.get("/items/")
async def read_items(
    strange_header: Annotated[str | None, Header(convert_underscores=False)] = None,
):
    return {"strange_header": strange_header}
```

CAUTION: SOME HTTP PROXIES AND SERVERS REJECT HEADERS WITH UNDERSCORES.

H3: Duplicate headers

HEADERS CAN APPEAR MULTIPLE TIMES. DECLARE A LIST TO RECEIVE ALL values (`tutorial003_an_py310.py`):

```python
@app.get("/items/")
async def read_items(x_token: Annotated[list[str] | None, Header()] = None):
    return {"X-Token values": x_token}
```

SENDING `X-Token: foo` AND `X-Token: bar` RETURNS ALL values IN A LIST, e.g. `{"X-Token values": ["bar", "foo"]}`.

H2: Cookies: `Cookie()`

`docs_src/cookie_params/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import Cookie, FastAPI

app = FastAPI()


@app.get("/items/")
async def read_items(ads_id: Annotated[str | None, Cookie()] = None):
    return {"ads_id": ads_id}
```

BROWSERS MANAGE COOKIES THEMSELVES AND PREVENT JavaScript FROM SETTING ARBITRARY COOKIES. THEREFORE, **"Try it out" IN DOCS UI CANNOT SEND COOKIES** — TEST WITH A REAL BROWSER, `curl`, OR `TestClient`. TO *SET* COOKIES, SEE [Setting Response Headers and Cookies](../responses/response-headers-and-cookies.md).

`Header` AND `Cookie` (LIKE `Path` AND `Query`) ARE SUBCLASSES OF INTERNAL `Param`; IMPORT THEM FROM `fastapi`.

H2: Parameter models

GROUP RELATED HEADERS OR COOKIES IN A PYDANTIC MODEL; DECLARE WITH `Header()` / `Cookie()`. FASTAPI EXTRACTS EACH FIELD FROM REQUEST AND VALIDATES THE MODEL.

H3: Header model

`docs_src/header_param_models/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI()


class CommonHeaders(BaseModel):
    host: str
    save_data: bool
    if_modified_since: str | None = None
    traceparent: str | None = None
    x_tag: list[str] = []


@app.get("/items/")
async def read_items(headers: Annotated[CommonHeaders, Header()]):
    return headers
```

UNDERSCORE CONVERSION ALSO APPLIES TO MODEL FIELDS (`save_data` ↔ `Save-Data`); DISABLE WITH `Header(convert_underscores=False)` (`tutorial003_an_py310.py`). LIST FIELDS (`x_tag`) COLLECT DUPLICATE HEADERS.

H3: Cookie model

`docs_src/cookie_param_models/tutorial001_an_py310.py`:

```python
class Cookies(BaseModel):
    session_id: str
    fatebook_tracker: str | None = None
    googall_tracker: str | None = None


@app.get("/items/")
async def read_items(cookies: Annotated[Cookies, Cookie()]):
    return cookies
```

H3: Forbidding extra values

ADD `model_config = {"extra": "forbid"}` TO REJECT UNDECLARED values (`header_param_models/tutorial002_an_py310.py`, `cookie_param_models/tutorial002_an_py310.py`):

```python
class Cookies(BaseModel):
    model_config = {"extra": "forbid"}

    session_id: str
    fatebook_tracker: str | None = None
    googall_tracker: str | None = None
```

REQUEST WITH UNEXPECTED Cookie (e.g. `santa_tracker`) OR Header RECEIVES 422 ERROR, TYPE `extra_forbidden`. USEFUL FOR Cookie CONSENT: REJECT COOKIES CLIENT SENDS THAT YOU DIDN'T DECLARE.

PARAMETER MODELS WORK THE SAME WAY FOR [Query PARAMETERS](Query-parameters.md) AND [FORMS](forms-and-files.md).

H2: Related

- [Query Parameters](Query-parameters.md)
- [Security Basics](../security/oauth2-password-flow.md) — `Authorization` Header VIA SECURITY UTILITIES
- [HTTP Basic, Bearer, API Keys](../security/HTTP-basic-and-API-keys.md) — `APIKeyHeader`, `APIKeyCookie`
