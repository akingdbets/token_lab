---
type: guide
title: Response Models and Return Types
description: Declare the Response shape with a return type annotation or response_model to validate, filter, document and serialize output; priority rules, returning Response objects, response_model=None, and the response_model_exclude_unset / include / exclude options.
tags: [Response-model, return-type, pydantic, filtering, serialization, response_model_exclude_unset, OpenAPI]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-9a62f7950d7a9b9ac95d2fa4
    resource: repo://docs_src/response_model/tutorial003_01_py310.py
  - id: openwiki-source-41ea77b7453e52dc9a990df8
    resource: repo://docs_src/response_model/tutorial003_05_py310.py
  - id: openwiki-source-bd6ac53b99ab082ca19d305a
    resource: repo://docs_src/response_model/tutorial003_py310.py
  - id: openwiki-source-f40a322e7e096e6207d3367b
    resource: repo://docs_src/response_model/tutorial004_py310.py
  - id: openwiki-source-246dc932abfd82985b764c70
    resource: repo://docs_src/response_model/tutorial005_py310.py
  - id: openwiki-source-1815f7028972fe19690e83a7
    resource: repo://docs/en/docs/tutorial/Response-model.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://FastAPI/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Response MODELS AND RETURN TYPES

PATH OPERATION Response TYPE MAKES FastAPI:
- VALIDATE RETURNED DATA; INVALID DATA (e.g. MISSING FIELD) IS AN APP BUG;
  FastAPI RESPONDS WITH SERVER ERROR, NOT WRONG DATA.
- FILTER OUTPUT TO DECLARED FIELDS; IMPORTANT FOR SECURITY,
  e.g. HIDING PASSWORDS.
- DOCUMENT Response WITH JSON Schema IN OpenAPI;
  THEREFORE ALSO DOCUMENTS GENERATED CLIENTS.
- SERIALIZE EFFICIENTLY: Response TYPE + DEFAULT Response CLASS LET Pydantic
  SERIALIZE DIRECTLY TO JSON BYTES. SEE [INTERNALS](../internals/request-handling-internals.md).

H2: RETURN TYPE ANNOTATIONS

`docs_src/response_model/tutorial001_01_py310.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: list[str] = []


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item


@app.get("/items/")
async def read_items() -> list[Item]:
    return [
        Item(name="Portal Gun", price=42.0),
        Item(name="Plumbus", price=32.0),
    ]
```

ANY TYPE VALID FOR Pydantic FIELDS WORKS: MODELS, `list[...]`, `dict[...]`,
SCALARS, UNIONS.

H2: THE `response_model` PARAMETER

RETURNING A VALUE THAT ISN'T LITERALLY THE DECLARED TYPE—e.g. A dict
OR DATABASE OBJECT—CAN UPSET YOUR EDITOR/TYPE CHECKER.
USE DECORATOR PARAMETER `response_model` INSTEAD (`tutorial001_py310.py`):

```python
from typing import Any


@app.post("/items/", response_model=Item)
async def create_item(item: Item) -> Any:
    return item


@app.get("/items/", response_model=list[Item])
async def read_items() -> Any:
    return [
        {"name": "Portal Gun", "price": 42.0},
        {"name": "Plumbus", "price": 32.0},
    ]
```

`response_model` IS A DECORATOR PARAMETER (`@app.get()`, `@app.post()`, …),
NOT A FUNCTION PARAMETER.

PRIORITY: IF BOTH EXIST, `response_model` WINS.
FastAPI DERIVES THE Response MODEL FROM THE RETURN ANNOTATION ONLY
WHEN `response_model` ISN'T PASSED AT ALL.

H2: FILTERING OUTPUT

NEVER ECHO SENSITIVE INPUT (`tutorial002_py310.py` RETURNS `UserIn`
WITH THE password: "Don't do this in production!").
DECLARE AN OUTPUT MODEL (`tutorial003_py310.py`):

```python
class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


@app.post("/user/", response_model=UserOut)
async def create_user(user: UserIn) -> Any:
    return user
```

RETURNED `UserIn` CONVERTS TO `UserOut`; `password` IS DROPPED.

H3: FILTERING WITH INHERITANCE AND A RETURN TYPE

PRECISE RETURN ANNOTATION + FILTERING: MAKE INPUT MODEL A SUBCLASS
OF OUTPUT MODEL (`tutorial003_01_py310.py`):

```python
class BaseUser(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserIn(BaseUser):
    password: str


@app.post("/user/")
async def create_user(user: UserIn) -> BaseUser:
    return user
```

TYPE CHECKERS ACCEPT THIS (`UserIn` *IS A* `BaseUser`);
FastAPI STILL SERIALIZES ONLY `BaseUser` FIELDS.
MORE PATTERNS: [EXTRA MODELS](extra-models-and-updates.md).

