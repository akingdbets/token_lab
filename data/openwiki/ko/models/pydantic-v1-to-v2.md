---
type: how-to
title: Pydantic v1에서 v2로 마이그레이션
description: 현재 FastAPI가 Pydantic v2만 지원하게 된 버전 이력(0.100.0, 0.119.0, 0.126.0, 0.128.0), Python 3.14에서 pydantic.v1 미지원, 테스트와 bump-pydantic으로 마이그레이션하는 방법, 과거 0.119~0.127에서 제공된 pydantic.v1 임시 지원과 현재 버전에서 pydantic.v1 모델 사용 시 PydanticV1NotSupportedError가 발생한다는 점을 설명한다.
tags: [pydantic, migration, pydantic-v2, bump-pydantic, compatibility]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-5e939e20b3e8fc2c03e44322
    resource: repo://docs_src/pydantic_v1_in_v2/tutorial003_an_py310.py
  - id: openwiki-source-ec68b83a934d7fc4eb1f527d
    resource: repo://docs_src/pydantic_v1_in_v2/tutorial004_an_py310.py
  - id: openwiki-source-01c7db97f3abec2e53d5dfa5
    resource: repo://docs/en/docs/how-to/migrate-from-pydantic-v1-to-pydantic-v2.md
  - id: openwiki-source-658293c5ba0aa1bcd6505fc5
    resource: repo://fastapi/encoders.py
  - id: openwiki-source-6960ae62409012c9993d0ec2
    resource: repo://fastapi/exceptions.py
  - id: openwiki-source-4aca434010af1ee8d02a42a5
    resource: repo://fastapi/utils.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# Pydantic v1에서 v2로 마이그레이션

오래된 FastAPI 앱은 Pydantic v1을 사용하고 있을 수 있다. **현재 FastAPI는 Pydantic v2만 지원한다**(이 저장소의 `pyproject.toml`은 `pydantic>=2.9.0`을 요구한다).

## 버전 이력

| FastAPI 버전 | Pydantic 지원 |
| --- | --- |
| 0.100.0 | Pydantic v1 또는 v2 중 설치된 것을 사용 |
| 0.119.0 | Pydantic v2 안의 `pydantic.v1`에 대한 **부분 지원** 추가(마이그레이션 보조용) |
| 0.126.0 | Pydantic v1 지원 중단(`pydantic.v1`은 잠시 유지) |
| 0.128.0 | `pydantic.v1` 지원도 중단 → **Pydantic v2 필수** |

> Pydantic 팀은 **Python 3.14**부터 Pydantic v1(및 `pydantic.v1` 서브모듈) 지원을 중단했다. 최신 Python을 쓰려면 Pydantic v2가 필요하다.

## 현재 버전에서 pydantic.v1 모델을 쓰면

`pydantic.v1` 모델을 응답 모델·파라미터 등으로 사용하면 `fastapi.exceptions.PydanticV1NotSupportedError`(`FastAPIError` 하위 클래스)가 발생한다. 메시지는 "pydantic.v1 models are no longer supported by FastAPI. Please update the response model ..." 형식이다. `jsonable_encoder()`로 `pydantic.v1` 모델 인스턴스를 변환하려 해도 같은 오류가 난다.

## 마이그레이션 방법

### 1. 공식 가이드 읽기

Pydantic 공식 [Migration Guide](https://pydantic.dev/docs/validation/latest/get-started/migration/)는 변경 사항, 더 정확하고 엄격해진 검증, 주의점을 설명한다.

### 2. 테스트 준비

앱에 [테스트](../testing/testing-basics.md)를 마련하고 CI에서 실행한다. 업그레이드 후 모든 것이 예상대로 동작하는지 확인할 수 있다.

### 3. bump-pydantic

특별한 커스터마이징이 없는 일반 Pydantic 모델이라면 대부분 자동화할 수 있다. Pydantic 팀의 [`bump-pydantic`](https://github.com/pydantic/bump-pydantic)이 바꿔야 할 코드 대부분을 자동으로 수정한다. 그 후 테스트를 실행해 통과하면 끝이다.

주요 API 변화 예(일부):

| v1 | v2 |
| --- | --- |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.copy(update=...)` | `.model_copy(update=...)` |
| `parse_obj()` | `model_validate()` |
| `class Config: schema_extra = ...` | `model_config = {"json_schema_extra": ...}` |
| `orm_mode = True` | `from_attributes=True` |

이 위키의 예제는 모두 v2 API(`model_dump(exclude_unset=True)`, `model_copy(update=...)`, `model_config`, `model_validate`)를 사용한다([본문 업데이트](./body-updates-and-encoder.md), [스키마 예제](./schema-examples.md)).

## 참고: 과거의 pydantic.v1 임시 지원(0.119.0 ~ 0.127.x)

> 아래 기능은 **FastAPI 0.119.0에서 추가되어 0.128.0에서 제거**되었다. 현재 버전에서는 동작하지 않으며, 오래된 버전에서 점진적으로 옮길 때만 의미가 있다.

Pydantic v2는 v1 전체를 `pydantic.v1` 서브모듈로 포함한다(Python 3.13 이하). 해당 FastAPI 버전에서는 Pydantic을 v2로 올리고 임포트만 `pydantic.v1`로 바꿔도 대부분 동작했다.

```Python
from fastapi import FastAPI
from pydantic.v1 import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    size: float


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item) -> Item:
    return item
```

- v2 모델의 필드로 v1 모델을 쓰거나 그 반대는 Pydantic이 **지원하지 않는다**.
- 서로 다른 모델이 각각 v1·v2인 것은 같은 앱에서 가능했고, 한 경로 작업에서 입력은 v1, `response_model`은 v2인 조합도 가능했다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel as BaseModelV2
from pydantic.v1 import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    size: float


class ItemV2(BaseModelV2):
    name: str
    description: str | None = None
    size: float


app = FastAPI()


@app.post("/items/", response_model=ItemV2)
async def create_item(item: Item):
    return item
```

- v1 모델에 `Body`, `Query`, `Form` 등을 쓰려면 `fastapi.temp_pydantic_v1_params`에서 임포트했다. 이 모듈은 현재 저장소의 `fastapi` 패키지에 **존재하지 않는다**.

```Python
from typing import Annotated

from fastapi import FastAPI
from fastapi.temp_pydantic_v1_params import Body  # 0.119~0.127 전용
from pydantic.v1 import BaseModel


class Item(BaseModel):
    name: str
    description: str | None = None
    size: float


app = FastAPI()


@app.post("/items/")
async def create_item(item: Annotated[Item, Body(embed=True)]) -> Item:
    return item
```

### 점진적 마이그레이션 전략(해당 버전에서)

1. 먼저 `bump-pydantic`을 시도한다. 테스트가 통과하면 한 번에 끝난다.
2. 안 되면 Pydantic을 v2로 올리고 모든 모델 임포트를 `pydantic.v1`로 바꾼다.
3. 모델을 그룹 단위로 조금씩 v2로 옮긴다.
4. 최종적으로 모든 모델을 v2로 옮긴 뒤 FastAPI 0.128.0 이상으로 업그레이드한다.

## 관련 페이지

- [요청 본문](../request/request-body.md)
- [OpenAPI 확장](../openapi/customizing-openapi-and-docs-ui.md) — v2에서 입력/출력 스키마 분리(`separate_input_output_schemas`)
- [배포 개념: 버전 관리](../deployment/deployment-concepts-and-https.md)
