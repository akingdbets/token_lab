---
type: guide
title: 추가 모델, Union 응답, dataclasses
description: 입력(UserIn)·출력(UserOut)·DB(UserInDB) 모델을 분리하고 상속(UserBase)으로 중복을 줄이는 방법, model_dump()와 ** 언패킹으로 모델 간 변환, Union(anyOf)·list·dict 응답 모델, 표준 dataclasses와 pydantic.dataclasses를 요청·응답에 사용하는 방법을 설명한다.
tags: [pydantic, models, inheritance, union, anyof, dataclasses, response-model]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
sources:
  - id: openwiki-source-4fff8cb0aa0f6462c62095ec
    resource: repo://docs_src/dataclasses_/tutorial001_py310.py
  - id: openwiki-source-ced07dd154cac77e0f89290a
    resource: repo://docs_src/dataclasses_/tutorial002_py310.py
  - id: openwiki-source-1444b79c624a2dd4828c71dc
    resource: repo://docs_src/dataclasses_/tutorial003_py310.py
  - id: openwiki-source-15890a9c70d4080c4eaea06f
    resource: repo://docs_src/extra_models/tutorial002_py310.py
  - id: openwiki-source-131b291703682dc56b518f4a
    resource: repo://docs_src/extra_models/tutorial003_py310.py
  - id: openwiki-source-c299ace4d0d6ac62cab6497e
    resource: repo://docs_src/extra_models/tutorial004_py310.py
  - id: openwiki-source-5d4a94100600e93671597137
    resource: repo://docs_src/extra_models/tutorial005_py310.py
  - id: openwiki-source-8856aa4fa12f55213fc0a65b
    resource: repo://docs/en/docs/tutorial/extra-models.md
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 추가 모델, Union 응답, dataclasses

## 여러 모델이 필요한 이유

하나의 엔티티(예: 사용자)에 여러 관련 모델이 필요한 경우가 흔하다.

- **입력 모델**: 비밀번호를 받아야 한다.
- **출력 모델**: 비밀번호가 있으면 안 된다.
- **DB 모델**: 해시된 비밀번호가 필요하다.

> 사용자의 평문 비밀번호를 절대 저장하지 말고, 나중에 검증할 수 있는 "안전한 해시"를 저장한다([JWT와 비밀번호 해싱](../security/oauth2-jwt.md)).

## 상속으로 중복 줄이기

코드 중복은 버그, 보안 문제, 동기화 문제(한 곳만 고치고 다른 곳은 잊는 일)의 가능성을 높인다. 공통 필드를 기본 클래스에 두고 차이만 서브클래스에 선언한다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI()


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserIn(UserBase):
    password: str


class UserOut(UserBase):
    pass


class UserInDB(UserBase):
    hashed_password: str


def fake_password_hasher(raw_password: str):
    return "supersecret" + raw_password


def fake_save_user(user_in: UserIn):
    hashed_password = fake_password_hasher(user_in.password)
    user_in_db = UserInDB(**user_in.model_dump(), hashed_password=hashed_password)
    print("User saved! ..not really")
    return user_in_db


@app.post("/user/", response_model=UserOut)
async def create_user(user_in: UserIn):
    user_saved = fake_save_user(user_in)
    return user_saved
```

- `EmailStr`은 `email-validator` 패키지가 필요하다(`fastapi[standard]`에 포함).
- `fake_password_hasher`, `fake_save_user`는 데이터 흐름을 보여 주는 예시일 뿐 실제 보안을 제공하지 않는다.
- 반환값은 `UserInDB`(해시 포함)지만 `response_model=UserOut`이므로 출력은 `UserOut` 필드로 필터링된다([응답 모델](../responses/response-model.md)).

### `**user_in.model_dump()`의 의미

- Pydantic 모델의 `.model_dump()`는 모델 데이터를 담은 `dict`를 반환한다.

```Python
user_in = UserIn(username="john", password="secret", email="john.doe@example.com")
user_dict = user_in.model_dump()
# {'username': 'john', 'password': 'secret', 'email': 'john.doe@example.com', 'full_name': None}
```

- `dict`를 `**user_dict`로 함수나 클래스에 넘기면 Python이 키-값을 키워드 인자로 "언패킹"한다. `UserInDB(**user_dict)`는 `UserInDB(username=..., password=..., email=..., full_name=...)`와 같다.
- 따라서 `UserInDB(**user_in.model_dump())`는 다른 Pydantic 모델의 데이터로 새 모델을 만드는 것이다.
- 추가 키워드 인자를 덧붙일 수 있다: `UserInDB(**user_in.model_dump(), hashed_password=hashed_password)`. `UserInDB`에 없는 `password` 같은 추가 필드는 기본 설정상 무시된다.

## Union 응답(anyOf)

응답이 여러 타입 중 하나일 수 있다고 선언하면 OpenAPI에서 `anyOf`로 정의된다.

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class BaseItem(BaseModel):
    description: str
    type: str


class CarItem(BaseItem):
    type: str = "car"


class PlaneItem(BaseItem):
    type: str = "plane"
    size: int


items = {
    "item1": {"description": "All my friends drive a low rider", "type": "car"},
    "item2": {
        "description": "Music is my aeroplane, it's my aeroplane",
        "type": "plane",
        "size": 5,
    },
}


@app.get("/items/{item_id}", response_model=PlaneItem | CarItem)
async def read_item(item_id: str):
    return items[item_id]
```

