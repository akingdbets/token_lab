---
type: guide
title: GraphQL과 OpenTelemetry 연동
description: Strawberry의 GraphQLRouter 등 ASGI 호환 GraphQL 라이브러리를 FastAPI에 붙이는 방법과, FastAPI 내장 OpenTelemetry 지원(HTTP 트레이스·메트릭·로그, WebSocket 트레이스)을 OTLP 환경 변수와 FastAPI(telemetry={...}) 설정(tracer_provider, operation_spans, exclude, auto_configure 등)으로 구성하는 방법을 설명한다.
tags: [graphql, strawberry, opentelemetry, telemetry, tracing, metrics, observability]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-43125d1f0ce73ed6acecd9cd
    resource: repo://docs_src/graphql_/tutorial001_py310.py
  - id: openwiki-source-539d9ab9f499fc843911a1d7
    resource: repo://docs_src/opentelemetry/tutorial001_py310.py
  - id: openwiki-source-4c452bd926f1b0947619f144
    resource: repo://docs_src/opentelemetry/tutorial002_py310.py
  - id: openwiki-source-07582db320603f82fd723950
    resource: repo://docs_src/opentelemetry/tutorial003_py310.py
  - id: openwiki-source-975b7cc9785fa4765144633f
    resource: repo://docs/en/docs/advanced/opentelemetry.md
  - id: openwiki-source-e2ee34879f38d2f0f7092b69
    resource: repo://fastapi/telemetry/_api.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# GraphQL과 OpenTelemetry 연동

## GraphQL

FastAPI는 **ASGI** 표준 기반이므로 ASGI 호환 GraphQL 라이브러리를 쉽게 통합할 수 있고, 일반 경로 작업과 GraphQL을 한 앱에서 함께 쓸 수 있다. GraphQL은 특정 사용 사례에 맞는 장단점이 있으므로 이점이 단점을 상쇄하는지 먼저 평가한다.

### ASGI를 지원하는 GraphQL 라이브러리

