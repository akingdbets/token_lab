- **Encoding and requirement**
  - Forms/files use `application/x-www-form-urlencoded` for plain HTML forms and `multipart/form-data` for forms with files. `Form()` and `File()` read from the form body, not JSON or the query string.
  - Install `python-multipart` (`uv add python-multipart`; included in `fastapi[standard]`). Otherwise declaring form/file parameters raises a `RuntimeError` with install instructions via `ensure_multipart_is_installed()` in `fastapi/dependencies/utils.py`; mistakenly installing the unrelated `multipart` package produces a specific error.

- **Form fields: `Form()`**
  - `Form` subclasses `Body` and supports the same validation and metadata, including `min_length`, `alias`, and `examples`. Without `Form()`, `str` parameters are query parameters.
  - The OAuth2 "password flow" requires `username` and `password` as form fields; `OAuth2PasswordRequestForm` reads them.

- **Files: `File()` and `UploadFile`**
  - `bytes` with `File()` loads whole content in memory; suited to small files and requires `File()` (otherwise it would be a query/body parameter). `UploadFile` uses a spooled file (memory up to a limit, then disk), suited to large files, and needs no `File()` unless adding metadata.
  - `UploadFile` (a subclass of Starlette's) has `filename`, `content_type`, `size`, `headers`, and `file` (underlying `SpooledTemporaryFile`). Async methods: `await file.read(size)`, `await file.write(data)`, `await file.seek(offset)` (use `seek(0)` to reread), and `await file.close()`. In a plain `def` endpoint use `file.file.read()`; uploads close automatically after the request through FastAPI's exit-stack middleware.
  - Files may be optional: `Annotated[bytes | None, File()] = None` or `UploadFile | None = None`. Add metadata with `File(description="A file read as UploadFile")`.
  - Multiple files use the same form field name: `Annotated[list[bytes], File()]` or `list[UploadFile]`. HTML uses `<input name="files" type="file" multiple>` in a form with `enctype="multipart/form-data"`. Metadata example: `Annotated[list[UploadFile], File(description="Multiple files as UploadFile")]`.

- **Forms and files together**
  - An operation can accept `File()` parameters and `Form()` fields together, but **can't mix** them with JSON `Body` parameters: the body is `multipart/form-data`, not `application/json`. This is how HTTP works, not a FastAPI limitation. Send structured data as form fields or as a JSON string in a form field and parse it yourself.

- **Form models**
  - Declare a Pydantic model with `Form()`: FastAPI reads each form field and validates the model. To reject unexpected fields, set `model_config = {"extra": "forbid"}`. An extra field (e.g. `extra=Mr. Poopybutthole`) yields a 422 error with type `extra_forbidden`. The same model approach exists for query, header, and cookie parameters.

- **Related**
  - Request Body: JSON bodies; Extra Data Types: base64 bytes in JSON as an alternative to uploads; Custom Responses: `FileResponse` for downloads.
