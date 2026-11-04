---
type: guide
title: Path parameters and Numeric Validation
description: Declare path parameters with Python types for conversion and validation, order fixed routes before parameterized ones, restrict values with Enum, capture paths with :path, and add Path() metadata and numeric constraints (gt, ge, lt, le).
tags: [path-parameters, path, validation, Enum, numeric-validation, routing]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-9718dff1ebb27c0b1bf1abf9
    resource: repo://docs_src/path_params_numeric_validations/tutorial004_an_py310.py
  - id: openwiki-source-d5ea2075b94825343c04edc8
    resource: repo://docs_src/path_params_numeric_validations/tutorial005_an_py310.py
  - id: openwiki-source-0fd032858ed69844c1398749
    resource: repo://docs_src/path_params_numeric_validations/tutorial006_an_py310.py
  - id: openwiki-source-38df07681a8fcbdb034904e9
    resource: repo://docs_src/path_params/tutorial002_py310.py
  - id: openwiki-source-3b9406805096315081c49590
    resource: repo://docs_src/path_params/tutorial003_py310.py
  - id: openwiki-source-cd9fb2b4addace155974917d
    resource: repo://docs_src/path_params/tutorial003b_py310.py
  - id: openwiki-source-84c4dbdfc11b1dfd298b8383
    resource: repo://docs_src/path_params/tutorial004_py310.py
  - id: openwiki-source-e891265db7ef0a76fe70d4f4
    resource: repo://docs_src/path_params/tutorial005_py310.py
  - id: openwiki-source-6a09064320fc387f97ffc738
    resource: repo://docs/en/docs/tutorial/path-params.md
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-4ba318fa02e49c0255b400c4
    resource: repo://fastapi/param_functions.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Path parameters and Numeric Validation

H2: Declaring path parameters

USE PYTHON FORMAT-STRING SYNTAX IN PATH; value PASSES TO FUNCTION ARGUMENT
WITH SAME NAME (`docs_src/path_params/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}
```

`GET /items/foo` → `{"item_id": "foo"}`.

H2: Types: conversion and validation

ADD TYPE ANNOTATION (`tutorial002_py310.py`):

```python
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

- `GET /items/3` → `{"item_id": 3}`; STRING `"3"` CONVERTS TO `int` `3`.
- `GET /items/foo` (OR `/items/4.2`) → **422** ERROR; TYPE `int_parsing`,
  `loc` `["path", "item_id"]`, READABLE MESSAGE.
- TYPE DOCUMENTED IN OpenAPI AND DOCS UI.

PYDANTIC DOES THIS; ANY PYDANTIC TYPE WORKS (`str`, `float`, `bool`, `UUID`, …).

H2: Route order matters

PATH OPERATIONS MATCH IN DECLARATION ORDER. PUT FIXED PATHS BEFORE
PARAMETERIZED ONES (`tutorial003_py310.py`):

```python
@app.get("/users/me")
async def read_user_me():
    return {"user_id": "the current user"}


@app.get("/users/{user_id}")
async def read_user(user_id: str):
    return {"user_id": user_id}
```

OTHERWISE `/users/me` MATCHES `/users/{user_id}` WITH `user_id="me"`.
REDEFINE SAME PATH AND METHOD (`tutorial003b_py310.py`) → ONLY FIRST
DEFINITION USED.

H2: Predefined values with `Enum`

SUBCLASS BOTH `str` AND `Enum` TO RESTRICT PATH PARAMETER TO KNOWN VALUES
(`tutorial005_py310.py`):

```python
from enum import Enum

from fastapi import FastAPI


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


app = FastAPI()


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}

    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}

    return {"model_name": model_name, "message": "Have some residuals"}
