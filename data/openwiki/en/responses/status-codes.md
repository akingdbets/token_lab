---
type: guide
title: Response Status Codes
description: Set the default status code with status_code and fastapi.status constants, understand status ranges and body-less codes, return additional status codes with a JSONResponse, and change the status per request through an injected Response parameter.
tags:
  - status-code
  - http-status
  - fastapi-status
  - jsonresponse
  - response-parameter
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

# Response Status Codes

## Declaring the status code

Pass `status_code` to the path operation decorator (`docs_src/response_status_code/tutorial001_py310.py`):

```python
from fastapi import FastAPI

app = FastAPI()


@app.post("/items/", status_code=201)
async def create_item(name: str):
    return {"name": name}
```

- `status_code` is a parameter of the **decorator** (`@app.get()`, `@app.post()`, …), not of your function.
- It sets the response status **and** documents it in OpenAPI.
- It accepts an `int` or an `IntEnum` such as Python's `http.HTTPStatus` (normalized to `int`).

Use the named constants in `fastapi.status` (re-exported from Starlette) for readability and autocompletion (`tutorial002_py310.py`):

```python
from fastapi import FastAPI, status

app = FastAPI()


@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(name: str):
    return {"name": name}
```

## Status code ranges

| Range | Meaning | Notes |
|-------|---------|-------|
| `100–199` | Informational | Can't have a body; rarely used directly |
| `200–299` | Success | `200` OK (default), `201` Created, `204` No Content (no body) |
| `300–399` | Redirection | `304` Not Modified must not have a body |
| `400–499` | Client error | `404` Not Found, `400` generic client error, `422` validation error |
| `500–599` | Server error | Produced automatically for unhandled errors |

FastAPI knows which codes forbid a body (`is_body_allowed_for_status_code`: below 200, `204`, `205`, `304`). For those it documents no response body and sends an empty body even if your function returned something.

To return errors, **raise** `HTTPException` instead of choosing an error status here — see [Handling Errors](../errors/handling-errors.md).

## Additional status codes

`status_code` declares the *main* status. To sometimes return a different one, return a `Response` (e.g. `JSONResponse`) directly with that status (`docs_src/additional_status_codes/tutorial001_an_py310.py`):

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

Existing items → `200` with the item; new items → `201`. Caveats:

- A directly returned response isn't validated or filtered by any response model — serialize the content yourself (here it's already a plain dict).
- OpenAPI doesn't know about the extra status. Document it with `responses={201: {...}}` ([Extending OpenAPI](../openapi/extending-openapi.md)).

## Changing the status code per request

To keep using your response model *and* change the status dynamically, declare a `Response` parameter and set `response.status_code` (`docs_src/response_change_status_code/tutorial001_py310.py`):

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

FastAPI injects a temporary `Response`; if you set `status_code` on it, that value overrides the decorator's `status_code` for this response (`_build_response_args` in `fastapi/routing.py`). Your return value is still serialized through the response model. You can set the status the same way inside dependencies. The same object lets you set [headers and cookies](response-headers-and-cookies.md).

## Related

- [Custom Responses](custom-responses.md)
- [Path Operation Configuration](../app-structure/path-operation-configuration.md)
