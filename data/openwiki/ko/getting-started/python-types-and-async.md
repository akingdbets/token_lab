---
type: concept
title: Python 타입 힌트와 async/await
description: FastAPI가 기반으로 하는 Python 타입 힌트(단순 타입, list/tuple/set/dict 제네릭, | 유니언과 None, 클래스, Pydantic 모델, Annotated 메타데이터)와 Union vs Optional, FastAPI가 async def와 def 경로 작업·의존성을 어떻게 실행하는지(이벤트 루프 vs 스레드풀)와 언제 무엇을 써야 하는지 설명한다.
tags: [python-types, type-hints, annotated, pydantic, async, concurrency, threadpool]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
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
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# Python 타입 힌트와 async/await

## 타입 힌트

Python은 선택적인 **타입 힌트**(타입 주석)를 지원한다. FastAPI는 전적으로 이 타입 힌트에 기반한다. 타입을 선언하면 에디터 자동 완성과 오류 검사를 받을 수 있고, FastAPI는 같은 선언으로 요청 데이터를 변환·검증·문서화한다.

```Python
def get_full_name(first_name: str, last_name: str):
    full_name = first_name.title() + " " + last_name.title()
    return full_name
```

### 단순 타입

`str`, `int`, `float`, `bool`, `bytes` 등 표준 타입을 모두 선언할 수 있다. "어떤 타입이든"은 `typing.Any`를 쓴다.

### 제네릭 타입

대괄호 안에 내부 타입("타입 파라미터")을 넣는 타입이다. 내장 `list`, `tuple`, `set`, `dict`를 그대로 쓴다.

```Python
def process_items(items: list[str]):
    for item in items:
        print(item)          # 에디터가 item이 str임을 안다


def process_items(items_t: tuple[int, int, str], items_s: set[bytes]):
    return items_t, items_s


def process_items(prices: dict[str, float]):  # 키: str, 값: float
    for item_name, item_price in prices.items():
        print(item_name)
        print(item_price)
```

### 유니언과 None

```Python
def process_item(item: int | str):
    print(item)


def say_hi(name: str | None = None):
    if name is not None:
        print(f"Hey {name}!")
    else:
        print("Hello World")
```

`|`를 쓸 수 없는 곳(예: 타입 주석이 아닌 `response_model=` 인자)에서는 `typing.Union`을 쓴다. `Optional[str]`은 `Union[str, None]`과 같지만, "optional"이라는 이름이 "생략 가능"으로 오해되기 쉽다. 기본값이 없으면 `None`을 허용하더라도 여전히 **필수** 파라미터다.

```python
from typing import Optional


def say_hi(name: Optional[str]):
    print(f"Hey {name}!")

say_hi()            # 오류! name은 필수
say_hi(name=None)   # 동작: None은 유효한 값
```

FastAPI 문서는 `Optional[X]`보다 `X | None`(또는 `Union[X, None]`)을 권장한다.

### 클래스를 타입으로

```Python
class Person:
    def __init__(self, name: str):
        self.name = name


def get_person_name(one_person: Person):
    return one_person.name
```

## Pydantic 모델

