---
type: how-to
title: 클라이언트 SDK 생성
description: FastAPI가 생성하는 OpenAPI 3.1 스키마로 Hey API(@hey-api/openapi-ts), OpenAPI Generator 등을 이용해 TypeScript 등 클라이언트 SDK를 생성하는 방법, 태그로 서비스 분리, generate_unique_id_function으로 operationId·메서드 이름을 개선하고 생성 전 openapi.json을 전처리하는 방법을 설명한다.
tags: [openapi, sdk, client-generation, typescript, operation-id, tags]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-76de6f1988b3da87b99700d4
    resource: repo://docs_src/generate_clients/tutorial001_py310.py
  - id: openwiki-source-59a7865e2278cee3747d1fc0
    resource: repo://docs_src/generate_clients/tutorial002_py310.py
  - id: openwiki-source-a46bf4ffd2de64654d40232b
    resource: repo://docs_src/generate_clients/tutorial003_py310.py
  - id: openwiki-source-2b3a6ecf8322c7cd69b79190
    resource: repo://docs_src/generate_clients/tutorial004_py310.py
  - id: openwiki-source-87af7584e524afec4b61cf9d
    resource: repo://docs_src/generate_clients/tutorial004.js
  - id: openwiki-source-4546be900a921da774341d65
    resource: repo://docs/en/docs/advanced/generate-clients.md
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 클라이언트 SDK 생성

FastAPI API는 **OpenAPI** 명세로 기술되므로 많은 도구가 이해할 수 있다. 이를 이용해 최신 문서, 여러 언어의 클라이언트 라이브러리(**SDK**), 코드와 동기화된 테스트·자동화 워크플로를 생성할 수 있다.

## 오픈소스 SDK 생성기

