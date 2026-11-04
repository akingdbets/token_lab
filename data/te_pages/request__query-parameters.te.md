---
type: guide
title: Query Parameters, String Validation and Query Models
description: DECLARE QUERY PARAMETERS: DEFAULTS, OPTIONAL/REQUIRED VALUES, bool CONVERSION; ADD Query() VALIDATION/METADATA (min_length, max_length, pattern, alias, title, description, deprecated, include_in_schema); ACCEPT LISTS; RUN AfterValidator CHECKS; GROUP PARAMETERS IN PYDANTIC QUERY MODELS.
tags: [query-parameters, query, validation, min_length, pattern, alias, AfterValidator, query-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-c3463ac642282d1295429819
    resource: repo://docs_src/query_param_models/tutorial001_an_py310.py
  - id: openwiki-source-f9fab8c4c0cd9a48fc290d64
    resource: repo://docs_src/query_param_models/tutorial002_an_py310.py
  - id: openwiki-source-bfecd207b62fd1add418af15
    resource: repo://docs_src/query_params_str_validations/tutorial004_an_py310.py
  - id: openwiki-source-4c543e970630d93ac9d2bc3c
    resource: repo://docs_src/query_params_str_validations/tutorial010_an_py310.py
  - id: openwiki-source-82bd0c2cd2f545b07ca9b4a9
    resource: repo://docs_src/query_params_str_validations/tutorial011_an_py310.py
  - id: openwiki-source-5a46921e30adc93528f07e41
    resource: repo://docs_src/query_params_str_validations/tutorial012_an_py310.py
  - id: openwiki-source-8d52852e029948a6134be659
    resource: repo://docs_src/query_params_str_validations/tutorial014_an_py310.py
  - id: openwiki-source-9002331d6a69fc47a47e97a1
    resource: repo://docs_src/query_params_str_validations/tutorial015_an_py310.py
  - id: openwiki-source-374e6010bbc0a7d7ac10f0c2
    resource: repo://docs_src/query_params/tutorial001_py310.py
  - id: openwiki-source-a953d8b52b06de4ee9a15262
    resource: repo://docs_src/query_params/tutorial003_py310.py
  - id: openwiki-source-dcf5db78241bb394f47b0e8a
    resource: repo://docs_src/query_params/tutorial006_py310.py
  - id: openwiki-source-7942b45ca7312e2116551132
    resource: repo://docs/en/docs/tutorial/query-param-models.md
  - id: openwiki-source-b32b25e66b7af40f3eae0f8b
    resource: repo://docs/en/docs/tutorial/query-params.md
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://FastAPI/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: QUERY PARAMETERS, STRING VALIDATION AND QUERY MODELS

H2: BASICS

FUNCTION PARAMETERS THAT AREN'T PATH PARAMETERS, PYDANTIC MODELS, OR
SPECIAL TYPES ARE QUERY PARAMETERS: `?key=value&...` URL COMPONENT
(`docs_src/query_params/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]


@app.get("/items/")
async def read_item(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]
```

`/items/?skip=20` → `skip=20, limit=10`. VALUES ARRIVE AS STRINGS;
CONVERTED/VALIDATED ACCORDING TO TYPE.

H3: OPTIONAL, REQUIRED AND DEFAULTS

default value DETERMINES WHETHER QUERY PARAMETER IS REQUIRED:

```python
@app.get("/items/{item_id}")
async def read_user_item(
    item_id: str, needy: str, skip: int = 0, limit: int | None = None
):
    item = {"item_id": item_id, "needy": needy, "skip": skip, "limit": limit}
    return item
```

(`tutorial006_py310.py`.)

- `needy: str` — REQUIRED; no default. OMITTING IT CAUSES 422 `missing` ERROR.
- `skip: int = 0` — OPTIONAL; HAS default.
- `limit: int | None = None` — OPTIONAL; `None` IF ABSENT.

FastAPI DISTINGUISHES PATH VS QUERY PARAMETERS BY NAME: NAMES IN PATH
TEMPLATE ARE PATH PARAMETERS; ALL OTHERS ARE QUERY PARAMETERS, IN ANY ORDER.

H3: `bool` CONVERSION

```python
async def read_item(item_id: str, q: str | None = None, short: bool = False):
```

(`tutorial003_py310.py`.) `short=1`, `short=True`, `short=true`, `short=on`
AND `short=yes` BECOME `True`; `0`, `false`, `off`, `no` BECOME `False`.

H2: `Query()`: VALIDATION AND METADATA

ADD CONSTRAINTS WITH `Query` INSIDE `Annotated`
(`docs_src/query_params_str_validations/tutorial002_an_py310.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/items/")
async def read_items(q: Annotated[str | None, Query(max_length=50)] = None):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results
```

`Annotated` SUPPORT ADDED IN FastAPI 0.95.0; RECOMMENDED STYLE.
OLDER STYLE: `q: str | None = Query(default=None, max_length=50)`;
default GOES INSIDE `Query`. WITH `Annotated`, default IS NORMAL PYTHON
default; FUNCTION REMAINS NORMALLY CALLABLE; TWO DEFAULTS CANNOT BE SET
ACCIDENTALLY.

H3: STRING CONSTRAINTS

```python
q: Annotated[
    str | None, Query(min_length=3, max_length=50, pattern="^fixedquery$")
] = None
```

(`tutorial004_an_py310.py`.) `pattern` IS A REGULAR EXPRESSION;
OLDER `regex=` PARAMETER IS deprecated IN FAVOR OF `pattern`.
NUMERIC CONSTRAINTS `gt`, `ge`, `lt`, `le` ALSO AVAILABLE
(SEE [PATH PARAMETERS](path-parameters.md)).

H3: REQUIRED WITH VALIDATION

- default MAKES PARAMETER OPTIONAL: `q: Annotated[str, Query(min_length=3)] = "fixedquery"` (`tutorial005`).
- no default MAKES PARAMETER REQUIRED: `q: Annotated[str, Query(min_length=3)]` (`tutorial006`).
- REQUIRED, BUT MAY BE `None`: `q: Annotated[str | None, Query(min_length=3)]`.
  CLIENT MUST SEND IT; `None` IS A VALID value (`tutorial006c`).

H3: LISTS (MULTIPLE VALUES)

DECLARE list TYPE WITH `Query()` EXPLICITLY; OTHERWISE, `list` IS
INTERPRETED AS REQUEST BODY (`tutorial011_an_py310.py`):

```python
@app.get("/items/")
async def read_items(q: Annotated[list[str] | None, Query()] = None):
    query_items = {"q": q}
    return query_items
```

`/items/?q=foo&q=bar` → `{"q": ["foo", "bar"]}`. default list:
`q: Annotated[list[str], Query()] = ["foo", "bar"]` (`tutorial012`).
BARE `list` WORKS, BUT items AREN'T TYPE-CHECKED (`tutorial013`).

H3: METADATA, ALIASES AND DEPRECATION

```python
@app.get("/items/")
async def read_items(
    q: Annotated[
        str | None,
        Query(
            alias="item-query",
            title="Query string",
            description="Query string for the items to search in the database that have a good match",
            min_length=3,
            max_length=50,
            pattern="^fixedquery$",
            deprecated=True,
        ),
    ] = None,
):
    ...
```

(`tutorial010_an_py310.py`.)
- `alias="item-query"` — URL USES `?item-query=...` (NOT A VALID PYTHON NAME); YOUR VARIABLE IS `q` (`tutorial009`).
- `title`, `description` — DOCUMENTATION.
- `deprecated=True` — STILL WORKS; MARKED deprecated IN THE DOCS.

H3: HIDING A PARAMETER FROM OpenAPI

```python
hidden_query: Annotated[str | None, Query(include_in_schema=False)] = None
```

(`tutorial014_an_py310.py`.) PARAMETER STILL WORKS; IT IS NOT DOCUMENTED.

H2: CUSTOM VALIDATION WITH `AfterValidator`

FOR CHECKS BUILT-IN PARAMETERS CANNOT EXPRESS, USE PYDANTIC'S `AfterValidator` IN `Annotated`; IT RUNS AFTER NORMAL TYPE VALIDATION (`tutorial015_an_py310.py`):

```python
import random
from typing import Annotated

from fastapi import FastAPI
from pydantic import AfterValidator

app = FastAPI()

data = {
    "isbn-9781529046137": "The Hitchhiker's Guide to the Galaxy",
    "imdb-tt0371724": "The Hitchhiker's Guide to the Galaxy",
    "isbn-9781439512982": "Isaac Asimov: The Complete Stories, Vol. 2",
}


def check_valid_id(id: str):
    if not id.startswith(("isbn-", "imdb-")):
        raise ValueError('Invalid ID format, it must start with "isbn-" or "imdb-"')
    return id


@app.get("/items/")
async def read_items(
    id: Annotated[str | None, AfterValidator(check_valid_id)] = None,
):
    if id:
        item = data.get(id)
    else:
        id, item = random.choice(list(data.items()))
    return {"id": id, "name": item}
```

RAISING `ValueError` PRODUCES A NORMAL 422 VALIDATION ERROR. PYDANTIC ALSO OFFERS `BeforeValidator` AND OTHERS. FOR CHECKS REQUIRING OTHER RESOURCES (e.g., A DATABASE LOOKUP), USE A [DEPENDENCY](../dependencies/dependency-injection-basics.md) INSTEAD.

H2: QUERY PARAMETER MODELS

GROUP RELATED QUERY PARAMETERS IN A PYDANTIC MODEL; DECLARE IT WITH `Query()` (`docs_src/query_param_models/tutorial001_an_py310.py`):

```python
from typing import Annotated, Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []


@app.get("/items/")
async def read_items(filter_query: Annotated[FilterParams, Query()]):
    return filter_query
```

EACH FIELD IS A SEPARATE QUERY PARAMETER (`?limit=10&tags=a&tags=b`); VALIDATE VIA THE MODEL AND DOCUMENT INDIVIDUALLY. REUSE THE MODEL ACROSS ENDPOINTS.

forbid UNKNOWN PARAMETERS WITH `model_config = {"extra": "forbid"}` (`tutorial002_an_py310.py`): `?tool=plumbus` THEN RETURNS A 422 `extra_forbidden` ERROR.

H2: RELATED

- [PATH PARAMETERS AND NUMERIC VALIDATION](path-parameters.md)
- [HEADER AND COOKIE PARAMETERS](headers-and-cookies.md)
- [REQUEST BODY](request-body.md)
- [extra DATA TYPES AND examples](extra-data-types-and-examples.md) — `examples` / `openapi_examples` on `Query`
