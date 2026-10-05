---
type: guide
title: Background Tasks
description: Run work after the response is sent using a BackgroundTasks parameter and add_task, add tasks from dependencies, how tasks attach to returned responses, and when to use a real task queue like Celery instead.
tags: [background-tasks, backgroundtasks, add_task, dependencies, celery, async]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-1cc99efb4a255c20ae28655e
    resource: repo://docs_src/background_tasks/tutorial001_py310.py
  - id: openwiki-source-84b400c1e155ab0fc9ca2054
    resource: repo://docs_src/background_tasks/tutorial002_an_py310.py
  - id: openwiki-source-d3c9d22ec2ffb7771384a96e
    resource: repo://docs/en/docs/tutorial/background-tasks.md
  - id: openwiki-source-aef05ad53d3c32b290b5dc5a
    resource: repo://fastapi/background.py
  - id: openwiki-source-b95ef10caaaf12bb7a1e46f9
    resource: repo://fastapi/routing.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Background Tasks

Background tasks run **after the response has been sent**. Use them for work the client shouldn't wait for: sending a notification email, writing a log entry, processing an uploaded file.

## Basic usage

Declare a parameter typed `BackgroundTasks` and call `add_task()` (`docs_src/background_tasks/tutorial001_py310.py`):

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

- FastAPI creates the `BackgroundTasks` object and injects it — don't instantiate it yourself.
- `add_task(func, *args, **kwargs)` takes the task function followed by its positional and keyword arguments (it's typed with `ParamSpec`, so editors check the arguments).
- The task can be `async def` (awaited) or plain `def` (run in a threadpool).
- Tasks run in the order they were added, in the same process, after the response is sent.

`fastapi.BackgroundTasks` subclasses Starlette's `BackgroundTasks`.

## Background tasks from dependencies

`BackgroundTasks` can be declared in dependencies, sub-dependencies and the path operation; FastAPI injects the **same object** everywhere in a request, so all tasks are collected together (`tutorial002_an_py310.py`):

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

Both log lines are written after the response is sent (the dependency's first, since it ran first).

## Returning a `Response` yourself

If your endpoint returns a `Response` object directly, FastAPI attaches the collected tasks to it **only if** that response has no `background` of its own (`if response.background is None: response.background = ...` in `fastapi/routing.py`). If you build a Starlette `Response(background=BackgroundTask(...))` yourself, the injected `BackgroundTasks` are not attached — use one mechanism per endpoint.

## Resources and `yield` dependencies

Since FastAPI 0.106.0, don't rely on objects from `yield` dependencies (such as a DB session) inside background tasks. Open a new session inside the task and pass simple values (like an object's ID) as arguments. See [Advanced Dependencies](../dependencies/advanced-dependencies.md).

## When to use a task queue instead

`BackgroundTasks` runs in your web process. For heavy computation, long jobs, retries, scheduling, or work that should survive restarts or run on other machines, use a dedicated tool such as **Celery** (with a broker like RabbitMQ or Redis). `BackgroundTasks` is ideal for small tasks that need access to the same app's variables and objects.

## Related

- [Dependency Injection Basics](../dependencies/dependency-injection-basics.md)
- [Custom Responses](../responses/custom-responses.md)
- [Lifespan Events](../app-structure/lifespan-events.md)