H2: RETURNING `Response` OBJECTS

RETURN ANNOTATION `Response` OR SUBCLASS:
FastAPI DOES NOT CREATE A Response MODEL
(`lenient_issubclass(return_annotation, Response)` → `response_model = None`):

```python
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse


@app.get("/portal")
async def get_portal(teleport: bool = False) -> Response:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return JSONResponse(content={"message": "Here's your interdimensional portal."})


@app.get("/teleport")
async def get_teleport() -> RedirectResponse:
    return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

RETURNED `Response` INSTANCE IS SENT AS-IS; NO VALIDATION OR FILTERING.
SEE [CUSTOM RESPONSES](../responses/custom-responses.md).

H3: INVALID ANNOTATIONS AND `response_model=None`

ANNOTATION NEITHER VALID Pydantic TYPE NOR PLAIN `Response` CLASS
(e.g. `Response | dict` (`tutorial003_04_py310.py`) OR AN ORM CLASS)
MAKES FastAPI FAIL WHEN CREATING THE ROUTE:
IT TRIES TO BUILD A Pydantic MODEL FROM THE ANNOTATION.
KEEP THE ANNOTATION FOR YOUR TOOLS; DISABLE THE Response MODEL
(`tutorial003_05_py310.py`):

```python
@app.get("/portal", response_model=None)
async def get_portal(teleport: bool = False) -> Response | dict:
    if teleport:
        return RedirectResponse(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    return {"message": "Here's your interdimensional portal."}
```

WITHOUT A Response MODEL, RETURN VALUES CONVERT WITH `jsonable_encoder`.
GENERATOR ENDPOINTS ARE SPECIAL: FOR STREAMING (JSON LINES / SSE), ANNOTATIONS
LIKE `AsyncIterable[Item]` DETERMINE THE **Item** TYPE; SEE
[STREAMING](../responses/streaming-and-sse.md).

H2: Response MODEL ENCODING OPTIONS

`tutorial004_py310.py`:

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float = 10.5
    tags: list[str] = []


@app.get("/items/{item_id}", response_model=Item, response_model_exclude_unset=True)
async def read_item(item_id: str):
    return items[item_id]
```

`response_model_exclude_unset=True` OMITS FIELDS NOT EXPLICITLY SET FROM JSON.
FOR `"foo": {"name": "Foo", "price": 50.2}`, Response IS
`{"name": "Foo", "price": 50.2}`: NO DEFAULT `description`, `tax` OR `tags`.
EXPLICITLY SET VALUES ARE INCLUDED EVEN IF EQUAL TO THE DEFAULT, SUCH AS
`baz`'S `"tax": 10.5`.

RELATED OPTIONS ARE ALL DECORATOR PARAMETERS, APPLIED VIA PYDANTIC
SERIALIZATION:

`response_model_exclude_unset`: OMIT FIELDS NOT EXPLICITLY SET.
`response_model_exclude_defaults`: OMIT FIELDS EQUAL TO THEIR DEFAULT.
`response_model_exclude_none`: OMIT FIELDS WHOSE VALUE IS `None`.
`response_model_include`: INCLUDE ONLY THESE FIELDS (SET OF NAMES).
`response_model_exclude`: DROP THESE FIELDS.
`response_model_by_alias`: USE FIELD ALIASES IN OUTPUT (DEFAULT `True`).

`response_model_include` / `response_model_exclude`
(`tutorial005_py310.py`):

```python
@app.get(
    "/items/{item_id}/name",
    response_model=Item,
    response_model_include={"name", "description"},
)
async def read_item_name(item_id: str):
    return items[item_id]


@app.get("/items/{item_id}/public", response_model=Item, response_model_exclude={"tax"})
async def read_item_public_data(item_id: str):
    return items[item_id]
```

LISTS OR TUPLES ARE ALSO ACCEPTED AND CONVERTED TO SETS
(`tutorial006_py310.py`). PREFER SEPARATE MODELS OVER INCLUDE/EXCLUDE:
WITH INCLUDE/EXCLUDE, THE OpenAPI SCHEMA STILL SHOWS THE **FULL** MODEL;
SEPARATE CLASSES DOCUMENT EXACTLY WHAT IS RETURNED.

H2: RELATED

- [Response STATUS CODES](../responses/status-codes.md)
- [DATACLASSES AND PYDANTIC VERSIONS](dataclasses-and-pydantic-versions.md):
  SEPARATE INPUT/OUTPUT SCHEMAS
- [HANDLING ERRORS](../errors/handling-errors.md): `ResponseValidationError`
