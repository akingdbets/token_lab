## Background Tasks
- Run **after the response has been sent** for work the client shouldn’t wait for, such as notification email, logging, or uploaded-file processing.

## Basic usage
- Declare a `BackgroundTasks` parameter; FastAPI creates and injects it—don’t instantiate it yourself. Call `add_task(func, *args, **kwargs)` with the task function and its positional/keyword arguments. It is typed with `ParamSpec`, so editors check arguments.
- Tasks may be `async def` (awaited) or plain `def` (run in a threadpool). They run in the order added, in the same process, after the response.
- `fastapi.BackgroundTasks` subclasses Starlette’s `BackgroundTasks`.
- Example imports: `from fastapi import BackgroundTasks, FastAPI`; `background_tasks.add_task(write_notification, email, message="some notification")`.

## Background tasks from dependencies
- `BackgroundTasks` may be declared in dependencies, sub-dependencies, and the path operation. FastAPI injects the **same object** throughout a request, collecting all tasks.
- Dependency tasks run in execution order: in the example, both log lines are written after the response, with the dependency’s first because it ran first.

## Returning a `Response` yourself
- FastAPI attaches collected tasks to a directly returned `Response` **only if** `response.background is None`.
- A Starlette `Response(background=BackgroundTask(...))` keeps its own background; injected `BackgroundTasks` are not attached. Use one mechanism per endpoint.

## Resources and `yield` dependencies
- Since FastAPI 0.106.0, don’t rely on objects from `yield` dependencies (for example, a DB session) inside tasks. Open a new session inside the task and pass simple values, such as an object’s ID. See [Advanced Dependencies](../dependencies/advanced-dependencies.md).

## When to use a task queue instead
- `BackgroundTasks` runs in the web process and suits small tasks needing access to the same app’s variables and objects. For heavy computation, long jobs, retries, scheduling, survival across restarts, or work on other machines, use a dedicated tool such as **Celery**, with a broker like RabbitMQ or Redis.
