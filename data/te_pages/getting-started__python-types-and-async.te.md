---
type: concept
title: Python Types and async/await
description: The Python type hints FastAPI relies on (str | None, list/dict generics, classes, Pydantic models, Annotated) and when to declare path operations and dependencies with async def versus def, including how def functions run in a threadpool.
tags: [python-types, type-hints, Annotated, pydantic, async, await, concurrency, threadpool]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-fd7b2ae6eaa9dc0952e51e70
    resource: repo://docs_src/python_types/tutorial011_py310.py
  - id: openwiki-source-1deb722f21a51dbcd993b0eb
    resource: repo://docs_src/python_types/tutorial013_py310.py
  - id: openwiki-source-f0c19533402c6bf5c789f498
    resource: repo://docs/en/docs/advanced/advanced-python-types.md
  - id: openwiki-source-83099dea33ef3297e6faa1ec
    resource: repo://docs/en/docs/async.md
  - id: openwiki-source-14deaaf4cdf18f4e43256a4c
    resource: repo://docs/en/docs/python-types.md
  - id: openwiki-source-46771283dce4d38560c5dc75
    resource: repo://fastapi/concurrency.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---
H1: Python Types and async/await
FASTAPI USES STANDARD PYTHON TYPE HINTS; SUPPORTS `async def` AND PLAIN `def`.
UNDERSTANDING BOTH MAKES THE REST OF THE FRAMEWORK PREDICTABLE.
H2: Type hints
TYPE HINTS: Optional ANNOTATIONS UNDERSTOOD BY EDITORS/TOOLS.
FASTAPI ALSO USES THEM AT RUNTIME TO CONVERT, VALIDATE, AND DOCUMENT DATA.
```python
def get_full_name(first_name: str, last_name: str):
    full_name = first_name.title() + " " + last_name.title()
    return full_name
```
H3: Simple and generic types
- SIMPLE: `str`, `int`, `float`, `bool`, `bytes`.
- GENERIC CONTAINERS WITH INNER TYPES:
  - `list[str]`: list OF STRINGS.
  - `tuple[int, int, str]`, `set[bytes]`.
  - `dict[str, float]`: KEYS `str`; VALUES `float`.
- UNIONS: `int | str`.
- POSSIBLY `None`: `str | None`.
`docs_src/python_types/tutorial009_py310.py`:
```python
def say_hi(name: str | None = None):
    if name is not None:
        print(f"Hey {name}!")
    else:
        print("Hello World")
```
WHERE `|` CANNOT BE USED (e.g., SOME NON-ANNOTATION CONTEXTS), USE
`typing.Union[str, None]`. DOCS SUGGEST `Union[X, None]` OVER `Optional[X]`:
PARAMETER TYPED `Optional[str]` WITHOUT A DEFAULT REMAINS REQUIRED;
IT ONLY ACCEPTS `None`.
IN FASTAPI, PARAMETER OPTIONALITY COMES FROM ITS DEFAULT VALUE (`= None`),
NOT ITS TYPE.
H3: Classes as types
```python
class Person:
    def __init__(self, name: str):
        self.name = name


def get_person_name(one_person: Person):
    return one_person.name
```
H3: Pydantic models
PYDANTIC CLASSES DECLARE DATA SHAPES WITH TYPES;
INSTANCE CREATION VALIDATES AND CONVERTS INPUT (`tutorial011_py310.py`):
```python
from datetime import datetime

from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str = "John Doe"
    signup_ts: datetime | None = None
    friends: list[int] = []


external_data = {
    "id": "123",
    "signup_ts": "2017-06-01 12:22",
    "friends": [1, "2", b"3"],
}
user = User(**external_data)
print(user)
# > User id=123 name='John Doe' signup_ts=datetime.datetime(2017, 6, 1, 12, 22) friends=[1, 2, 3]
```
FASTAPI USES PYDANTIC (v2) FOR ALL REQUEST/RESPONSE DATA.
SEE [Request Body](../request/request-body.md).
H3: `Annotated`: types with metadata
`typing.Annotated[T, ...]` ATTACHES EXTRA METADATA TO A TYPE WITHOUT
CHANGING IT (`tutorial013_py310.py`):
```python
from typing import Annotated


def say_hello(name: Annotated[str, "this is just metadata"]) -> str:
    return f"Hello {name}"
```
PYTHON IGNORES THE METADATA; FASTAPI READS IT.
USE THIS TO DECLARE PARAMETER SOURCES, VALIDATION, AND DEPENDENCIES:
```python
from typing import Annotated
from fastapi import Depends, Query

async def read_items(
    q: Annotated[str | None, Query(max_length=50)] = None,
    commons: Annotated[dict, Depends(common_parameters)] = ...,
): ...
```
`Annotated` IS THE RECOMMENDED STYLE THROUGHOUT THE DOCS.
H3: What FastAPI does with types
ONE DECLARATION PROVIDES EDITOR COMPLETION/TYPE CHECKS; CONVERTS INCOMING
STRINGS/JSON TO PYTHON TYPES; VALIDATES WITH AUTOMATIC 422 ERRORS; CONVERTS
OUTPUTS TO JSON; AND PROVIDES OpenAPI DOCUMENTATION.
H2: `async def` vs `def`
H3: Quick rules
- LIBRARY REQUIRES `await` (e.g., async DB DRIVER, `httpx.AsyncClient`):
  USE `async def` AND `await`:
  ```python
  @app.get("/")
  async def read_results():
      results = await some_library()
      return results
  ```