[Pydantic](https://pydantic.dev/docs/)은 데이터 검증 라이브러리다. 클래스 속성으로 데이터 "형태"를 선언하고, 인스턴스를 만들 때 값을 검증하며 가능하면 적절한 타입으로 변환한다.

```Python
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
print(user.id)
# > 123
```

FastAPI는 요청 본문, 응답 모델 등 모든 데이터 처리에 Pydantic(v2)을 사용한다([요청 본문](../request/request-body.md)).

## Annotated: 타입에 메타데이터 붙이기

```Python
from typing import Annotated


def say_hello(name: Annotated[str, "this is just metadata"]) -> str:
    return f"Hello {name}"
```

- Python 자체는 `Annotated`로 아무것도 하지 않으며, 에디터와 도구에게 타입은 여전히 `str`이다.
- **첫 번째 타입 파라미터가 실제 타입**이고, 나머지는 다른 도구를 위한 메타데이터다.
- FastAPI는 이 메타데이터 자리에서 `Query()`, `Path()`, `Body()`, `Depends()` 같은 정보를 읽는다. 예: `q: Annotated[str | None, Query(max_length=50)] = None`([쿼리 파라미터](../request/query-parameters.md), [의존성](../dependencies/dependency-injection-basics.md)).

## FastAPI에서 타입 힌트가 하는 일

타입 힌트로 파라미터를 선언하면:

- **에디터 지원**과 **타입 검사**를 받는다.
- FastAPI는 같은 선언으로 **요구사항 정의**(경로·쿼리 파라미터, 헤더, 본문, 의존성), 요청 데이터의 **타입 변환**, **검증**(유효하지 않으면 자동 오류 응답), OpenAPI **문서화**를 수행한다.

## 동시성과 async/await

### 빠른 규칙

- `await`로 호출하라는 서드파티 라이브러리를 쓰면 `async def`로 선언한다.

```Python
@app.get('/')
async def read_results():
    results = await some_library()
    return results
```

- `await`를 지원하지 않는 라이브러리(대부분의 DB 라이브러리 등)로 DB·API·파일 시스템과 통신하면 일반 `def`로 선언한다.

```Python
@app.get('/')
def results():
    results = some_library()
    return results
```

- 다른 무언가와 통신하며 기다릴 일이 없다면 `await`를 쓰지 않더라도 `async def`를 쓴다.
- 잘 모르겠으면 일반 `def`를 쓴다.
- `def`와 `async def`는 경로 작업마다 자유롭게 섞어 쓸 수 있다. 어떤 경우든 FastAPI는 비동기로 동작한다.
- `await`는 `async def` 함수 안에서만 쓸 수 있다.

### 개념 요약

- **비동기 코드**: 느린 I/O(네트워크, 디스크, DB, 원격 API 응답)를 기다리는 동안 다른 작업을 할 수 있게 하는 코드. 웹 서버처럼 대기 시간이 많은 작업에 적합하다(동시성, concurrency).
- **병렬성(parallelism)**: 여러 CPU 코어에서 동시에 계산. 머신러닝처럼 CPU 바운드 작업에 적합하며, FastAPI 앱도 [여러 워커 프로세스](../deployment/manual-deployment-and-workers.md)로 병렬성을 활용할 수 있다.
- `async def`로 정의한 함수를 호출하면 **코루틴**이 반환되며, `await`해야 실행 결과를 얻는다. FastAPI는 AnyIO를 통해 asyncio·Trio와 호환된다.

### FastAPI가 함수를 실행하는 방식(기술적 세부)

| 대상 | `async def` | `def` |
| --- | --- | --- |
| 경로 작업 함수 | 이벤트 루프에서 직접 `await` | 외부 **스레드풀**에서 실행한 뒤 `await`(`run_in_threadpool`) |
| 의존성·하위 의존성 | 직접 `await` | 스레드풀에서 실행 |
| yield 의존성 | `asynccontextmanager`로 감쌈 | `contextmanager` + 스레드풀(`contextmanager_in_threadpool`) |
| 직접 호출하는 유틸리티 함수 | 직접 `await`해야 함 | 그대로 호출(FastAPI가 관여하지 않음) |

- 일반 `def` 경로 작업 함수에서는 응답 모델 검증도 스레드풀에서 실행된다.
- `fastapi.concurrency`는 `run_in_threadpool`, `iterate_in_threadpool`, `run_until_first_complete`(Starlette)와 `contextmanager_in_threadpool`을 제공한다. `contextmanager_in_threadpool`은 커넥션 풀을 가진 컨텍스트 매니저의 `__exit__`이 스레드를 기다리다 교착 상태에 빠지지 않도록 별도 용량 제한기(`CapacityLimiter`)로 실행한다.
- 다른 비동기 프레임워크에서처럼 단순 계산만 하는 함수를 `def`로 선언하면 FastAPI에서는 오히려 스레드풀 오버헤드가 생긴다. 블로킹 I/O가 없다면 `async def`가 낫다.
- 반대로 `async def` 안에서 블로킹 I/O(동기 DB 드라이버, `time.sleep` 등)를 호출하면 이벤트 루프 전체가 막힌다.

## 관련 페이지

- [첫 단계](./first-steps.md)
- [의존성 주입 기초](../dependencies/dependency-injection-basics.md)
- [요청 처리 흐름](../internals/request-lifecycle.md)
- [스트리밍](../responses/streaming-and-sse.md) — 동기 이터레이터는 `iterate_in_threadpool`로 처리
