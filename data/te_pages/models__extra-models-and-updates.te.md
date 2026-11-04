---
type: guide
title: Extra Models, jsonable_encoder and Body Updates
description: Use separate input, output and database models (UserIn/UserOut/UserInDB) with inheritance, declare Union, list and dict responses, convert data with jsonable_encoder, and implement PUT replacement and PATCH partial updates with model_dump(exclude_unset=True) and model_copy(update=...).
tags: [models, pydantic, inheritance, union, jsonable_encoder, PUT, PATCH, partial-update, exclude_unset]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-5f519de595b6849750f292ab
    resource: repo://docs_src/body_updates/tutorial001_py310.py
  - id: openwiki-source-bff631448023340ec732b8ef
    resource: repo://docs_src/body_updates/tutorial002_py310.py
  - id: openwiki-source-8757c8be1c8c9c702c8a82f0
    resource: repo://docs_src/encoder/tutorial001_py310.py
  - id: openwiki-source-ac62bbfdea5459b31a4bf3b5
    resource: repo://docs_src/extra_models/tutorial001_py310.py
  - id: openwiki-source-15890a9c70d4080c4eaea06f
    resource: repo://docs_src/extra_models/tutorial002_py310.py
  - id: openwiki-source-131b291703682dc56b518f4a
    resource: repo://docs_src/extra_models/tutorial003_py310.py
  - id: openwiki-source-c299ace4d0d6ac62cab6497e
    resource: repo://docs_src/extra_models/tutorial004_py310.py
  - id: openwiki-source-5d4a94100600e93671597137
    resource: repo://docs_src/extra_models/tutorial005_py310.py
  - id: openwiki-source-46c2c90f17a97455b57ac0a9
    resource: repo://docs/en/docs/tutorial/body-updates.md
  - id: openwiki-source-8856aa4fa12f55213fc0a65b
    resource: repo://docs/en/docs/tutorial/extra-models.md
  - id: openwiki-source-658293c5ba0aa1bcd6505fc5
    resource: repo://fastapi/encoders.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

H1: EXTRA MODELS, jsonable_encoder AND BODY UPDATES

H2: MULTIPLE MODELS PER ENTITY

ENTITY OFTEN NEEDS DIFFERENT SHAPES IN DIFFERENT CONTEXTS. USER:
- INPUT MODEL: PLAIN PASSWORD
- OUTPUT MODEL: NO PASSWORD
- DATABASE MODEL: HASHED PASSWORD

NEVER RETURN OR STORE PLAIN PASSWORDS.
`docs_src/extra_models/tutorial001_py310.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI()


class UserIn(BaseModel):
    username: str
    password: str
    email: EmailStr
    full_name: str | None = None


class UserOut(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None


class UserInDB(BaseModel):
    username: str
    hashed_password: str
    email: EmailStr
    full_name: str | None = None


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

KEY IDIOMS:
- `user_in.model_dump()` RETURNS MODEL DATA AS A `dict`.
- `UserInDB(**user_dict, hashed_password=...)` UNPACKS `user_dict` AS
  KEYWORD ARGUMENTS AND ADDS AN EXTRA FIELD. PYDANTIC VALIDATES THE NEW OBJECT.
- `response_model=UserOut` FILTERS RETURNED `UserInDB`; `hashed_password`
  NEVER LEAVES THE API ([Response Models](response-model.md)).
- `EmailStr` REQUIRES `email-validator` PACKAGE, INCLUDED IN
  `fastapi[standard]`.

H3: REDUCE DUPLICATION WITH INHERITANCE

`tutorial002_py310.py` DECLARES SHARED FIELDS ONCE:

```python
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
```

SAME PATTERN WITH SQLModel (`HeroBase`, `Hero`, `HeroCreate`, `HeroPublic`,
`HeroUpdate`) IN [SQL Databases](../integrations/SQL-databases.md).

H2: UNION RESPONSES (`anyOf`)

RESPONSE MAY USE ONE OF SEVERAL MODELS; OpenAPI DOCUMENTS THIS WITH `anyOf`
(`tutorial003_py310.py`):

```python
class BaseItem(BaseModel):
    description: str
    type: str


class CarItem(BaseItem):
    type: str = "car"


class PlaneItem(BaseItem):
    type: str = "plane"
    size: int


@app.get("/items/{item_id}", response_model=PlaneItem | CarItem)
async def read_item(item_id: str):
    return items[item_id]
```

PUT MOST SPECIFIC type FIRST (`PlaneItem` BEFORE `CarItem`); OTHERWISE,
PYDANTIC MAY MATCH LESS SPECIFIC MODEL FIRST.
`typing.Union[PlaneItem, CarItem]` IS EQUIVALENT.
`X | Y` FORM WORKS AS A VALUE HERE; FASTAPI REQUIRES Python 3.10+.

H2: LISTS AND DICTS

```python
@app.get("/items/", response_model=list[Item])
async def read_items():
    return items


