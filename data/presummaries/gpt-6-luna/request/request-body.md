- **Request body / basic body**
  - A request body is data the client sends, usually JSON, typically with `POST`, `PUT` or `PATCH`; declare it with a Pydantic model.
  - In `class Item(BaseModel)`, fields without defaults (`name: str`, `price: float`) are required; fields with defaults (`description: str | None = None`, `tax: float | None = None`) are optional.
  - FastAPI reads JSON when `Content-Type` is `application/json` (see [Strict Content-Type](using-request-directly.md)), converts types and validates, returns 422 for invalid data with error locations such as `["body", "price"]`, supplies an `Item` instance with editor completion, and generates its OpenAPI JSON Schema. Use `item.model_dump()` to get a dict; the example adds `price_with_tax` only if `item.tax is not None`.
  - A body with `GET` is undefined in the HTTP spec. FastAPI supports it for extreme cases, but Swagger UI won’t document it and proxies may drop it.

- **Body + path + query parameters**
  - FastAPI classifies parameters in this order: declared in the path → path parameter; singular types (`int`, `float`, `str`, `bool`, …) → query parameter; Pydantic model → request body. An endpoint may combine `item_id: int`, `item: Item` and `q: str | None = None`.

- **Multiple body parameters**
  - Optional body: `item: Item | None = None`. Path constraints can use `Annotated[int, Path(title="The ID of the item to get", ge=0, le=1000)]`.
  - With multiple body parameters, FastAPI expects a JSON object keyed by parameter names, e.g. `"item"` and `"user"`.
  - A plain `int` is a query parameter; use `importance: Annotated[int, Body()]` to read it from the body. `Body` accepts the same validation as `Query`/`Path`, e.g. `Body(gt=0)`, and has `media_type`, `examples` and `openapi_examples`.
  - A single model parameter normally means the body *is* the model. `Annotated[Item, Body(embed=True)]` instead requires a wrapping key, e.g. `{"item": {"name": "Foo", "price": 42.0, ...}}`.

- **Field validation and metadata: `Field()`**
  - Import `Field` from `pydantic`, not `fastapi`. It supports `default`, `title`, `description`, `examples`, `alias`, numeric constraints (`gt`, `ge`, `lt`, `le`) and string constraints (`min_length`, `max_length`, `pattern`); these appear in JSON Schema. FastAPI’s `Query`, `Path`, `Body`, etc. are built on Pydantic’s `FieldInfo`.

- **Nested models**
  - Models can contain `list[str]` or `set[str]`; sets remove duplicates and produce `uniqueItems` in schema. A field like `image: Image | None = None` nests an `Image` object (`url`, `name`). Validation, conversion and docs work at every level.
  - Use Pydantic types such as `HttpUrl` for validated strings and `list[Image]` for lists of submodels. Models can be deeply nested, e.g. `Offer` with `items: list[Item]`.
  - A top-level array is supported (`images: list[Image]`). Arbitrary-key dict bodies are supported (`weights: dict[int, float]`); JSON object keys are always strings, and Pydantic converts them to `int` and validates values as `float`.

- **Related**
  - [Response Models and Return Types](../models/response-model.md); [Extra Models and Body Updates](../models/extra-models-and-updates.md) — input/output models, PATCH; [Extra Data Types and Examples](extra-data-types-and-examples.md) — `datetime`, `UUID`, examples; [Forms and File Uploads](forms-and-files.md) — non-JSON bodies.
