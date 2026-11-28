- **Extra data types**
  - Any Pydantic-supported type works in path/query/header/cookie parameters, bodies and responses, with the same conversion, validation and documentation as `int`, `float`, `str` and `bool`.
  - JSON representations: `uuid.UUID` → `str`; `datetime.datetime`, `datetime.date` and `datetime.time` → ISO 8601 `str`; `datetime.timedelta` → `float` total seconds (Pydantic can also use ISO 8601 durations); `frozenset` / `set` → list (requests are de-duplicated), with schema `uniqueItems`; `bytes` → `str` (schema format `binary`); `decimal.Decimal` is handled like `float`.
  - Pydantic types also include `EmailStr`, `HttpUrl` and constrained types. Values inside the function are real Python objects; responses are converted back to JSON.

- **Declaring request examples**
  - Examples appear in the docs UI and help clients. JSON Schema `examples` can be added to a model with `model_config = {"json_schema_extra": {"examples": [...]}}`; `json_schema_extra` can add any extra JSON Schema info, e.g. frontend metadata.
  - Per-field examples use `Field(examples=[...])`. Per-parameter `examples=[...]` is accepted by `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` and `File()`. Several examples can be passed, but Swagger UI currently shows only one example from JSON Schema `examples`.
  - `examples` is a list and the JSON Schema standard keyword, supported since OpenAPI 3.1.0 (FastAPI ≥ 0.99.0). The single `example` keyword still works but is deprecated; migrate to `examples`.
  - For multiple named Swagger UI examples on a specific path operation, use `openapi_examples` on `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` or `File()`. Keys identify examples; each value may have `summary`, Markdown `description`, `value` or `externalValue` (a URL; less widely supported). These go into the OpenAPI operation’s media-type `examples`, not JSON Schema, and Swagger UI shows a dropdown.
  - Rule of thumb: use `Field(examples=...)` / `json_schema_extra` for models; use `openapi_examples` for selectable examples for a specific endpoint.

- **Binary data in JSON: base64**
  - JSON only contains text, so raw bytes cannot be sent directly. If binary data must be included in JSON, encode it as base64; otherwise prefer file uploads and `FileResponse`, which are more efficient.
  - Pydantic model config: `val_json_bytes="base64"` decodes base64 strings from input JSON into `bytes` (`"aGVsbG8="` → `b"hello"`); `ser_json_bytes="base64"` encodes `bytes` as base64 in JSON output. A model can configure both; the docs show that `data` expects base64-encoded bytes.