| 라이브러리 | FastAPI 연동 |
| --- | --- |
| [Strawberry](https://strawberry.rocks/) 🍓 | [FastAPI 연동 문서](https://strawberry.rocks/docs/integrations/fastapi) — **권장** |
| [Ariadne](https://ariadnegraphql.org/) | [FastAPI 연동 문서](https://ariadnegraphql.org/server/Integrations/fastapi-integration) |
| [Tartiflette](https://tartiflette.io/) | [Tartiflette ASGI](https://tartiflette.github.io/tartiflette-asgi/) |
| [Graphene](https://graphene-python.org/) | [starlette-graphene3](https://github.com/ciscorn/starlette-graphene3) |

### Strawberry로 GraphQL

Strawberry는 **타입 주석** 기반이라 FastAPI 설계와 가장 가깝다.

```Python
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

`GraphQLRouter`는 FastAPI 라우터처럼 `app.include_router()`로 포함한다([큰 애플리케이션](../app-structure/bigger-applications.md)).

### Starlette의 구 GraphQLApp

예전 Starlette의 `GraphQLApp`(Graphene 연동)은 deprecated되었다. 이를 쓰던 코드는 인터페이스가 거의 같은 [starlette-graphene3](https://github.com/ciscorn/starlette-graphene3)로 옮기면 된다. 다만 새로 시작한다면 Strawberry를 권장한다.

## OpenTelemetry

**텔레메트리**는 앱 동작에 대한 데이터다.

- **메트릭**: 응답 시간, 처리 중인 요청 수처럼 시간에 따라 요약할 수 있는 측정값
- **트레이스**: 개별 요청과 그 처리 과정의 기록. 시간이 측정된 각 작업을 **span**이라 한다.
- **로그**: 타임스탬프가 있는 이벤트 기록

[OpenTelemetry](https://opentelemetry.io/)는 텔레메트리를 수집해 모니터링 서비스로 보내는 표준·도구 모음이다. **FastAPI는 기본으로 OpenTelemetry를 지원**해 HTTP 요청의 트레이스·메트릭·로그를 기록하고, WebSocket 연결의 트레이스·로그도 기록한다. FastAPI는 필수 의존성으로 `opentelemetry-api`를 가지며, 데이터를 내보내는 SDK·OTLP exporter는 `fastapi[standard]`(또는 `fastapi[opentelemetry]`)에 포함된다.

### 기본 사용

```console
$ uv add "fastapi[standard]"
```

```Python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

텔레메트리를 위한 코드를 따로 작성할 필요가 없다.

- **FastAPI Cloud**: `fastapi[standard]`로 배포하면 메트릭이 자동으로 동작한다(Pro 플랜에서 Metrics 대시보드 제공).
- **다른 모니터링 서비스**: **OTLP**(OpenTelemetry 프로토콜)를 받는 엔드포인트를 환경 변수로 설정한다.

```bash
export OTEL_SERVICE_NAME=my-api
export OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com
```

- `OTEL_SERVICE_NAME`: 모니터링 서비스에서 앱을 식별하는 이름
- `OTEL_EXPORTER_OTLP_ENDPOINT`: HTTP/protobuf 기본 URL. 트레이스는 `/v1/traces`, 메트릭은 `/v1/metrics`, 로그는 `/v1/logs`로 전송된다.
- 인증이 필요하면 `OTEL_EXPORTER_OTLP_HEADERS`(예: `api-key=YOUR_API_KEY`)

`uv run fastapi run`으로 실행하고 `curl http://127.0.0.1:8000/items/1`을 보내면, 다음 내보내기 후 모니터링 서비스에서 `GET /items/{item_id}` span과 요청 수·응답 시간·활성 요청 메트릭을 볼 수 있다.

### telemetry 설정 딕셔너리

`FastAPI(telemetry={...})`는 `fastapi.telemetry.TelemetryConfig` 형식의 딕셔너리를 받는다. 생략한 설정은 기본값을 유지한다.

| 설정 | 용도 | 기본값 |
| --- | --- | --- |
| `tracer_provider` / `meter_provider` / `logger_provider` | 전역 provider 대신 사용할 provider | 전역 provider |
| `tracing` | HTTP 요청·WebSocket 연결 span 기록 | `True` |
| `metrics` | HTTP 요청 메트릭 기록 | `True` |
| `logs` | 검증 실패와 처리되지 않은 예외 기록 | `True` |
| `operation_spans` | 요청 내부 작업(의존성 해석, 엔드포인트 실행, 직렬화, 백그라운드 작업) span 추가 | `True` |
| `exclude` | ASGI scope를 받아 `True`를 반환하면 해당 요청 제외 | `None` |
| `auto_configure` | 환경 변수의 OTLP 엔드포인트에 대한 exporter 자동 추가 | `True` |

#### provider와 exporter 직접 구성

**provider**는 트레이스·메트릭·로그를 기록하는 객체를 공급하고, 그 구성이 데이터 처리·내보내기를 결정한다. 텔레메트리 라이브러리가 OpenTelemetry 전역 provider를 구성하면(앱 시작 전에) FastAPI가 자동으로 사용한다. 환경 변수에 OTLP 엔드포인트가 있으면 FastAPI가 활성화된 각 provider에 그 목적지 exporter를 추가하며, 기존 exporter도 계속 동작한다.

다른 라이브러리가 이미 환경 변수 목적지를 처리한다면 중복을 피하려 자동 설정을 끈다.

```python
app = FastAPI(telemetry={"auto_configure": False})
```

provider를 직접 넘길 수도 있다. 다음은 콘솔 exporter로 요청 span을 터미널에 출력한다.

```Python
from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

app = FastAPI(telemetry={"tracer_provider": tracer_provider})


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

`BatchSpanProcessor`는 span을 모아 백그라운드에서 전송한다. provider를 만든 애플리케이션/라이브러리가 그 종료를 관리하며, **애플리케이션이 넘긴 provider는 FastAPI가 종료하지 않는다**. FastAPI는 자신이 추가한 내보내기 컴포넌트만 관리한다. provider 설정을 lifespan 안에서 직접 한다면 `auto_configure`를 `False`로 둔다.

> OpenTelemetry는 기본적으로 전역 provider를 사용하므로, [마운트한 서브 애플리케이션](../app-structure/sub-applications-proxy-and-wsgi.md)별 독립 텔레메트리 구성은 보장되지 않는다.

#### 요청 작업 span

기본 요청 트레이스에는 의존성 해석, 경로 작업 함수 실행, 응답 직렬화, `BackgroundTasks`의 각 작업 span이 포함된다. 백그라운드 작업 span은 요청 트레이스에 속하지만 HTTP 응답 span이 끝난 뒤 실행되므로 측정된 응답 시간을 늘리지 않는다([백그라운드 작업](./background-tasks.md)). HTTP 요청 span만 남기려면:

```Python
from fastapi import FastAPI

app = FastAPI(telemetry={"operation_spans": False})
```

#### WebSocket 연결

각 WebSocket 연결은 `WS /ws/{room}` 같은 span을 가지며 핸들러와 의존성 정리를 포함한다. HTTP 요청 메트릭은 HTTP 요청만 대상이다. 코드 `1000`/`1001`의 정상 종료는 오류 로그를 남기지 않는다([WebSocket](./websockets.md)).

#### 오류 기록

- 처리되지 않은 예외는 요청/연결 트레이스에 연결된 OpenTelemetry 로그로 기록되며, 트레이스가 샘플링되지 않아도 기록된다.
- 예외 로그에는 타입·메시지·스택 트레이스가 포함되어 민감 정보가 있을 수 있다. provider의 로그 프로세서로 필터링·마스킹하거나 `logs`를 `False`로 끈다.
- 요청 검증 실패는 경로와 오류 수만 담은 경고 로그로 기록되며, 유효하지 않은 입력값은 포함하지 않는다.

예: 헬스 체크를 제외하고 메트릭만 수집

```python
from fastapi import FastAPI

app = FastAPI(
    telemetry={
        "tracing": False,
        "exclude": lambda scope: scope["path"] == "/health",
    }
)
```

### 요청 데이터에 접근: get_telemetry_data

`fastapi.telemetry.get_telemetry_data(context=None)`는 OpenTelemetry 컨텍스트에서 FastAPI가 채우는 `TelemetryData`(요청/WebSocket 객체, 파라미터 검증 전 본문 `body`, 의존성 해석 후 인자 `values`, 검증 오류 `errors`)를 읽는다. 동기 로그 프로세서 등에서 `record.context`를 넘겨 사용할 수 있으며, 요청이 끝나면 `None`을 반환한다. 이 데이터는 자동으로 span이나 로그에 추가되지 **않으므로**, 내보내기 전에 수집·마스킹 정책을 직접 적용해야 한다.

## 관련 페이지

- [배포 개념](../deployment/deployment-concepts-and-https.md)
- [Docker와 클라우드 배포](../deployment/docker-and-cloud.md) — FastAPI Cloud 메트릭
- [미들웨어](../middleware/middleware-and-cors.md)
