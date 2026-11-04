---
type: guide
title: GraphQL and OpenTelemetry Integrations
description: Add a GraphQL endpoint with Strawberry's GraphQLRouter (or other ASGI GraphQL libraries), and use FastAPI's built-in OpenTelemetry support for traces, metrics and logs via OTLP environment variables or the telemetry= configuration dict.
tags: [graphql, strawberry, opentelemetry, telemetry, tracing, metrics, logs, OTLP, observability]
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

H1: GraphQL and OpenTelemetry Integrations

H2: GraphQL

FASTAPI IS ASGI-BASED: COMBINE ANY ASGI-COMPATIBLE GRAPHQL LIBRARY
WITH NORMAL PATH OPERATIONS IN SAME APP.

ASGI-SUPPORTED LIBRARIES:
- Strawberry: RECOMMENDED; TYPE-ANNOTATION-BASED LIKE FASTAPI;
  HAS FASTAPI INTEGRATION DOCS
- Ariadne: HAS FASTAPI INTEGRATION DOCS
- Tartiflette: VIA Tartiflette ASGI
- Graphene: VIA `starlette-graphene3`

H3: Strawberry example

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

`GraphQLRouter` IS AN `APIRouter`: ADD WITH `include_router()` LIKE ANY ROUTER;
CAN USE FASTAPI DEPENDENCIES FOR context.
GRAPHQL ENDPOINT: `/graphql`.

starlette'S OLD `GraphQLApp` (FOR Graphene) IS DEPRECATED.
MIGRATE TO `starlette-graphene3`, WITH ALMOST IDENTICAL INTERFACE,
OR CONSIDER Strawberry.

GRAPHQL TYPICALLY USES ONLY `POST` FOR ALL OPERATIONS.
EVALUATE WHETHER ITS TRADE-OFFS SUIT YOUR USE CASE VS
A PLAIN REST-STYLE API.

====

H2: OpenTelemetry

telemetry: DATA ABOUT RUNNING APP.
metrics: AGGREGATED MEASUREMENTS, e.g. request COUNTS AND DURATIONS.
traces: PER-request RECORDS COMPOSED OF TIMED SPANS.
logs: TIMESTAMPED EVENTS.
OpenTelemetry: standard FOR COLLECTING AND EXPORTING telemetry DATA.

FASTAPI HAS BUILT-IN OpenTelemetry SUPPORT, ENABLED BY DEFAULT:
- HTTP REQUESTS: traces, metrics, logs
- WEBSOCKET CONNECTIONS: traces, logs

`opentelemetry-api` IS A CORE DEPENDENCY.
SDK AND OTLP HTTP EXPORTER COME WITH `fastapi[standard]`
OR THE `opentelemetry` EXTRA.
NO INSTRUMENTATION CODE REQUIRED:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

H3: Sending data to a monitoring service (OTLP)

CONFIGURE FASTAPI TO SEND DATA TO ANY SERVICE ACCEPTING OTLP
OVER HTTP/PROTOBUF, USING standard ENVIRONMENT VARIABLES:

```bash
export OTEL_SERVICE_NAME=my-api
export OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com
# if required by the service:
export OTEL_EXPORTER_OTLP_HEADERS=api-key=YOUR_API_KEY

fastapi run
```

UNDER ENDPOINT:
- traces → `/v1/traces`
- metrics → `/v1/metrics`
- logs → `/v1/logs`

AFTER request TO `/items/1`, EXPECT `GET /items/{item_id}` SPAN
AND metrics FOR request COUNT, RESPONSE DURATION,
AND ACTIVE REQUESTS.

ON FastAPI Cloud, metrics WORK AUTOMATICALLY WITH `fastapi[standard]`.

H3: Configuring with `telemetry=`

`FastAPI(telemetry={...})` ACCEPTS A `TelemetryConfig` DICT
FROM `fastapi.telemetry`.
DEFAULTS:
| KEY | PURPOSE | DEFAULT |
|-----|---------|---------|
| `tracing` | HTTP request + WebSocket CONNECTION SPANS | `True` |
| `metrics` | HTTP request metrics | `True` |
| `logs` | VALIDATION-FAILURE + UNHANDLED-EXCEPTION logs | `True` |
| `operation_spans` | CHILD SPANS: DEPENDENCY RESOLUTION, ENDPOINT FUNCTION, RESPONSE SERIALIZATION, EACH `BackgroundTasks` TASK | `True` |
| `exclude` | FUNCTION RECEIVES ASGI `scope`; RETURN `True` TO SKIP request | `None` |
| `auto_configure` | ADD OTLP EXPORTERS FOR ENDPOINTS SET IN ENVIRONMENT VARIABLES | `True` |
| `tracer_provider`, `meter_provider`, `logger_provider` | EXPLICIT OPENTELEMETRY PROVIDERS | `None` (USE GLOBAL PROVIDERS) |

