---
type: guide
title: Extra Models, jsonable_encoder and Body Updates
description: Use separate input, output and database models (UserIn/UserOut/UserInDB) with inheritance, declare Union, list and dict responses, convert data with jsonable_encoder, and implement PUT replacement and PATCH partial updates with model_dump(exclude_unset=True) and model_copy(update=...).
tags: [models, pydantic, inheritance, union, jsonable_encoder, put, patch, partial-update, exclude_unset]
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

# Extra Models, jsonable_encoder and Body Updates

## Multiple models per entity

An entity often needs different shapes in different places. For a user:

- **input** model with the plain password;
- **output** model without any password;
- **database** model with the hashed password.

Never return or store plain passwords. `docs_src/extra_models/tutorial001_py310.py`:

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

Key idioms:

- `user_in.model_dump()` returns a `dict` of the model's data.
- `UserInDB(**user_dict, hashed_password=...)` unpacks that dict as keyword arguments and adds an extra field. Pydantic validates the new object.
- `response_model=UserOut` filters the returned `UserInDB` so `hashed_password` never leaves the API ([Response Models](response-model.md)).
- `EmailStr` requires the `email-validator` package (in `fastapi[standard]`).

### Reduce duplication with inheritance

`tutorial002_py310.py` declares shared fields once:

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

The same pattern appears with SQLModel (`HeroBase`, `Hero`, `HeroCreate`, `HeroPublic`, `HeroUpdate`) in [SQL Databases](../integrations/sql-databases.md).

## Union responses (`anyOf`)

A response may be one of several models; OpenAPI documents it with `anyOf` (`tutorial003_py310.py`):

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

Put the **most specific** type first (`PlaneItem` before `CarItem`), so Pydantic doesn't match the less specific model first. `typing.Union[PlaneItem, CarItem]` is equivalent; the `X | Y` form works as a value here because FastAPI requires Python 3.10+.

## Lists and dicts

```python
@app.get("/items/", response_model=list[Item])
async def read_items():
    return items


@app.get("/keyword-weights/", response_model=dict[str, float])
async def read_keyword_weights():
    return {"foo": 2.3, "bar": 3.4}
```

`dict[str, float]` is useful when field names aren't known in advance.

## `jsonable_encoder`

Sometimes you need JSON-compatible data — `dict`, `list`, `str`, numbers, `None` — e.g. to store in a JSON-only database. `fastapi.encoders.jsonable_encoder` converts Pydantic models, dataclasses and other types (`docs_src/encoder/tutorial001_py310.py`):

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

The `Item` becomes a `dict` and `timestamp` an ISO-format `str`. It returns Python data structures, **not** a JSON string (use `json.dumps()` for that).

Built-in conversions (`ENCODERS_BY_TYPE` in `fastapi/encoders.py`) include: `datetime`/`date`/`time` → ISO string, `timedelta` → total seconds (`float`), `Decimal` → `int` if integral else `float`, `Enum` → its value, `UUID` and `Path` → `str`, `bytes` → `str`, sets/tuples/generators → lists. Parameters: `include`, `exclude`, `by_alias`, `exclude_unset`, `exclude_defaults`, `exclude_none`, `custom_encoder` (a `{type: function}` dict) and `sqlalchemy_safe`.

FastAPI uses `jsonable_encoder` internally to serialize return values when there is no response model.

## Updating data: `PUT` vs `PATCH`

### Replace with `PUT`

`PUT` **replaces** the stored data (`docs_src/body_updates/tutorial001_py310.py`):

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

Caveat: sending `{"name": "Barz", "price": 3, "description": None}` for an item stored with `"tax": 20.2` resets `tax` to the model default `10.5`, because the omitted field takes its default.

### Partial update with `PATCH`

Use `model_dump(exclude_unset=True)` to get only fields the client **actually sent**, then `model_copy(update=...)` on the stored model (`tutorial002_py310.py`):

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

Steps: load stored data → build a model → dump only set fields from the input → copy with updates → encode and save → return.

Notes:

- The same technique works with `PUT`; many teams use only `PUT`, even for partial updates.
- The input model above has all-optional fields so partial bodies validate. For create vs update, it's usually cleaner to have a separate update model with optional fields (like `HeroUpdate`) and keep required fields on the create model.
- `model_copy(update=...)` does **not** re-validate the update data; validate before if needed.

## Related

- [Request Body](../request/request-body.md)
- [Response Models and Return Types](response-model.md)
- [SQL Databases with SQLModel](../integrations/sql-databases.md) — `sqlmodel_update()` for PATCH
