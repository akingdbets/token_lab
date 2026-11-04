---
type: guide
title: background TASKS
description: RUN WORK AFTER Response SENT VIA BackgroundTasks PARAMETER/ add_task; ADD TASKS FROM DEPENDENCIES; ATTACH TASKS TO RETURNED RESPONSES; USE REAL QUEUE LIKE Celery INSTEAD WHEN NEEDED.
tags: [background-tasks, BackgroundTasks, add_task, dependencies, celery, async]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - ID: openwiki-source-1cc99efb4a255c20ae28655e
    resource: repo://docs_src/background_tasks/tutorial001_py310.py
  - ID: openwiki-source-84b400c1e155ab0fc9ca2054
    resource: repo://docs_src/background_tasks/tutorial002_an_py310.py
  - ID: openwiki-source-d3c9d22ec2ffb7771384a96e
    resource: repo://docs/en/docs/tutorial/background-tasks.md
  - ID: openwiki-source-aef05ad53d3c32b290b5dc5a
    resource: repo://fastapi/background.py
  - ID: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---
H1: background TASKS

background TASKS RUN AFTER Response SENT.
USE FOR WORK CLIENT NEEDN'T WAIT FOR: SEND NOTIFICATION EMAIL, WRITE LOG ENTRY, PROCESS UPLOADED FILE.

H2: BASIC USAGE

DECLARE `BackgroundTasks`-TYPED PARAMETER; CALL `add_task()` (`docs_src/background_tasks/tutorial001_py310.py`):

```python
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


def write_notification(email: str, message=""):
    with open("log.txt", mode="w") as email_file:
        content = f"notification for {email}: {message}"
        email_file.write(content)


@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}
```

- FastAPI CREATES AND INJECTS `BackgroundTasks`; DON'T INSTANTIATE IT YOURSELF.
- `add_task(func, *args, **kwargs)` TAKES TASK FUNCTION, THEN POSITIONAL/KEYWORD ARGUMENTS; `ParamSpec` TYPING LETS EDITORS CHECK ARGUMENTS.
- TASK FUNCTION MAY BE `async def` (AWAITED) OR PLAIN `def` (RUN IN THREADPOOL).
- TASKS RUN IN ADDITION ORDER, IN SAME PROCESS, AFTER Response SENT.

`fastapi.BackgroundTasks` SUBCLASSES Starlette's `BackgroundTasks`.

H2: background TASKS FROM DEPENDENCIES

DECLARE `BackgroundTasks` IN DEPENDENCIES, SUB-DEPENDENCIES, AND PATH OPERATION.
FastAPI INJECTS THE **SAME OBJECT** EVERYWHERE IN A REQUEST; ALL TASKS ARE COLLECTED TOGETHER (`tutorial002_an_py310.py`):

```python
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI

app = FastAPI()


def write_log(message: str):
    with open("log.txt", mode="a") as log:
        log.write(message)


def get_query(background_tasks: BackgroundTasks, q: str | None = None):
    if q:
        message = f"found query: {q}\n"
        background_tasks.add_task(write_log, message)
    return q


@app.post("/send-notification/{email}")
async def send_notification(
    email: str, background_tasks: BackgroundTasks, q: Annotated[str, Depends(get_query)]
):
    message = f"message to {email}\n"
    background_tasks.add_task(write_log, message)
    return {"message": "Message sent"}
```

BOTH LOG LINES ARE WRITTEN AFTER Response SENT.
DEPENDENCY'S LINE is FIRST, BECAUSE DEPENDENCY RAN FIRST.

H2: RETURNING A `Response` YOURSELF

if ENDPOINT DIRECTLY RETURNS A `Response` OBJECT, FastAPI ATTACHES COLLECTED TASKS
ONLY if Response HAS NO `background` OF ITS OWN
(`if response.background is None: response.background = ...` IN `fastapi/routing.py`).

if YOU BUILD A Starlette `Response(background=BackgroundTask(...))` YOURSELF,
INJECTED `BackgroundTasks` AREN'T ATTACHED.
USE ONE MECHANISM PER ENDPOINT.

H2: RESOURCES AND `yield` DEPENDENCIES

SINCE FastAPI 0.106.0, DON'T RELY ON OBJECTS FROM `yield` DEPENDENCIES
(E.G., DB SESSION) INSIDE background TASKS.
OPEN A NEW SESSION INSIDE TASK; PASS SIMPLE VALUES (E.G., OBJECT ID) AS ARGUMENTS.
SEE [ADVANCED DEPENDENCIES](../dependencies/advanced-dependencies.md).

H2: WHEN TO USE A TASK QUEUE INSTEAD

`BackgroundTasks` RUNS IN YOUR WEB PROCESS.
FOR HEAVY COMPUTATION, LONG JOBS, RETRIES, SCHEDULING, OR WORK THAT SHOULD
SURVIVE RESTARTS OR RUN ON OTHER MACHINES, USE DEDICATED TOOL LIKE **Celery**
(WITH BROKER LIKE RabbitMQ OR Redis).
`BackgroundTasks` is IDEAL FOR SMALL TASKS NEEDING ACCESS TO SAME APP'S VARIABLES AND OBJECTS.

H2: RELATED

- [DEPENDENCY INJECTION BASICS](../dependencies/dependency-injection-basics.md)
- [CUSTOM RESPONSES](../responses/custom-responses.md)
- [LIFESPAN EVENTS](../app-structure/lifespan-events.md)