USE YOUR OWN PROVIDER, e.g. PRINT SPANS TO CONSOLE (`docs_src/opentelemetry/tutorial002_py310.py`):

```python
from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

app = FastAPI(telemetry={"tracer_provider": tracer_provider})
```

HTTP request SPAN ONLY; NO OPERATION SPANS (`tutorial003_py310.py`):

```python
app = FastAPI(telemetry={"operation_spans": False})
```

metrics ONLY; SKIP HEALTH CHECKS:

```python
app = FastAPI(
    telemetry={
        "tracing": False,
        "exclude": lambda scope: scope["path"] == "/health",
    }
)
```

BEHAVIOR DETAILS:

- IF A telemetry LIBRARY CONFIGURES OPENTELEMETRY'S **GLOBAL** PROVIDERS
  BEFORE APP START, FASTAPI USES THEM.
  WITH AN OTLP ENDPOINT IN THE ENVIRONMENT, FASTAPI ADDS AN EXPORTER TO
  EACH ENABLED PROVIDER; EXISTING EXPORTERS KEEP WORKING.
  IF ANOTHER LIBRARY ALREADY EXPORTS TO THE ENV ENDPOINT, SET
  `auto_configure=False` TO AVOID DUPLICATES; ALSO DO THIS WHEN YOU
  CONFIGURE PROVIDERS YOURSELF, e.g. IN LIFESPAN.
- PROVIDER CREATOR MANAGES PROVIDER SHUTDOWN; FASTAPI MANAGES EXPORT
  COMPONENTS IT ADDS.
- BACKGROUND TASK SPANS BELONG TO THE request TRACE BUT RUN AFTER THE
  HTTP RESPONSE SPAN ENDS; THEY DON'T INCREASE RESPONSE TIME.
- EACH WebSocket CONNECTION GETS A SPAN LIKE `WS /ws/{room}`.
  NORMAL DISCONNECTS (CODES `1000`/`1001`) PRODUCE NO ERROR logs.
- UNHANDLED EXCEPTIONS ARE RECORDED AS logs (TYPE, MESSAGE, STACK TRACE)
  LINKED TO THE TRACE, EVEN IF UNSAMPLED.
  logs MAY CONTAIN SENSITIVE DATA: REDACT WITH LOG PROCESSORS OR SET
  `logs=False`.
  request VALIDATION FAILURES ARE LOGGED AS WARNINGS WITH ROUTE + ERROR
  COUNT, WITHOUT INVALID INPUT.
- PROVIDERS ARE GLOBAL BY DEFAULT; INDEPENDENT telemetry CONFIGURATION
  FOR MOUNTED SUB-APPLICATIONS IS NOT GUARANTEED.

H3: ACCESSING request DATA FROM PROCESSORS

`fastapi.telemetry.get_telemetry_data(context=None)` RETURNS A
`TelemetryData` OBJECT FOR THE CURRENT request OR CONNECTION, OR `None`
AFTER IT FINISHES.
FIELDS: `request`, `websocket`, `body` (READ BEFORE VALIDATION),
`values` (PARSED ARGUMENTS AFTER DEPENDENCY RESOLUTION), `errors`
(VALIDATION errors WITH ORIGINAL INPUT).
FASTAPI POPULATES THESE AS IT HANDLES THE request.
INTENDED FOR SYNCHRONOUS OPENTELEMETRY SPAN/LOG PROCESSORS;
READ-ONLY; APPLY YOUR OWN REDACTION.
NOT ADDED TO EXPORTED DATA AUTOMATICALLY.

H3: RELATED

- [MIDDLEWARE](../middleware/middleware.md)
- [BIGGER APPLICATIONS WITH `APIRouter`](../app-structure/bigger-applications.md)
- [BACKGROUND TASKS](background-tasks.md)
