---
Type: guide
title: USING THE Request OBJECT, STRICT Content-Type AND CUSTOM Request CLASSES
description: ACCESS Starlette's Request directly (client, headers, raw body); strict JSON Content-Type checking and strict_content_type=False; customize handling with custom Request subclasses and APIRoute.get_route_handler (gzip bodies, log validation errors, timing).
tags: [Request, starlette, Content-Type, CSRF, strict_content_type, APIRoute, route_class, gzip]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-6466f5371ff581d059ae3ba8
    resource: repo://docs_src/custom_request_and_route/tutorial001_py310.py
  - id: openwiki-source-6bd74c24f53cf74f8797f45e
    resource: repo://docs_src/custom_request_and_route/tutorial002_py310.py
  - id: openwiki-source-e79f261952e8647156880574
    resource: repo://docs_src/custom_request_and_route/tutorial003_py310.py
  - id: openwiki-source-c2610c12a0bb7697c1366728
    resource: repo://docs_src/strict_content_type/tutorial001_py310.py
  - id: openwiki-source-8782b090f58527cb09067138
    resource: repo://docs_src/using_request_directly/tutorial001_py310.py
  - id: openwiki-source-dca17208de257c294db55bc3
    resource: repo://docs/en/docs/advanced/strict-Content-type.md
  - id: openwiki-source-1c4300918a70439b89cefc67
    resource: repo://docs/en/docs/advanced/using-Request-directly.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-4f39b87de176905c9a9e93d3
    resource: repo://fastapi/requests.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: USING THE Request OBJECT, STRICT Content-Type AND CUSTOM Request CLASSES

H2: USING THE `Request` DIRECTLY

NORMALLY, DECLARE REQUIRED DATA (PATH, QUERY, BODY…); FastAPI VALIDATES,
CONVERTS AND DOCUMENTS IT.
SOMETIMES, RAW Request DATA IS NEEDED: CLIENT IP, ALL HEADERS, RAW BODY.
DECLARE PARAMETER TYPED `Request` (`docs_src/using_request_directly/tutorial001_py310.py`):

```python
from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/items/{item_id}")
def read_root(item_id: str, request: Request):
    client_host = request.client.host
    return {"client_host": client_host, "item_id": item_id}
```

- `fastapi.Request` IS Starlette's `Request`; `fastapi/requests.py` ALSO
  RE-EXPORTS `HTTPConnection`, COMMON BASE OF `Request` AND `WebSocket`.
- OTHER PARAMETERS REMAIN VALIDATED AND DOCUMENTED (`item_id` HERE).
- DATA READ DIRECTLY FROM `Request` (e.g. `await request.body()`,
  `await request.json()`, `request.query_params`) IS NOT VALIDATED,
  CONVERTED OR DOCUMENTED.

USEFUL ATTRIBUTES: `request.method`, `request.url`, `request.headers`,
`request.query_params`, `request.path_params`, `request.cookies`,
`request.client` (`host`, `port`), `request.state`, `request.app`,
`request.scope`, AND `await request.body()` / `json()` / `form()` / `stream()`.

`Request` CAN BE INJECTED INTO DEPENDENCIES; ALSO PASSED TO MIDDLEWARE
AND EXCEPTION HANDLERS.

H2: STRICT `Content-Type` CHECKING

SINCE FastAPI **0.132.0**, PARSE JSON BODIES ONLY WHEN Request HAS JSON
`Content-Type` (`application/json` OR `application/*+json`).
WITHOUT `Content-Type`, DO NOT PARSE AS JSON; MODEL BODY FAILS VALIDATION.

H3: WHY: CSRF PROTECTION

BROWSERS ALLOW CROSS-ORIGIN REQUESTS WITHOUT CORS PREFLIGHT WHEN THERE IS
NO `Content-Type` (e.g. `fetch()` WITH A `Blob` BODY) AND NO CREDENTIALS.
CONSIDER UNAUTHENTICATED LOCAL AI AGENT API AT
`http://localhost:8000/v1/agents/multivac`, TRUSTING LOCAL NETWORK.
MALICIOUS WEBSITE COULD POST TO IT FROM USER'S BROWSER.
BROWSER WOULD NOT PREFLIGHT: IT DOES NOT THINK IT IS SENDING JSON.
STRICT CHECKING MAKES SUCH BODIES FAIL.

