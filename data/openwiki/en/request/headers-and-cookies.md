---
type: guide
title: Header and Cookie Parameters
description: Read request headers with Header() (automatic underscore-to-hyphen conversion, convert_underscores, duplicate headers as lists) and cookies with Cookie(), and group them in Pydantic header/cookie parameter models with extra='forbid'.
tags: [headers, header, cookies, cookie, parameters, convert_underscores, parameter-models]
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
    resource: repo://docs/en/docs/tutorial/cookie-param-models.md
  - id: openwiki-source-92b8161cd107b8fe2397b104
    resource: repo://docs/en/docs/tutorial/cookie-params.md
  - id: openwiki-source-018921fd9b7328bb4c81647c
    resource: repo://docs/en/docs/tutorial/header-params.md
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Header and Cookie Parameters

`Header` and `Cookie` work like `Query` and `Path`: same validation and metadata parameters, declared with `Annotated`. Without them, a scalar parameter would be interpreted as a query parameter.

## Headers: `Header()`

`docs_src/header_params/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI()


@app.get("/items/")
async def read_items(user_agent: Annotated[str | None, Header()] = None):
    return {"User-Agent": user_agent}
```

### Automatic conversion

Most HTTP headers use hyphens (`User-Agent`), which aren't valid in Python names. By default `Header` converts underscores to hyphens, so `user_agent` reads the `User-Agent` header. Headers are case-insensitive, so snake_case names work.

To disable the conversion (`tutorial002_an_py310.py`):

```python
@app.get("/items/")
async def read_items(
    strange_header: Annotated[str | None, Header(convert_underscores=False)] = None,
):
    return {"strange_header": strange_header}
```

Caution: some HTTP proxies and servers reject headers containing underscores.

### Duplicate headers

A header can appear several times. Declare a list to receive all values (`tutorial003_an_py310.py`):

```python
@app.get("/items/")
async def read_items(x_token: Annotated[list[str] | None, Header()] = None):
    return {"X-Token values": x_token}
```

Sending `X-Token: foo` and `X-Token: bar` returns all values in a list, e.g. `{"X-Token values": ["bar", "foo"]}`.

## Cookies: `Cookie()`

`docs_src/cookie_params/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import Cookie, FastAPI

app = FastAPI()


@app.get("/items/")
async def read_items(ads_id: Annotated[str | None, Cookie()] = None):
    return {"ads_id": ads_id}
```

Browsers manage cookies themselves and don't let JavaScript set arbitrary ones, so **"Try it out" in the docs UI can't send cookies** — test with a real browser, `curl`, or `TestClient`. To *set* cookies, see [Setting Response Headers and Cookies](../responses/response-headers-and-cookies.md).

`Header` and `Cookie` (like `Path` and `Query`) are subclasses of an internal `Param` class; import them from `fastapi`.

## Parameter models

Group related headers or cookies into a Pydantic model and declare it with `Header()` / `Cookie()`. FastAPI extracts each field from the request and validates the model.

### Header model

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

Underscore conversion applies to the model's fields too (`save_data` ↔ `Save-Data`); disable it with `Header(convert_underscores=False)` (`tutorial003_an_py310.py`). List fields (`x_tag`) collect duplicate headers.

### Cookie model

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

### Forbidding extra values

Add `model_config = {"extra": "forbid"}` to reject anything not declared (`header_param_models/tutorial002_an_py310.py`, `cookie_param_models/tutorial002_an_py310.py`):

```python
class Cookies(BaseModel):
    model_config = {"extra": "forbid"}

    session_id: str
    fatebook_tracker: str | None = None
    googall_tracker: str | None = None
```

A request with an unexpected cookie (e.g. a `santa_tracker` cookie) or header receives a 422 error of type `extra_forbidden`. This is handy for cookie consent: if a client sends cookies you didn't declare, you can reject them.

Parameter models work the same way for [query parameters](query-parameters.md) and [forms](forms-and-files.md).

## Related

- [Query Parameters](query-parameters.md)
- [Security Basics](../security/oauth2-password-flow.md) — the `Authorization` header via security utilities
- [HTTP Basic, Bearer, API Keys](../security/http-basic-and-api-keys.md) — `APIKeyHeader`, `APIKeyCookie`
