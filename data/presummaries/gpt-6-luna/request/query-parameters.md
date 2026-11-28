## Basics
- Function parameters that aren’t path parameters, Pydantic models, or special types are query parameters: the `?key=value&...` part of the URL. Values arrive as strings and are converted and validated according to their type.
- Path and query parameters are distinguished by name: names in the path template are path parameters; the rest are query parameters, in any order.
- `skip: int = 0` and `limit: int = 10` are optional defaults; `/items/?skip=20` gives `skip=20, limit=10`.
- A parameter without a default, such as `needy: str`, is required; omitting it gives a 422 `missing` error. `limit: int | None = None` is optional and is `None` if absent.
- `short: bool = False` accepts `1`, `True`, `true`, `on`, `yes` as `True`; `0`, `false`, `off`, `no` become `False`.

## `Query()`: validation and metadata
- Use `Query()` inside `Annotated` for validation. `Annotated` support was added in FastAPI 0.95.0 and is the recommended style.
- Older style: `q: str | None = Query(default=None, max_length=50)`. With `Annotated`, use a normal Python default; the function remains callable normally, and you can’t accidentally set two defaults.
- String constraints include `min_length`, `max_length`, and `pattern` (a regular expression); `regex=` is deprecated in favor of `pattern`. Numeric constraints `gt`, `ge`, `lt`, `le` are also available.
- A default makes a validated parameter optional; no default makes it required. `q: Annotated[str | None, Query(min_length=3)]` is required but may be `None`.
- For multiple values, declare a list type with `Query()` explicitly; without it, a `list` is interpreted as a request body. `/items/?q=foo&q=bar` yields `{"q": ["foo", "bar"]}`. A default list is supported. A bare `list` works, but items aren’t type-checked.
- `alias` sets the URL parameter name (for example, `alias="item-query"` uses `?item-query=...` while the variable can be `q`). `title` and `description` document it. `deprecated=True` keeps it working but marks it deprecated in the docs.
- `Query(include_in_schema=False)` hides a parameter from OpenAPI; it still works.

## Custom validation with `AfterValidator`
- Pydantic’s `AfterValidator` in `Annotated` runs after normal type validation. A `check_valid_id` validator can raise `ValueError`; this produces a normal 422 validation error. Pydantic also offers `BeforeValidator` and others.
- For checks requiring other resources, such as a database lookup, use a dependency instead.

## Query parameter models
- Declare a Pydantic model with `Query()` to group related query parameters. Each model field is a separate query parameter, validated via the model and documented individually; models can be reused across endpoints.
- Example fields: `limit: int = Field(100, gt=0, le=100)`, `offset: int = Field(0, ge=0)`, `order_by: Literal["created_at", "updated_at"] = "created_at"`, and `tags: list[str] = []`.
- Forbid unknown parameters with `model_config = {"extra": "forbid"}`; `?tool=plumbus` then returns a 422 `extra_forbidden` error.
