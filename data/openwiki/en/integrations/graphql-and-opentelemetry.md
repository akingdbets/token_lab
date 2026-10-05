---
type: guide
title: GraphQL and OpenTelemetry Integrations
description: Add a GraphQL endpoint with Strawberry's GraphQLRouter (or other ASGI GraphQL libraries), and use FastAPI's built-in OpenTelemetry support for traces, metrics and logs via OTLP environment variables or the telemetry= configuration dict.
tags: [graphql, strawberry, opentelemetry, telemetry, tracing, metrics, logs, otlp, observability]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-43125d1f0ce73ed6acecd9cd
    resource: repo://docs_src/graphql_/tutorial001_py310.py
  - id: openwiki-source-4c452bd926f1b0947619f144
    resource: repo://docs_src/opentelemetry/tutorial002_py310.py
  - id: openwiki-source-07582db320603f82fd723950
    resource: repo://docs_src/opentelemetry/tutorial003_py310.py
  - id: openwiki-source-975b7cc9785fa4765144633f
    resource: repo://docs/en/docs/advanced/opentelemetry.md
  - id: openwiki-source-644930dab608fea97556e55a
    resource: repo://docs/en/docs/how-to/graphql.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-e2ee34879f38d2f0f7092b69
    resource: repo://fastapi/telemetry/_api.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# GraphQL and OpenTelemetry Integrations

## GraphQL

FastAPI is ASGI-based, so any ASGI-compatible GraphQL library can be combined with normal path operations in the same app. Libraries with ASGI support:

- **Strawberry** — recommended; type-annotation-based like FastAPI, with FastAPI integration docs
- **Ariadne** — has FastAPI integration docs
- **Tartiflette** — via Tartiflette ASGI
- **Graphene** — via `starlette-graphene3`

### Strawberry example

`docs_src/graphql_/tutorial001_py310.py`:

```python
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter


@strawberry.type
class User:
    name: str
    age: int


@strawberry.type
class Query:
    @strawberry.field
    def user(self) -> User:
        return User(name="Patrick", age=100)


schema = strawberry.Schema(query=Query)


graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")
```

`GraphQLRouter` is an `APIRouter`, so it's added with `include_router()` like any router (and can use FastAPI dependencies for context). The GraphQL endpoint is at `/graphql`.

Starlette's old `GraphQLApp` (for Graphene) is deprecated; migrate to `starlette-graphene3`, which has an almost identical interface — or consider Strawberry.

GraphQL typically uses only `POST` for all operations. Evaluate whether its trade-offs suit your use case compared to a plain REST-style API.

## OpenTelemetry

**Telemetry** is data about your running app: **metrics** (aggregated measurements like request counts and durations), **traces** (per-request records made of timed **spans**), and **logs** (timestamped events). **OpenTelemetry** is the standard for collecting and exporting it.

**FastAPI has OpenTelemetry support built in and enabled by default** for HTTP request traces, metrics and logs; WebSocket connections get traces and logs. `opentelemetry-api` is a core dependency; the SDK and OTLP HTTP exporter come with `fastapi[standard]` (or the `opentelemetry` extra). You don't need to write any instrumentation code:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

### Sending data to a monitoring service (OTLP)

Point FastAPI at any service that accepts **OTLP** over HTTP/protobuf using standard environment variables:

```bash
export OTEL_SERVICE_NAME=my-api
export OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com
# if required by the service:
export OTEL_EXPORTER_OTLP_HEADERS=api-key=YOUR_API_KEY

fastapi run
```

Traces go to `/v1/traces`, metrics to `/v1/metrics` and logs to `/v1/logs` under the endpoint. After a request to `/items/1` you'll see a `GET /items/{item_id}` span plus metrics for request count, response duration and active requests.

On **FastAPI Cloud**, metrics work automatically with `fastapi[standard]`.

### Configuring with `telemetry=`

`FastAPI(telemetry={...})` accepts a `TelemetryConfig` dict (from `fastapi.telemetry`). Defaults:

| Key | Purpose | Default |
|-----|---------|---------|
| `tracing` | HTTP request and WebSocket connection spans | `True` |
| `metrics` | HTTP request metrics | `True` |
| `logs` | Logs for validation failures and unhandled exceptions | `True` |
| `operation_spans` | Child spans for dependency resolution, the endpoint function, response serialization and each `BackgroundTasks` task | `True` |
| `exclude` | Function receiving the ASGI `scope`; return `True` to skip a request | `None` |
| `auto_configure` | Add OTLP exporters for endpoints set in environment variables | `True` |
| `tracer_provider`, `meter_provider`, `logger_provider` | Explicit OpenTelemetry providers | `None` (use global providers) |

Use your own provider, e.g. print spans to the console (`docs_src/opentelemetry/tutorial002_py310.py`):

```python
from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

app = FastAPI(telemetry={"tracer_provider": tracer_provider})
```

Only the HTTP request span, no operation spans (`tutorial003_py310.py`):

```python
app = FastAPI(telemetry={"operation_spans": False})
```

Metrics only, skipping health checks:

```python
app = FastAPI(
    telemetry={
        "tracing": False,
        "exclude": lambda scope: scope["path"] == "/health",
    }
)
```

Behavior details:

- If a telemetry library already configured OpenTelemetry's **global** providers before the app starts, FastAPI uses them. With an OTLP endpoint in the environment, FastAPI *adds* an exporter to each enabled provider; existing exporters keep working. If another library already exports to the env endpoint, set `auto_configure=False` to avoid duplicates (also when you set providers up yourself, e.g. in lifespan).
- Whoever creates a provider manages its shutdown; FastAPI manages the export components it adds.
- Background task spans belong to the request's trace but run after the HTTP response span ends, so they don't inflate response time.
- Each WebSocket connection gets a span like `WS /ws/{room}`. Normal disconnects (codes `1000`/`1001`) don't produce error logs.
- Unhandled exceptions are recorded as logs (type, message, stack trace) linked to the trace, even when the trace isn't sampled. They may contain sensitive data — redact with log processors or set `logs=False`. Request validation failures are logged as warnings with the route and error count, without the invalid input.
- Providers are global by default; independent telemetry configuration for mounted sub-applications is not guaranteed.

### Accessing request data from processors

`fastapi.telemetry.get_telemetry_data(context=None)` returns a `TelemetryData` object for the current request or connection (or `None` after it finishes). Its fields — `request`, `websocket`, `body` (as read before validation), `values` (parsed arguments after dependency resolution) and `errors` (validation errors with original input) — are populated as FastAPI handles the request. It's meant for synchronous OpenTelemetry span/log processors; treat it as read-only and apply your own redaction. It is **not** added to exported data automatically.

## Related

- [Middleware](../middleware/middleware.md)
- [Bigger Applications with APIRouter](../app-structure/bigger-applications.md)
- [Background Tasks](background-tasks.md)