THIS MATTERS MAINLY FOR APPS ON `localhost` OR INTERNAL NETWORKS WHOSE
ONLY PROTECTION IS "trust the network".
OPEN-INTERNET APPS MUST AUTHENTICATE PRIVILEGED ENDPOINTS ANYWAY;
THEREFORE, ATTACK DOES NOT APPLY THERE.

H3: ALLOWING REQUESTS WITHOUT `Content-Type`

IF CLIENTS OMIT HEADER MUST BE SUPPORTED
(`docs_src/strict_content_type/tutorial001_py310.py`):

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(strict_content_type=False)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items/")
async def create_item(item: Item):
    return item
```

BODIES WITHOUT `Content-Type` ARE THEN PARSED AS JSON (PRE-0.132 BEHAVIOR).
`FastAPI(...)` AND `APIRouter(...)` ACCEPT THE FLAG; EACH `APIRoute`
STORES IT.
NON-JSON `Content-Type` (e.g. `text/plain`) IS NEVER PARSED AS JSON,
REGARDLESS OF FLAG.

H2: CUSTOM `Request` AND `APIRoute` CLASSES
ADVANCED CASES: CHANGE HOW ROUTES TURN REQUESTS INTO RESPONSES; KEEP ALL FASTAPI VALIDATION.
EVERY PATH OPERATION IS AN `APIRoute`; OVERRIDE `get_route_handler()` TO WRAP
THE ORIGINAL HANDLER; SET THE CLASS ON THE APP ROUTER OR AN `APIRouter`.

> USE ONLY FOR THINGS YOU CANNOT DO WITH DEPENDENCIES OR MIDDLEWARE.

H3: DECOMPRESSING GZIP Request BODIES

`docs_src/custom_request_and_route/tutorial001_py310.py`:

```python
import gzip
from collections.abc import Callable

from fastapi import Body, FastAPI, Request, Response
from fastapi.routing import APIRoute


class GzipRequest(Request):
    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = await super().body()
            if "gzip" in self.headers.getlist("Content-Encoding"):
                body = gzip.decompress(body)
            self._body = body
        return self._body


class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = GzipRequest(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler


app = FastAPI()
app.router.route_class = GzipRoute


@app.post("/sum")
async def sum_numbers(numbers: list[int] = Body()):
    return {"sum": sum(numbers)}
```

- BUILD `Request` FROM THE ASGI `scope` DICT AND `receive` CALLABLE; WRAP IT
  IN YOUR SUBCLASS.
- `GzipRequest.body()` DECOMPRESSES ONCE AND CACHES IN `_body`; FASTAPI BODY
  PARSING THEN SEES plain JSON.
- `app.router.route_class = GzipRoute` APPLIES TO ROUTES DECLARED AFTERWARDS.

H3: ACCESSING THE BODY WHEN VALIDATION FAILS

IF AN EXCEPTION OCCURS, THE Request REMAINS AVAILABLE; INCLUDE THE RAW BODY
IN THE ERROR (`tutorial002_py310.py`):

```python
class ValidationErrorLoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                body = await request.body()
                detail = {"errors": exc.errors(), "body": body.decode()}
                raise HTTPException(status_code=422, detail=detail)

        return custom_route_handler
```

SIMPLER ALTERNATIVE FOR MOST APPS: `RequestValidationError` [EXCEPTION
HANDLER](../errors/handling-errors.md) USING `exc.body`.

H3: PER-ROUTER ROUTE CLASSES: TIMING

SET `route_class` ON AN `APIRouter` TO AFFECT ONLY ITS ROUTES
(`tutorial003_py310.py`):

```python
class TimedRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            before = time.time()
            response: Response = await original_route_handler(request)
            duration = time.time() - before
            response.headers["X-Response-Time"] = str(duration)
            return response

        return custom_route_handler


app = FastAPI()
router = APIRouter(route_class=TimedRoute)


@app.get("/")
async def not_timed():
    return {"message": "Not timed"}


@router.get("/timed")
async def timed():
    return {"message": "It's the time of my life"}


app.include_router(router)
```

ONLY `/timed` GETS THE `X-Response-Time` HEADER. UNLIKE MIDDLEWARE, THIS RUNS
INSIDE THE ROUTE, AFTER ROUTING, WITH ACCESS TO FASTAPI'S HANDLER.

H2: RELATED

- [HOW FASTAPI HANDLES A Request](../internals/Request-handling-internals.md)
- [MIDDLEWARE](../middleware/middleware.md)
- [CORS](../middleware/cors.md)