- [OpenAPI Generator](https://openapi-generator.tech/): **여러 프로그래밍 언어** 지원
- [Hey API](https://heyapi.dev/): **TypeScript** 생태계 전용
- 더 많은 도구: [OpenAPI.Tools](https://openapi.tools/categories/sdk-generators)

FastAPI는 **OpenAPI 3.1** 스키마를 생성하므로, 사용하는 도구가 이 버전을 지원해야 한다.

## TypeScript SDK 만들기

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


class ResponseMessage(BaseModel):
    message: str


@app.post("/items/", response_model=ResponseMessage)
async def create_item(item: Item):
    return {"message": "item received"}


@app.get("/items/", response_model=list[Item])
async def get_items():
    return [
        {"name": "Plumbus", "price": 3},
        {"name": "Portal Gun", "price": 9001},
    ]
```

경로 작업이 요청·응답 모델(`Item`, `ResponseMessage`)을 선언했기 때문에 `/docs`에 스키마가 표시되고, 같은 정보가 OpenAPI 스키마에 들어가 클라이언트 코드 생성에 사용된다.

### Hey API로 생성

```sh
npx @hey-api/openapi-ts -i http://localhost:8000/openapi.json -o src/client
```

`./src/client`에 TypeScript SDK가 생성된다. 생성된 클라이언트를 쓰면 메서드, 보낼 페이로드(`Item` 모델의 `name`, `price`), 응답 객체에 대한 자동 완성과 인라인 오류를 받는다.

## 태그로 그룹화

```Python
class User(BaseModel):
    username: str
    email: str


@app.post("/items/", response_model=ResponseMessage, tags=["items"])
async def create_item(item: Item):
    return {"message": "Item received"}


@app.get("/items/", response_model=list[Item], tags=["items"])
async def get_items():
    return [
        {"name": "Plumbus", "price": 3},
        {"name": "Portal Gun", "price": 9001},
    ]


@app.post("/users/", response_model=ResponseMessage, tags=["users"])
async def create_user(user: User):
    return {"message": "User received"}
```

태그를 쓰면 생성기가 보통 클라이언트 코드도 태그별로 나눈다(`ItemsService`, `UsersService`). 태그 지정은 [경로 작업 설정](../app-structure/path-operation-configuration.md), 라우터 단위 태그는 [큰 애플리케이션](../app-structure/bigger-applications.md)을 참고한다.

### 메서드 이름 문제

기본 생성 메서드 이름은 깔끔하지 않다.

```TypeScript
ItemsService.createItemItemsPost({name: "Plumbus", price: 5})
```

생성기는 각 경로 작업의 OpenAPI **operationId**를 메서드 이름으로 쓴다. OpenAPI는 operationId가 모든 경로 작업에서 고유하기를 요구하므로, FastAPI는 기본적으로 **함수 이름 + 경로 + HTTP 메서드**로 만든다(예: `create_item_items__post`).

## 사용자 정의 operationId

operationId 생성 방식을 바꿔 클라이언트 메서드 이름을 단순하게 만들 수 있다. 대신 다른 방식으로 **고유성**을 보장해야 한다. 예를 들어 모든 경로 작업에 태그가 있도록 하고, **태그 + 함수 이름**으로 만든다.

FastAPI는 각 경로 작업의 **고유 ID**를 operationId와 요청·응답용 사용자 정의 모델 이름에 사용한다. 이 함수는 `APIRoute`를 받아 문자열을 반환하며, `generate_unique_id_function`으로 교체한다.

```Python
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel


def custom_generate_unique_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
```

다시 생성하면 메서드 이름이 URL 경로나 HTTP 작업 정보 없이 태그와 함수 이름으로 구성된다(예: `items-get_items` 기반). `generate_unique_id_function`은 `APIRouter`, `include_router()`, 개별 데코레이터에도 지정할 수 있다.

## 생성 전에 OpenAPI 전처리

이미 `ItemsService`라는 이름에 "items"가 들어 있는데 메서드 이름에도 태그가 붙는 중복이 남는다. OpenAPI 자체에서는 고유성을 위해 접두사를 유지하고, **클라이언트 생성 직전에만** `openapi.json`을 내려받아 접두사를 제거할 수 있다.

```Python
import json
from pathlib import Path

file_path = Path("./openapi.json")
openapi_content = json.loads(file_path.read_text())

for path_data in openapi_content["paths"].values():
    for operation in path_data.values():
        tag = operation["tags"][0]
        operation_id = operation["operationId"]
        to_remove = f"{tag}-"
        new_operation_id = operation_id[len(to_remove) :]
        operation["operationId"] = new_operation_id

file_path.write_text(json.dumps(openapi_content))
```

Node.js 버전(`docs_src/generate_clients/tutorial004.js`)도 있으며, 태그가 있고 operationId가 `태그-`로 시작할 때만 접두사를 제거한다. 그러면 `items-get_items`가 `get_items`가 된다. 이제 로컬 파일을 입력으로 생성한다.

```sh
npx @hey-api/openapi-ts -i ./openapi.json -o src/client
```

## 이점

- 메서드, 요청 페이로드(본문·쿼리 파라미터 등), 응답 페이로드에 대한 **자동 완성**과 **인라인 오류**
- 백엔드를 바꾼 뒤 클라이언트를 **다시 생성**하면 새 경로 작업은 메서드로 추가되고, 삭제된 것은 사라지며, 변경 사항이 자동으로 반영된다.
- 클라이언트를 **빌드**할 때 데이터 불일치가 있으면 오류가 나므로, 운영 환경 사용자에게 문제가 드러나기 전에 개발 초기에 많은 오류를 잡을 수 있다.

응답 모델에서 `id: int`처럼 항상 존재하는 필드를 명확히 선언하거나([SQL 데이터베이스](../integrations/sql-databases.md)의 `HeroPublic`), 입력/출력 스키마 분리를 활용하면([OpenAPI 확장](./customizing-openapi-and-docs-ui.md)) 생성된 클라이언트 인터페이스가 더 단순해진다.

## 관련 페이지

- [경로 작업 설정](../app-structure/path-operation-configuration.md) — `operation_id`, `generate_unique_id_function`
- [OpenAPI 확장과 문서 UI](./customizing-openapi-and-docs-ui.md)
