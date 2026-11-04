---
type: guide
title: Response STATUS CODES
description: SET DEFAULT STATUS CODE WITH status_code AND fastapi.status CONSTANTS; UNDERSTAND STATUS RANGES AND BODY-LESS CODES; RETURN ADDITIONAL STATUS CODES WITH A JSONResponse; CHANGE STATUS PER REQUEST VIA AN INJECTED Response PARAMETER.
tags:
  - status-code
  - http-status
  - fastapi-status
  - JSONResponse
  - Response-parameter
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-64f65a49d9b0624f36e8c4da
    resource: repo://docs_src/additional_status_codes/tutorial001_an_py310.py
  - id: openwiki-source-f95dc6f662f6c7f6ffe6230f
    resource: repo://docs_src/response_change_status_code/tutorial001_py310.py
  - id: openwiki-source-96588f86415f73ebac05921c
    resource: repo://docs_src/response_status_code/tutorial001_py310.py
  - id: openwiki-source-253ff8d6337ec5a30ecba880
    resource: repo://docs_src/response_status_code/tutorial002_py310.py
  - id: openwiki-source-0266708b69f2d248a7bf8dd4
    resource: repo://docs/en/docs/advanced/additional-status-codes.md
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: Response STATUS CODES

H2: DECLARING THE STATUS CODE

PASS `status_code` TO THE PATH OPERATION DECORATOR (`docs_src/response_status_code/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()


@app.post("/items/", status_code=201)
async def create_item(name: str):
    return {"name": name}
```

- `status_code` IS A DECORATOR PARAMETER (`@app.get()`, `@app.post()`, …),
  NOT A FUNCTION PARAMETER.
- SETS Response STATUS AND DOCUMENTS IT IN OpenAPI.
- ACCEPTS `int` OR `IntEnum`, e.g. PYTHON'S `http.HTTPStatus`
  (NORMALIZED TO `int`).

USE NAMED CONSTANTS IN `fastapi.status` (RE-EXPORTED FROM Starlette)
FOR READABILITY AND AUTOCOMPLETION (`tutorial002_py310.py`):

```python
from fastapi import FastAPI, status

app = FastAPI()


@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(name: str):
    return {"name": name}
```

H2: STATUS CODE RANGES

| RANGE | MEANING | NOTES |
|-------|---------|-------|
| `100–199` | INFORMATIONAL | NO BODY; RARELY USED DIRECTLY |
| `200–299` | SUCCESS | `200` OK (DEFAULT), `201` CREATED, `204` NO CONTENT (NO BODY) |
| `300–399` | REDIRECTION | `304` NOT MODIFIED MUST NOT HAVE A BODY |
| `400–499` | CLIENT ERROR | `404` NOT FOUND, `400` GENERIC CLIENT ERROR, `422` VALIDATION ERROR |
| `500–599` | SERVER ERROR | AUTO-PRODUCED FOR UNHANDLED ERRORS |

FastAPI KNOWS WHICH CODES FORBID A BODY
(`is_body_allowed_for_status_code`: BELOW 200, `204`, `205`, `304`).
FOR THESE CODES, IT DOCUMENTS NO Response BODY AND SENDS AN EMPTY BODY,
EVEN IF YOUR FUNCTION RETURNS SOMETHING.

TO RETURN ERRORS, **RAISE** `HTTPException` INSTEAD OF CHOOSING AN ERROR
STATUS HERE — SEE [HANDLING ERRORS](../errors/handling-errors.md).

H2: ADDITIONAL STATUS CODES

`status_code` DECLARES THE *MAIN* STATUS. TO SOMETIMES RETURN A DIFFERENT
STATUS, RETURN A `Response` (e.g. `JSONResponse`) DIRECTLY WITH THAT STATUS
(`docs_src/additional_status_codes/tutorial001_an_py310.py`):

```python
from typing import Annotated

from fastapi import Body, FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()

items = {"foo": {"name": "Fighters", "size": 6}, "bar": {"name": "Tenders", "size": 3}}


@app.put("/items/{item_id}")
async def upsert_item(
    item_id: str,
    name: Annotated[str | None, Body()] = None,
    size: Annotated[int | None, Body()] = None,
):
    if item_id in items:
        item = items[item_id]
        item["name"] = name
        item["size"] = size
        return item
    else:
        item = {"name": name, "size": size}
        items[item_id] = item
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=item)
```

EXISTING ITEMS RETURN `200` WITH THE ITEM; NEW ITEMS RETURN `201`.
CAVEATS:

- A DIRECTLY RETURNED Response ISN'T VALIDATED OR FILTERED BY ANY Response
  MODEL. SERIALIZE THE CONTENT YOURSELF (HERE, IT'S ALREADY A PLAIN DICT).
- OpenAPI DOESN'T KNOW ABOUT THE EXTRA STATUS. DOCUMENT IT WITH
  `responses={201: {...}}` ([EXTENDING OpenAPI](../OpenAPI/extending-openapi.md)).

H2: CHANGING THE STATUS CODE PER REQUEST

TO KEEP USING YOUR Response MODEL AND CHANGE THE STATUS DYNAMICALLY,
DECLARE A `Response` PARAMETER AND SET `response.status_code`
(`docs_src/response_change_status_code/tutorial001_py310.py`):

```python
from fastapi import FastAPI, Response, status

app = FastAPI()

tasks = {"foo": "Listen to the Bar Fighters"}


@app.put("/get-or-create-task/{task_id}", status_code=200)
def get_or_create_task(task_id: str, response: Response):
    if task_id not in tasks:
        tasks[task_id] = "This didn't exist before"
        response.status_code = status.HTTP_201_CREATED
    return tasks[task_id]
```

FastAPI INJECTS A TEMPORARY `Response`. IF YOU SET `status_code` ON IT,
THAT VALUE OVERRIDES THE DECORATOR'S `status_code` FOR THIS Response
(`_build_response_args` IN `fastapi/routing.py`).
YOUR RETURN VALUE IS STILL SERIALIZED THROUGH THE Response MODEL.
YOU CAN SET THE STATUS THE SAME WAY INSIDE DEPENDENCIES.
THE SAME OBJECT LETS YOU SET [HEADERS AND COOKIES](Response-headers-and-cookies.md).

H2: RELATED

- [CUSTOM responses](custom-responses.md)
- [PATH OPERATION CONFIGURATION](../app-structure/path-operation-configuration.md)