- LIBRARY BLOCKS AND DOES NOT SUPPORT `await` (MANY DB LIBRARIES, FILE I/O,
  `requests`): USE PLAIN `def`:
  ```python
  @app.get("/")
  def results():
      results = some_library()
      return results
  ```
- FUNCTION WAITS FOR NOTHING (QUICK, PURE COMPUTATION): USE `async def`.
- NOT SURE: USE PLAIN `def`.
MIX BOTH FREELY ACROSS PATH OPERATIONS AND DEPENDENCIES.
H3: Why it matters (what FastAPI does)
- `async def` PATH OPERATIONS: AWAITED DIRECTLY ON EVENT LOOP. BLOCKING CALLS BLOCK THE WHOLE SERVER PROCESS FOR THAT TIME; AVOID BLOCKING I/O.
- Plain `def` PATH OPERATIONS RUN IN EXTERNAL THREADPOOL AND ARE AWAITED (`run_in_threadpool` IN `run_endpoint_function`, `fastapi/routing.py`); BLOCKING CALLS DO NOT FREEZE EVENT LOOP.
- SAME FOR DEPENDENCIES/SUB-DEPENDENCIES: `def` RUN IN THREADPOOL; `async def` ARE AWAITED; `def` GENERATOR (`yield`) DEPENDENCIES RUN ENTER/EXIT IN THREADS.
- FastAPI ONLY DECIDES HOW TO CALL FUNCTIONS IT CALLS (PATH OPERATIONS, DEPENDENCIES); OWN UTILITY FUNCTIONS ARE UNAFFECTED. CALL HELPERS NORMALLY OR `await` THEM IF `async def`.

NOTE: FOR TRIVIAL COMPUTE-ONLY ENDPOINTS, `async def` IS SLIGHTLY FASTER THAN `def` IN FastAPI (NO THREAD HOP)—OPPOSITE OF SOME OTHER FRAMEWORKS.

`fastapi.concurrency` RE-EXPORTS STARLETTE'S `run_in_threadpool`, `iterate_in_threadpool` AND `run_until_first_complete`; USE THESE TO CALL BLOCKING CODE FROM OWN `async` CODE:

```python
from fastapi.concurrency import run_in_threadpool

result = await run_in_threadpool(blocking_function, arg1, arg2)
```

H3: CONCURRENCY VS PARALLELISM

`async` PROVIDES CONCURRENCY: WHILE ONE REQUEST WAITS FOR I/O (NETWORK, DB, DISK), SERVER WORKS ON OTHERS. IDEAL FOR WEB APIs, WHICH SPEND MOST TIME WAITING. CPU-BOUND WORK (e.g. ML INFERENCE) BENEFITS FROM PARALLELISM—MULTIPLE PROCESSES/WORKERS (SEE [DEPLOYMENT CONCEPTS](../deployment/deployment-concepts-and-servers.md)) OR A TASK QUEUE.

H2: RELATED

- [FIRST STEPS](first-steps.md)
- [HOW FASTAPI HANDLES A REQUEST](../internals/request-handling-internals.md)
- [DATACLASSES, SEPARATE OpenAPI SCHEMAS AND PYDANTIC v1 TO v2](../models/dataclasses-and-pydantic-versions.md)
