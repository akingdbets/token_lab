---
type: guide
title: OpenAPI 콜백과 웹훅
description: 경로 작업 데코레이터의 callbacks=router.routes로 내 API가 호출할 외부 API(콜백)의 형태를 OpenAPI 표현식({$callback_url}, {$request.body.id})과 함께 문서화하는 방법, app.webhooks(APIRouter)로 내 앱이 보낼 웹훅 이벤트를 문서화하는 방법을 설명한다.
tags: [openapi, callbacks, webhooks, documentation, apirouter]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-888d96f6fc5d92d8169decac
    resource: repo://docs_src/openapi_callbacks/tutorial001_py310.py
  - id: openwiki-source-38d361bd8ca97b84b5de187d
    resource: repo://docs_src/openapi_webhooks/tutorial001_py310.py
  - id: openwiki-source-425df282d44c2c18b97b213e
    resource: repo://docs/en/docs/advanced/openapi-callbacks.md
  - id: openwiki-source-6be36cbacef48d41c20c7a17
    resource: repo://docs/en/docs/advanced/openapi-webhooks.md
  - id: openwiki-source-cc2e5f0f09d872ef60382cea
    resource: repo://fastapi/applications.py
  - id: openwiki-source-614fe982fd0d993d004af94d
    resource: repo://fastapi/openapi/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# OpenAPI 콜백과 웹훅

