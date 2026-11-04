---
Type: architecture
title: How FastAPI Handles a Request (Internals for Users)
description: USER-RELEVANT FASTAPI Request INTERNALS: MIDDLEWARE STACK, Route MATCHING, body parsing AND Content-Type CHECKS, DEPENDENCY RESOLUTION WITH CACHING AND OVERRIDES, THREADPOOL VS EVENT-LOOP EXECUTION, RESPONSE VALIDATION AND SERIALIZATION, STREAMING PATHS, AND EXIT STACKS FOR yield dependencies.
tags: [internals, Request-lifecycle, middleware-stack, dependencies, serialization, response_model, exit-stack]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - ID: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - ID: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - ID: openwiki-source-338938fe8c8c2e10895f46fa
    resource: repo://fastapi/middleware/asyncexitstack.py
  - ID: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: HOW FASTAPI HANDLES A Request (INTERNALS FOR USERS)

FASTAPI USE DOESN'T REQUIRE THIS PAGE; IT EXPLAINS WHY BEHAVIOR OCCURS:
error CODES, MIDDLEWARE/HANDLER ORDER, DEPENDENCY-CLOSING TIME,
AND PERFORMANCE FACTORS.
SOURCES: `fastapi/applications.py`, `fastapi/routing.py`,
`fastapi/dependencies/utils.py`.

H2: 1. AT STARTUP: BUILDING ROUTES

EACH PATH OPERATION DECORATOR CREATES `APIRoute`, A STARLETTE `Route` SUBCLASS.
WHEN BUILT, FASTAPI:

- INSPECTS ENDPOINT SIGNATURE (`get_dependant`) AND CLASSIFIES EACH PARAMETER:
  PATH, QUERY, HEADER, COOKIE, body, FORM/FILE, DEPENDENCY
  (`Depends`/`Security`), OR SPECIAL OBJECT (`Request`, `WebSocket`,
  `Response`, `BackgroundTasks`, `SecurityScopes`).
  RESULT: TREE OF `Dependant` OBJECTS (`fastapi/dependencies/models.py`).
- DETERMINES RESPONSE FIELD FROM `response_model` OR RETURN ANNOTATION.
- FILLS METADATA, INCLUDING `description` FROM DOCSTRING AND `unique_id`
  (OPERATION ID).
- CHECKS CONFIGURATION ERRORS EARLY, e.g. `DependencyScopeError` FOR INVALID
  `yield` scope COMBINATIONS, OR body-FORBIDDING STATUS CODE COMBINED WITH
  RESPONSE MODEL.

OpenAPI SCHEMA IS GENERATED FROM ROUTES ON DEMAND AND CACHED (`app.openapi()`).

H2: 2. the MIDDLEWARE STACK

`FastAPI.build_middleware_stack()` WRAPS the ROUTER AS FOLLOWS
(OUTERMOST FIRST):

```
ServerErrorMiddleware        ← unhandled exceptions → 500 (your handler for 500/Exception goes here)
ExceptionTelemetryMiddleware ← OpenTelemetry exception recording
<your middleware>            ← add_middleware / @app.middleware("http"), last added = outermost
ExceptionMiddleware          ← your exception handlers (HTTPException, RequestValidationError, custom…)
AsyncExitStackMiddleware     ← closes uploaded files after the request
Router                       ← route matching → APIRoute
```

CONSEQUENCES:

- Exception HANDLERS RUN INSIDE YOUR MIDDLEWARE; MIDDLEWARE SEES the HANDLER
  RESPONSE (e.g. 422 OR 404).
- UNHANDLED EXCEPTIONS REACH `ServerErrorMiddleware` → 500.
  (`debug=True` SHOWS TRACEBACKS.)
- HANDLER REGISTERED FOR `500` OR `Exception` BECOMES the
  `ServerErrorMiddleware` HANDLER.

SEE [MIDDLEWARE](../middleware/middleware.md) AND
[HANDLING ERRORS](../errors/handling-errors.md).

H2: 3. MATCHING the Route

ROUTER MATCHES PATH AND METHOD.
PATH OPERATIONS TAKE PRIORITY OVER FRONTEND ROUTES (`app.frontend()`).
INCLUDED-ROUTER ROUTES RESOLVE "live" THROUGH `_IncludedRouter` ENTRIES;
SEE [BIGGER APPLICATIONS](../app-structure/bigger-applications.md).
NO MATCH → 404; PATH MATCHES, METHOD DOESN'T → 405.

H2: 4. PER-Request EXIT STACKS

`request_response()` OPENS TWO `AsyncExitStack`s AROUND the CALL:

- Request STACK (`fastapi_inner_astack`): CLOSES AFTER RESPONSE IS SENT.
- function STACK (`fastapi_function_astack`): CLOSES AFTER ENDPOINT RETURNS,
  BEFORE RESPONSE SENDING.

`yield` dependencies ENTER ONE STACK, DEPENDING ON `Depends(scope=...)`.
IF RESPONSE IS NEVER SENT BECAUSE an Exception IS SWALLOWED IN A `yield`
DEPENDENCY'S `except`, FASTAPI RAISES `FastAPIError` EXPLAINING THIS LIKELY
CAUSE.
SEE [dependencies WITH yield](../dependencies/dependencies-with-yield.md).

H2: 5. READING the body

