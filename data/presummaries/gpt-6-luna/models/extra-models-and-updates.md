## Multiple models per entity

- Use separate models for different purposes: `UserIn` has the plain `password`, `UserOut` omits passwords, and `UserInDB` has `hashed_password`. Never return or store plain passwords.
- `user_in.model_dump()` returns a `dict`; `UserInDB(**user_dict, hashed_password=...)` unpacks it and adds a field, with Pydantic validating the new object.
- `response_model=UserOut` filters the returned `UserInDB`, so `hashed_password` never leaves the API. `EmailStr` requires `email-validator` (included in `fastapi[standard]`).
- Reduce duplication by putting shared fields in `UserBase` and inheriting it in `UserIn`, `UserOut` (`pass`), and `UserInDB`. SQLModel uses the same pattern (`HeroBase`, `Hero`, `HeroCreate`, `HeroPublic`, `HeroUpdate`).

## Union responses (`anyOf`)

- Responses can be one of several models; OpenAPI documents this with `anyOf`. Put the most specific type first (`PlaneItem` before `CarItem`) so Pydantic does not match the less specific model first.
- `typing.Union[PlaneItem, CarItem]` is equivalent to `PlaneItem | CarItem`; FastAPI requires Python 3.10+ for `X | Y` here.

## Lists and dicts

- Response models can be `list[Item]` or `dict[str, float]`. A dict is useful when field names are unknown in advance.

## `jsonable_encoder`

- `fastapi.encoders.jsonable_encoder` converts Pydantic models, dataclasses and other types into JSON-compatible Python data (`dict`, `list`, `str`, numbers, `None`), e.g. for JSON-only databases. A model becomes a `dict`; `datetime` becomes an ISO-format `str`. It returns Python data structures, not a JSON string; use `json.dumps()` for a string.
- `ENCODERS_BY_TYPE` conversions: `datetime`/`date`/`time` → ISO string; `timedelta` → total seconds (`float`); `Decimal` → `int` if integral, otherwise `float`; `Enum` → its value; `UUID`, `Path`, and `bytes` → `str`; sets/tuples/generators → lists.
- Parameters: `include`, `exclude`, `by_alias`, `exclude_unset`, `exclude_defaults`, `exclude_none`, `custom_encoder` (a `{type: function}` dict), `sqlalchemy_safe`. FastAPI uses it internally to serialize return values when there is no response model.

## Updating data: `PUT` vs `PATCH`

### Replace with `PUT`

- `PUT` replaces stored data. Omitted fields take model defaults: sending `{"name": "Barz", "price": 3, "description": None}` resets a stored `"tax": 20.2` to the default `10.5`.

### Partial update with `PATCH`

- Load stored data → build a model → use `item.model_dump(exclude_unset=True)` to get only fields actually sent → apply with `stored_item_model.model_copy(update=update_data)` → encode with `jsonable_encoder` and save → return.
- The same technique works with `PUT`; many teams use only `PUT`, even for partial updates. The input model has all-optional fields so partial bodies validate. For create vs update, a separate update model with optional fields (like `HeroUpdate`) and required fields on the create model is usually cleaner.
- `model_copy(update=...)` does **not** re-validate update data; validate first if needed.
