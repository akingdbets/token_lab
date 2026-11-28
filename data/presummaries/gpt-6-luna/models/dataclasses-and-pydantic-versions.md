## Dataclasses
- Standard-library `dataclasses` are accepted wherever Pydantic models are: request bodies, `response_model`, and return types. FastAPI converts them internally to Pydantic dataclasses, providing validation, serialization, and docs.
- Dataclasses lack some Pydantic features, such as advanced validators and config; use `BaseModel` when needed.
- If problems arise (for example, generated docs for nested dataclasses), use `from pydantic.dataclasses import dataclass`. `field` still comes from the stdlib. `list[Item]` is accepted as a body; `response_model` converts returned plain dicts. Dataclasses can be combined with, inherit from, and be nested in Pydantic models.

## Separate input and output schemas
- With Pydantic v2, a model may have two OpenAPI JSON Schemas. For `Item` with `description: str | None = None`, input does not require `description`, but output always includes it in JSON (possibly `null`), so it is marked required. OpenAPI names these `Item-Input` and `Item-Output`; this is more precise and produces better generated clients.
- To use one schema, for example when existing generated clients cannot yet be regenerated:
  ```python
  app = FastAPI(separate_input_output_schemas=False)
  ```
  This produces only `Item`, with `description` not required, as in Pydantic v1-era output. The flag is passed to `get_openapi(..., separate_input_output_schemas=...)`.

## Migrating from Pydantic v1 to v2
- Current FastAPI requires `pydantic>=2.9.0`. Support timeline:
  - FastAPI `0.100.0`: Pydantic v1 or v2, whichever is installed.
  - `0.119.0`: partial support for `pydantic.v1` models inside Pydantic v2.
  - `0.126.0`: Pydantic v1 dropped; `pydantic.v1` temporarily supported.
  - `0.128.0`: `pydantic.v1` dropped; v2 only.
- Current FastAPI raises `PydanticV1NotSupportedError` for `pydantic.v1` models. The Pydantic team does not support v1 (including `pydantic.v1`) on Python 3.14+.
- Migration order: have tests and run them in CI; read Pydantic’s official migration guide; run `bump-pydantic`; fix remaining issues and run tests. Common renames: `.dict()` → `.model_dump()`, `.json()` → `.model_dump_json()`, `.parse_obj()` → `.model_validate()`, `.copy(update=...)` → `.model_copy(update=...)`, `class Config` → `model_config = ConfigDict(...)` (or `SettingsConfigDict` for settings), `schema_extra` → `json_schema_extra`, `orm_mode` → `from_attributes`.
- On FastAPI `0.119–0.127` only, gradual migration could use Pydantic v2 alongside models imported from `pydantic.v1`. Separate v1 and v2 models could coexist, even in one path operation (for example, v1 input with `response_model=ItemV2`), but neither could contain fields of the other version. `fastapi.temp_pydantic_v1_params` provided v1 parameter functions (`Body`, `Query`, `Form`, …). These features do not exist currently; finish migration before upgrading past `0.127`.

## Related
- Response Models and Return Types; Extra Models, jsonable_encoder and Body Updates; Generating SDK Clients.
