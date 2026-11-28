## Declaring path parameters
- Use Python format-string syntax, e.g. `"/items/{item_id}"`; the value is passed to the same-named function argument. `GET /items/foo` returns `{"item_id": "foo"}`.

## Types: conversion and validation
- Annotating `item_id: int` converts `GET /items/3` to `{"item_id": 3}`.
- `/items/foo` and `/items/4.2` return **422**, type `int_parsing`, `loc: ["path", "item_id"]`, and a readable message. The type appears in OpenAPI and the docs UI.
- Pydantic performs conversion and validation; any Pydantic type works, including `str`, `float`, `bool`, and `UUID`.

## Route order matters
- Path operations match in declaration order: put fixed paths such as `/users/me` before `/users/{user_id}`, or `"me"` is captured as `user_id`. For a duplicate path and method, only the first definition is used.

## Predefined values with `Enum`
- Subclass `str` and `Enum` (e.g. `ModelName`) to restrict values. `str` makes docs show string values; the docs UI shows a dropdown, and other values return **422**.
- Compare members with `is ModelName.alexnet` or use `.value`. Returning an enum member serializes to its value.

## Paths inside path parameters
- Use Starlette’s `:path` converter, e.g. `"/files/{file_path:path}"`, to capture slashes. `/files/home/johndoe/myfile.txt` gives `file_path="home/johndoe/myfile.txt"`; a value starting with `/` requires a double slash, e.g. `/files//home/johndoe/myfile.txt`. OpenAPI cannot represent path-containing parameters, so docs do not hint at this behavior.

## `Path()`: metadata and numeric validation
- Use `Path` with `Annotated`, e.g. `item_id: Annotated[int, Path(title="The ID of the item to get")]`. Path parameters are always required: `Path` rejects defaults (`"Path parameters cannot have a default value"`), and FastAPI also refuses them.
- Numeric constraints: `gt` (greater than), `ge` (greater than or equal), `lt` (less than), `le` (less than or equal). Examples: `ge=1`; `gt=0, le=1000`. Constraints also work for `float`, e.g. `Query(gt=0, lt=10.5)`.
- The same constraints are available on `Query`, `Header`, `Cookie`, `Body`, and Pydantic’s `Field`. Other `Path` parameters include `title`, `description`, `examples`, `openapi_examples`, `deprecated`, `include_in_schema`, and string constraints `min_length`, `max_length`, `pattern`.

## Parameter ordering
- FastAPI identifies parameters by **name, type and default**, not position. With `Annotated`, required parameters without defaults can follow defaulted parameters. With older `item_id: int = Path(...)` style, Python forbids non-default arguments after defaults; starting the signature with `*` makes parameters keyword-only. `Annotated` avoids this issue.
- `Path`, `Query`, and friends imported from `fastapi` are functions returning instances of classes in `fastapi.params`, typed to avoid editor complaints.