- [Pydantic Union](https://pydantic.dev/docs/validation/latest/concepts/unions/)을 정의할 때는 **더 구체적인 타입을 먼저**, 덜 구체적인 타입을 나중에 둔다(`PlaneItem`이 `CarItem`보다 먼저).
- 이 저장소의 예제는 `response_model=PlaneItem | CarItem`을 사용한다. Python 3.10+에서는 클래스 간 `|` 연산이 유니언 타입을 만든다. 대신 `typing.Union[PlaneItem, CarItem]`을 써도 같다([Python 타입 힌트](../getting-started/python-types-and-async.md)). FastAPI 문서 본문은 인자 값 위치에서는 `Union`을 쓰라고 설명하는데, `|`를 지원하지 않는 객체(예: 문자열 전방 참조)가 섞이면 실제로 오류가 나므로 그런 경우에는 `Union`을 쓴다.

## 모델 리스트

```Python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str


items = [
    {"name": "Foo", "description": "There comes my hero"},
    {"name": "Red", "description": "It's my aeroplane"},
]


@app.get("/items/", response_model=list[Item])
async def read_items():
    return items
```

## 임의의 dict 응답

필드 이름을 미리 알 수 없을 때는 Pydantic 모델 없이 키·값 타입만 선언한다.

```Python
@app.get("/keyword-weights/", response_model=dict[str, float])
async def read_keyword_weights():
    return {"foo": 2.3, "bar": 3.4}
```

## dataclasses 사용

FastAPI는 Pydantic의 [dataclasses 내부 지원](https://pydantic.dev/docs/validation/latest/concepts/dataclasses/) 덕분에 표준 `dataclasses`도 요청 본문과 응답에 쓸 수 있다(FastAPI 0.67.0+). FastAPI가 표준 dataclass를 Pydantic dataclass로 변환해 검증·직렬화·문서화를 똑같이 수행한다.

```Python
from dataclasses import dataclass

from fastapi import FastAPI


@dataclass
class Item:
    name: str
    price: float
    description: str | None = None
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return item
```

dataclass는 Pydantic 모델이 할 수 있는 모든 일을 하지는 못하므로, 여전히 Pydantic 모델이 필요할 수 있다.

### response_model에 dataclass

```Python
from dataclasses import dataclass, field

from fastapi import FastAPI


@dataclass
class Item:
    name: str
    price: float
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    tax: float | None = None


app = FastAPI()


@app.get("/items/next", response_model=Item)
async def read_next_item():
    return {
        "name": "Island In The Moon",
        "price": 12.99,
        "description": "A place to be playin' and havin' fun",
        "tags": ["breater"],
    }
```

dataclass가 자동으로 Pydantic dataclass로 변환되어 스키마가 문서 UI에 표시된다.

### 중첩 구조와 pydantic.dataclasses

dataclass를 다른 타입 주석과 조합해 중첩 구조를 만들 수 있다. 자동 생성 문서에서 오류가 나는 등 일부 경우에는 표준 `dataclasses` 대신 **드롭인 대체품** `pydantic.dataclasses`를 쓴다.

```Python
from dataclasses import field

from fastapi import FastAPI
from pydantic.dataclasses import dataclass


@dataclass
class Item:
    name: str
    description: str | None = None


@dataclass
class Author:
    name: str
    items: list[Item] = field(default_factory=list)


app = FastAPI()


@app.post("/authors/{author_id}/items/", response_model=Author)
async def create_author_items(author_id: str, items: list[Item]):
    return {"name": author_id, "items": items}


@app.get("/authors/", response_model=list[Author])
def get_authors():
    return [
        {
            "name": "Breaters",
            "items": [
                {
                    "name": "Island In The Moon",
                    "description": "A place to be playin' and havin' fun",
                },
                {"name": "Holy Buddies"},
            ],
        },
    ]
```

- `field`는 여전히 표준 `dataclasses`에서 가져온다.
- 요청 본문으로 `list[Item]`처럼 dataclass와 표준 타입 주석을 조합할 수 있다.
- dataclass를 담은 딕셔너리나 순수 딕셔너리를 반환해도 `response_model`이 변환·직렬화한다.
- dataclass는 다른 Pydantic 모델과 조합·상속·포함할 수 있다.

## 관련 페이지

- [응답 모델](../responses/response-model.md)
- [중첩 모델과 추가 데이터 타입](../request/nested-models-and-data-types.md)
- [SQL 데이터베이스](../integrations/sql-databases.md) — HeroBase/HeroCreate/HeroPublic 패턴
- [OpenAPI 입력/출력 스키마 분리](../openapi/customizing-openapi-and-docs-ui.md)