@app.get("/keyword-weights/", response_model=dict[str, float])
async def read_keyword_weights():
    return {"foo": 2.3, "bar": 3.4}
```

`dict[str, float]` USEFUL WHEN FIELD NAMES ARE UNKNOWN IN ADVANCE.

H2: `jsonable_encoder`

SOMETIMES JSON-COMPATIBLE DATA IS NEEDED — `dict`, `list`, `str`, NUMBERS,
`None` — e.g., FOR STORAGE IN A JSON-ONLY DATABASE.
`fastapi.encoders.jsonable_encoder` CONVERTS PYDANTIC MODELS, DATACLASSES
AND OTHER TYPES (`docs_src/encoder/tutorial001_py310.py`):

```python
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

fake_db = {}


class Item(BaseModel):
    title: str
    timestamp: datetime
    description: str | None = None


app = FastAPI()


@app.put("/items/{id}")
def update_item(id: str, item: Item):
    json_compatible_item_data = jsonable_encoder(item)
    fake_db[id] = json_compatible_item_data
```

`Item` BECOMES A `dict`; `timestamp` BECOMES AN ISO-FORMAT `str`.
RETURNS PYTHON DATA STRUCTURES, NOT A JSON STRING; USE `json.dumps()` FOR
A JSON STRING.

BUILT-IN CONVERSIONS (`ENCODERS_BY_TYPE` IN `fastapi/encoders.py`):
- `datetime`/`date`/`time` → ISO STRING
- `timedelta` → TOTAL SECONDS (`float`)
- `Decimal` → `int` IF INTEGRAL; OTHERWISE `float`
- `Enum` → ITS VALUE
- `UUID` AND `Path` → `str`
- `bytes` → `str`
- SETS/TUPLES/GENERATORS → LISTS

PARAMETERS: `include`, `exclude`, `by_alias`, `exclude_unset`,
`exclude_defaults`, `exclude_none`, `custom_encoder` (A `{type: function}`
dict), AND `sqlalchemy_safe`.

FASTAPI USES `jsonable_encoder` INTERNALLY TO SERIALIZE RETURN VALUES WHEN
THERE IS NO RESPONSE MODEL.

H2: UPDATING DATA: `PUT` VS `PATCH`

H3: REPLACE WITH `PUT`

`PUT` REPLACES STORED DATA (`docs_src/body_updates/tutorial001_py310.py`):

```python
class Item(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    tax: float = 10.5
    tags: list[str] = []


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, item: Item):
    update_item_encoded = jsonable_encoder(item)
    items[item_id] = update_item_encoded
    return update_item_encoded
```

CAVEAT: SENDING `{"name": "Barz", "price": 3, "description": None}` FOR AN
Item STORED WITH `"tax": 20.2` RESETS `tax` TO THE MODEL DEFAULT `10.5`,
BECAUSE THE OMITTED FIELD TAKES ITS DEFAULT.

H3: PARTIAL update WITH `PATCH`
USE `model_dump(exclude_unset=True)` TO GET ONLY FIELDS CLIENT ACTUALLY SENT;
THEN `model_copy(update=...)` ON STORED MODEL (`tutorial002_py310.py`):

```python
@app.patch("/items/{item_id}")
async def update_item(item_id: str, item: Item) -> Item:
    stored_item_data = items[item_id]
    stored_item_model = Item(**stored_item_data)
    update_data = item.model_dump(exclude_unset=True)
    updated_item = stored_item_model.model_copy(update=update_data)
    items[item_id] = jsonable_encoder(updated_item)
    return updated_item
```

STEPS: LOAD STORED DATA → BUILD MODEL → DUMP ONLY SET INPUT FIELDS →
COPY WITH UPDATES → ENCODE AND SAVE → RETURN.

NOTES:

- SAME TECHNIQUE WORKS WITH `PUT`; MANY TEAMS USE ONLY `PUT`, EVEN FOR
  PARTIAL UPDATES.
- INPUT MODEL ABOVE HAS ALL-OPTIONAL FIELDS, SO PARTIAL BODIES VALIDATE.
  FOR CREATE VS update, SEPARATE update MODEL WITH OPTIONAL FIELDS
  (e.g., `HeroUpdate`) IS USUALLY CLEANER; KEEP REQUIRED FIELDS ON CREATE
  MODEL.
- `model_copy(update=...)` DOES NOT RE-VALIDATE update DATA; VALIDATE
  BEFORE IF NEEDED.

H2: RELATED

- [REQUEST BODY](../request/request-body.md)
- [RESPONSE MODELS AND RETURN TYPES](response-model.md)
- [SQL DATABASES WITH SQLModel](../integrations/SQL-databases.md) —
  `sqlmodel_update()` FOR PATCH