두 기능 모두 **내 API가 외부 시스템으로 보내는 요청**을 문서화한다. 실제 요청을 보내는 코드는 직접 작성해야 하며(예: [HTTPX](https://www.python-httpx.org)), FastAPI는 OpenAPI 문서만 생성한다.

| | 콜백(callbacks) | 웹훅(webhooks) |
| --- | --- | --- |
| 계기 | 특정 경로 작업 요청 처리 중/후 | 앱의 이벤트(구독 생성 등) |
| URL 출처 | 원래 요청의 일부(쿼리·본문 등)에서 OpenAPI 표현식으로 계산 | 사용자가 대시보드 등에서 별도로 등록 |
| 선언 위치 | 경로 작업 데코레이터 `callbacks=` | `app.webhooks` |
| OpenAPI | 해당 operation의 `callbacks` | 최상위 `webhooks`(OpenAPI 3.1.0+) |

## OpenAPI 콜백

외부 개발자(API 사용자)가 내 API에 요청을 보내면, 내 API가 그 개발자가 만든 **외부 API**로 다시 요청을 보내는("call back") 구조다. 이때 외부 API가 어떤 경로·본문·응답을 가져야 하는지 문서화하고 싶을 때 쓴다.

### 예: 청구서 앱

외부 개발자가 `POST`로 청구서를 만들면 내 API는 청구서를 고객에게 보내고, 돈을 받고, 외부 개발자의 API로 알림(콜백)을 보낸다.

```Python
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, HttpUrl

app = FastAPI()


class Invoice(BaseModel):
    id: str
    title: str | None = None
    customer: str
    total: float


class InvoiceEvent(BaseModel):
    description: str
    paid: bool


class InvoiceEventReceived(BaseModel):
    ok: bool


invoices_callback_router = APIRouter()


@invoices_callback_router.post(
    "{$callback_url}/invoices/{$request.body.id}", response_model=InvoiceEventReceived
)
def invoice_notification(body: InvoiceEvent):
    pass


@app.post("/invoices/", callbacks=invoices_callback_router.routes)
def create_invoice(invoice: Invoice, callback_url: HttpUrl | None = None):
    """
    Create an invoice.

    This will (let's imagine) let the API user (some external developer) create an
    invoice.

    And this path operation will:

    * Send the invoice to the client.
    * Collect the money from the client.
    * Send a notification back to the API user (the external developer), as a callback.
        * At this point is that the API will somehow send a POST request to the
            external API with the notification of the invoice event
            (e.g. "payment successful").
    """
    # Send the invoice, collect the money, send the notification (the callback)
    return {"msg": "Invoice received"}
```

- 일반 경로 작업 `create_invoice`는 `Invoice` 본문과 콜백 URL을 담을 쿼리 파라미터 `callback_url`(Pydantic `HttpUrl` 타입)을 받는다.
- 실제 콜백은 단순한 HTTP 요청이다. 예:

```Python
callback_url = "https://example.com/api/v1/invoices/events/"
httpx.post(callback_url, json={"description": "Invoice paid", "paid": True})
```

### 콜백 문서화 코드 작성

이 코드는 앱에서 **실행되지 않으며** 외부 API의 모습을 문서화하는 데만 쓰인다. 잠시 *외부 개발자*의 입장에서 외부 API를 구현한다고 생각하면 파라미터와 본문·응답 모델 위치가 자연스럽다.

1. **콜백용 `APIRouter`**를 새로 만든다(`invoices_callback_router`).
2. 그 라우터에 **콜백 경로 작업**을 선언한다.
   - 받을 본문을 선언한다(`body: InvoiceEvent`).
   - 반환할 응답을 선언할 수 있다(`response_model=InvoiceEventReceived`).
   - 실제 코드가 필요 없으므로 함수 본문은 `pass`면 된다.
3. 경로에 [OpenAPI 3 표현식](https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.1.0.md#key-expression)을 써서 원래 요청의 일부를 변수로 사용할 수 있다.
4. 원래 경로 작업에 `callbacks=invoices_callback_router.routes`를 넘긴다. 라우터 자체가 아니라 **`.routes`**를 넘긴다는 점에 주의한다.

### 콜백 경로 표현식

```Python
"{$callback_url}/invoices/{$request.body.id}"
```

외부 개발자가 다음과 같이 요청하면:

```
https://yourapi.com/invoices/?callback_url=https://www.external.org/events
```

```JSON
{
    "id": "2expen51ve",
    "customer": "Mr. Richie Rich",
    "total": "9999"
}
```

내 API는 처리 후 다음 URL로 콜백 요청을 보낸다.

```
https://www.external.org/events/invoices/2expen51ve
```

본문은 `{"description": "Payment celebration", "paid": true}` 같은 `InvoiceEvent`이고, 외부 API는 `{"ok": true}` 같은 `InvoiceEventReceived`를 응답할 것으로 기대한다. 콜백 URL에 쿼리 파라미터 `callback_url`의 값과 JSON 본문의 `id`가 모두 쓰였다.

### 생성되는 OpenAPI

FastAPI는 `callbacks`의 각 `APIRoute`에 대해 일반 경로와 같은 방식으로 operation 스키마를 만들고, 원래 operation의 `"callbacks"`에 `{콜백 함수 이름: {콜백 경로: ...}}` 형태로 넣는다. `/docs`에서 `create_invoice` 아래에 "Callbacks" 섹션으로 외부 API의 형태가 표시된다.

## OpenAPI 웹훅

**웹훅**은 사용자가 내 API로 요청을 보내는 대신, **내 앱이 사용자 시스템으로** 이벤트를 알리는 요청을 보내는 것이다.

일반적인 흐름:

- 내 코드에서 보낼 메시지(요청 **본문**)를 정의한다.
- 어떤 **시점**에 요청·이벤트를 보낼지 정의한다.
- 사용자가 (예: 웹 대시보드에서) 요청을 받을 **URL**을 등록한다.
- URL 등록과 실제 전송 로직은 모두 직접 구현한다.

FastAPI와 OpenAPI로 웹훅 이름, 보낼 HTTP 작업 종류(`POST`, `PUT` 등), 요청 본문을 문서화하면, 사용자가 수신 API를 구현하기 쉽고 일부 코드를 자동 생성할 수도 있다. 웹훅은 OpenAPI 3.1.0 이상에서 제공되며 FastAPI 0.99.0 이상이 지원한다.

```Python
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Subscription(BaseModel):
    username: str
    monthly_fee: float
    start_date: datetime


@app.webhooks.post("new-subscription")
def new_subscription(body: Subscription):
    """
    When a new user subscribes to your service we'll send you a POST request with this
    data to the URL that you register for the event `new-subscription` in the dashboard.
    """


@app.get("/users/")
def read_users():
    return ["Rick", "Morty"]
```

- `app.webhooks`는 문서 전용 경로 작업을 담는 **`APIRouter`**다. 경로 작업처럼 `@app.webhooks.post()` 등으로 선언한다.
- 웹훅에는 **경로**(`/items/` 같은)가 아니라 **식별자**(이벤트 이름)를 넘긴다. `"new-subscription"`이 웹훅 이름이다. 실제 URL 경로는 사용자가 다른 방식으로 정하기 때문이다.
- 정의한 웹훅은 OpenAPI 스키마(`app.openapi()`가 `webhooks=self.webhooks.routes`를 전달)와 `/docs`의 "Webhooks" 섹션에 나타난다.

## 관련 페이지

- [경로 작업 설정](../app-structure/path-operation-configuration.md)
- [OpenAPI 확장과 문서 UI](./customizing-openapi-and-docs-ui.md)
- [백그라운드 작업](../integrations/background-tasks.md) — 응답 후 콜백·웹훅 요청을 보낼 때