body IS READ ONLY IF ENDPOINT HAS body PARAMETERS:
- FORM/FILE PARAMETERS → `await request.form()`; `AsyncExitStackMiddleware` closes the form and its files at the end.
- OTHERWISE, RAW body IS READ; PARSED AS JSON ONLY WHEN `Content-Type` IS `application/json` OR `application/*+json`.
- WITH NO `Content-Type`, JSON IS PARSED ONLY IF `strict_content_type=False`.
- ANY OTHER Content Type LEAVES RAW BYTES; THESE FAIL VALIDATION FOR MODEL BODIES. SEE [USING the Request OBJECT, STRICT Content-Type](../Request/using-Request-directly.md).
- INVALID JSON → `RequestValidationError` WITH Type `json_invalid` (→ 422). OTHER parsing FAILURES → `HTTPException(400, "There was an error parsing the body")`.

H2: 6. SOLVING dependencies AND VALIDATING PARAMETERS

`solve_dependencies()` WALKS the `Dependant` TREE DEPTH-FIRST:
- APPLIES `app.dependency_overrides` (REPLACES A DEPENDENCY callable WITH ITS OVERRIDE).
- FOR EACH SUB-DEPENDENCY: RETURNS A CACHED VALUE IF the SAME `(callable, security scopes, scope)` was ALREADY SOLVED IN THIS Request AND `use_cache=True`; OTHERWISE, CALLS IT — GENERATORS VIA EXIT STACKS, `async def` AWAITED, PLAIN `def` RUN IN the THREADPOOL.
- EXTRACTS PATH/QUERY/HEADER/COOKIE VALUES AND body; VALIDATES THEM WITH PYDANTIC. COLLECTS ALL ERRORS; IF ANY, RAISES A SINGLE `RequestValidationError` (→ 422 WITH ALL ERRORS) AFTER RESOLUTION.
- INJECTS SPECIAL OBJECTS: the `Request`, A TEMPORARY `Response` (FOR HEADERS/COOKIES/STATUS YOU SET), the SHARED `BackgroundTasks`, `SecurityScopes`.

H2: 7. RUNNING the ENDPOINT

`run_endpoint_function()` AWAITS `async def` ENDPOINTS DIRECTLY ON the EVENT LOOP; RUNS PLAIN `def` ENDPOINTS WITH `run_in_threadpool`. SEE [PYTHON TYPES AND async/await](../getting-started/python-types-and-async.md).

GENERATOR ENDPOINTS USE STREAMING PATHS INSTEAD:
- `response_class=EventSourceResponse` → SERVER-SENT EVENTS.
- GENERATOR WITH JSON LINES SEMANTICS → `StreamingResponse` WITH `media_type="application/jsonl"`; EACH ITEM VALIDATED/SERIALIZED INDIVIDUALLY.
- GENERATOR WITH EXPLICIT `response_class` (e.g. `StreamingResponse`) → CHUNKS PASSED THROUGH.

SEE [STREAMING DATA, JSON LINES AND SERVER-SENT EVENTS](../responses/streaming-and-sse.md).

H2: 8. BUILDING the RESPONSE

- IF ENDPOINT RETURNS A `Response` INSTANCE, USE IT AS IS (NO VALIDATION OR SERIALIZATION); ATTACH COLLECTED BACKGROUND TASKS IF RESPONSE HAS NONE.
- OTHERWISE, `serialize_response()`:
  - WITH A RESPONSE FIELD (FROM `response_model` OR RETURN Type), VALIDATE VALUE AGAINST IT (FAILURE RAISES `ResponseValidationError` → 500); SERIALIZE WITH PYDANTIC, HONORING `response_model_include/exclude/by_alias/exclude_unset/exclude_defaults/exclude_none`.
  - WITHOUT A RESPONSE FIELD, CONVERT VALUE WITH `jsonable_encoder`.
  - FAST PATH: WITH A RESPONSE FIELD AND the DEFAULT RESPONSE CLASS, PYDANTIC SERIALIZES DIRECTLY TO JSON BYTES (SKIPS INTERMEDIATE DICT + `json.dumps`); FASTAPI RETURNS `Response(media_type="application/json")`. DECLARE RESPONSE MODELS/RETURN TYPES FOR THIS REASON: FASTER, NOT JUST SAFER.
  - OTHERWISE, PASS Content TO Route'S `response_class` (DEFAULT `JSONResponse`).
- STATUS CODE: DECORATOR'S `status_code`, OR ONE SET ON INJECTED `Response` PARAMETER. FOR STATUSES THAT FORBID A body (e.g. 204, 304), EMPTY the body.
- COPY HEADERS AND COOKIES SET ON INJECTED `Response` ONTO FINAL RESPONSE.

SEE [RESPONSE MODELS](../models/response-model.md) AND [CUSTOM RESPONSES](../responses/custom-responses.md).

H2: 9. AFTER the RESPONSE

IN `request_response()` the ORDER IS:
1. function STACK CLOSES WHEN ENDPOINT AND RESPONSE-BUILDING FINISH; TEARDOWN OF `scope="function"` `yield` dependencies.
2. `await response(scope, receive, send)` SENDS RESPONSE; STARLETTE RUNS RESPONSE'S BACKGROUND TASKS AS PART OF THIS CALL, AFTER body IS SENT.
3. Request STACK CLOSES; TEARDOWN OF Request-SCOPED (DEFAULT) `yield` dependencies.
4. FURTHER OUT, `AsyncExitStackMiddleware` CLOSES UPLOADED FILES.

STILL, DON'T RELY ON OBJECTS FROM `yield` dependencies IN BACKGROUND TASKS; CREATE THEIR OWN RESOURCES (SEE [BACKGROUND TASKS](../integrations/background-tasks.md)).

H2: RELATED

- [DEPENDENCY INJECTION BASICS](../dependencies/dependency-injection-basics.md)
- [ADVANCED dependencies](../dependencies/advanced-dependencies.md)