```

- INHERITING FROM `str` MAKES DOCS SHOW VALUES AS STRINGS.
- DOCS UI SHOWS DROPDOWN OF ALLOWED VALUES; OTHER VALUES GET 422.
- COMPARE WITH Enum MEMBERS (`is ModelName.alexnet`) OR USE `.value`;
  RETURNED Enum MEMBER SERIALIZES TO ITS value.

H2: Paths inside path parameters

CAPTURE VALUES CONTAINING SLASHES (e.g. FILE PATH) WITH STARLETTE'S `:path`
CONVERTER (`tutorial004_py310.py`):

```python
@app.get("/files/{file_path:path}")
async def read_file(file_path: str):
    return {"file_path": file_path}
```

`/files/home/johndoe/myfile.txt` → `file_path="home/johndoe/myfile.txt"`.
FOR value STARTING WITH `/`, URL HAS DOUBLE SLASH:
`/files//home/johndoe/myfile.txt`. OpenAPI HAS NO NOTION OF
PATH-CONTAINING parameters; DOCS WON'T HINT AT THIS, BUT IT WORKS.

H2: `Path()`: metadata and numeric validation

USE `Path` WITH `Annotated` TO ADD METADATA AND CONSTRAINTS
(`docs_src/path_params_numeric_validations/tutorial001_an_py310.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI()


@app.get("/items/{item_id}")
async def read_items(
    item_id: Annotated[int, Path(title="The ID of the item to get")],
    q: Annotated[str | None, Query(alias="item-query")] = None,
):
    results = {"item_id": item_id}
    if q:
        results.update({"q": q})
    return results
```

**PATH PARAMETER ALWAYS REQUIRED**: IT'S PART OF PATH. `Path` ASSERTS NO
default (`"Path parameters cannot have a default value"`); FASTAPI ALSO
REFUSES A default FOR A PATH PARAMETER.

H3: Numeric constraints

| Parameter | Meaning |
|-----------|---------|
| `gt` | greater than |
| `ge` | greater than or equal |
| `lt` | less than |
| `le` | less than or equal |

```python
# ge=1 (tutorial004)
item_id: Annotated[int, Path(title="The ID of the item to get", ge=1)]

# gt=0, le=1000 (tutorial005)
item_id: Annotated[int, Path(title="The ID of the item to get", gt=0, le=1000)]
```

CONSTRAINTS ALSO WORK FOR `float` (`tutorial006_an_py310.py`):

```python
@app.get("/items/{item_id}")
async def read_items(
    *,
    item_id: Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)],
    q: str,
    size: Annotated[float, Query(gt=0, lt=10.5)],
):
    ...
```
SAME CONSTRAINTS APPLY TO `Query`, `Header`, `Cookie`, `Body` AND PYDANTIC'S `Field`.
OTHER `Path` parameters: `title`, `description`, `examples`,
`openapi_examples`, `deprecated`, `include_in_schema`; STRING CONSTRAINTS:
`min_length`, `max_length`, `pattern`.

H3: PARAMETER ORDERING

FASTAPI IDENTIFIES parameters BY **NAME, TYPE AND default**, NOT POSITION;
ORDER THEM ARBITRARILY.
WITH `Annotated`, REQUIRED parameters WITHOUT DEFAULTS MAY FOLLOW ONES WITH
DEFAULTS; PYTHON is UNAFFECTED.
OLDER default-value STYLE (`item_id: int = Path(...)`): PYTHON FORBIDS
NON-default ARGUMENTS AFTER default ONES.
DOCS' WORKAROUND: START SIGNATURE WITH `*`; ALL parameters BECOME KEYWORD-ONLY
(SEE `tutorial006`).
`Annotated` AVOIDS THIS ISSUE ENTIRELY.
`Path`, `Query` AND FRIENDS IMPORTED FROM `fastapi` ARE FUNCTIONS RETURNING
INSTANCES OF CLASSES IN `fastapi.params` (`fastapi/param_functions.py`);
THEY ARE TYPED SO EDITORS DON'T COMPLAIN.

H2: RELATED
- [Query parameters, STRING VALIDATION AND Query MODELS](Query-parameters.md)
- [REQUEST Body](request-body.md)
- [BIGGER APPLICATIONS](../app-structure/bigger-applications.md) —
  ROUTE ORDERING ACROSS ROUTERS
