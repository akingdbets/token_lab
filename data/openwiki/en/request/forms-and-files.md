---
type: guide
title: Forms and File Uploads
description: Receive HTML form fields with Form(), uploaded files with File() as bytes or UploadFile, optional and multiple files, forms and files together, Pydantic form models (with extra='forbid'), and the python-multipart requirement.
tags: [forms, form, file-upload, file, uploadfile, multipart, python-multipart, form-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-30f75f37e4cff44858a70b51
    resource: repo://docs_src/request_files/tutorial001_02_an_py310.py
  - id: openwiki-source-d6fc03d20d6314347f8c1793
    resource: repo://docs_src/request_files/tutorial001_an_py310.py
  - id: openwiki-source-f5934841942cad5e2f042234
    resource: repo://docs_src/request_files/tutorial002_an_py310.py
  - id: openwiki-source-0fb536ad1f20aee0079c692c
    resource: repo://docs_src/request_form_models/tutorial001_an_py310.py
  - id: openwiki-source-96582d02d632e5376615deec
    resource: repo://docs_src/request_form_models/tutorial002_an_py310.py
  - id: openwiki-source-9d65f8547370c7652a89fe27
    resource: repo://docs_src/request_forms_and_files/tutorial001_an_py310.py
  - id: openwiki-source-dd7c5da8ded0b9d51d52943e
    resource: repo://docs_src/request_forms/tutorial001_an_py310.py
  - id: openwiki-source-70ae9d2239ca638ce58b6a47
    resource: repo://docs/en/docs/tutorial/request-files.md
  - id: openwiki-source-ddb2f257f5130c9dec25e7d6
    resource: repo://docs/en/docs/tutorial/request-forms.md
  - id: openwiki-source-9314293a530bc6d7c261690e
    resource: repo://fastapi/datastructures.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Forms and File Uploads

Forms and files are sent with form encodings, not JSON:

- `application/x-www-form-urlencoded` — plain HTML forms without files;
- `multipart/form-data` — forms that include files.

Declaring `Form()` or `File()` tells FastAPI to read the data from the form body instead of JSON or the query string.

**Requirement:** install `python-multipart` (included in `fastapi[standard]`):

```bash
uv add python-multipart
```

Without it, FastAPI raises a `RuntimeError` with install instructions when you declare form/file parameters (`ensure_multipart_is_installed()` in `fastapi/dependencies/utils.py`). Installing the unrelated `multipart` package by mistake produces a specific error too.

## Form fields: `Form()`

`docs_src/request_forms/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, Form

app = FastAPI()


@app.post("/login/")
async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    return {"username": username}
```

- `Form` is a subclass of `Body`, so it supports the same validation and metadata (`min_length`, `alias`, `examples`, …).
- Without `Form()`, `str` parameters would be read as query parameters.
- The OAuth2 "password flow" requires `username` and `password` as form fields — that's what `OAuth2PasswordRequestForm` reads ([Security Basics](../security/oauth2-password-flow.md)).

## Files: `File()` and `UploadFile`

`docs_src/request_files/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, File, UploadFile

app = FastAPI()


@app.post("/files/")
async def create_file(file: Annotated[bytes, File()]):
    return {"file_size": len(file)}


@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile):
    return {"filename": file.filename}
```

Two options:

| | `bytes` + `File()` | `UploadFile` |
|---|---|---|
| Storage | Whole content **in memory** | **Spooled** file: memory up to a limit, then disk |
| Good for | Small files | Large files (images, videos, binaries) |
| Metadata | none | `filename`, `content_type`, `size`, `headers` |
| Needs `File()` | yes (else it'd be a query/body param) | no — the type is enough (use `File()` only for metadata) |

`UploadFile` (a subclass of Starlette's) has:

- attributes: `filename` (original name, e.g. `myimage.jpg`), `content_type` (e.g. `image/jpeg`), `size`, `headers`, and `file` (the underlying `SpooledTemporaryFile`, a file-like object for libraries that expect one);
- `async` methods: `await file.read(size)`, `await file.write(data)`, `await file.seek(offset)` (e.g. `seek(0)` to re-read), `await file.close()`.

In a plain `def` endpoint you can use the sync file directly: `contents = file.file.read()`. Uploaded files are closed automatically after the request (through FastAPI's exit-stack middleware).

### Optional files and metadata

```python
@app.post("/files/")
async def create_file(file: Annotated[bytes | None, File()] = None):
    if not file:
        return {"message": "No file sent"}
    else:
        return {"file_size": len(file)}


@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile | None = None):
    if not file:
        return {"message": "No upload file sent"}
    else:
        return {"filename": file.filename}
```

(`tutorial001_02_an_py310.py`.) Add a description with `File(description="A file read as UploadFile")` (`tutorial001_03_an_py310.py`).

### Multiple files

Send several files under the same form field name (`tutorial002_an_py310.py`):

```python
@app.post("/files/")
async def create_files(files: Annotated[list[bytes], File()]):
    return {"file_sizes": [len(file) for file in files]}


@app.post("/uploadfiles/")
async def create_upload_files(files: list[UploadFile]):
    return {"filenames": [file.filename for file in files]}
```

The matching HTML uses `<input name="files" type="file" multiple>` inside a form with `enctype="multipart/form-data"`. With metadata: `Annotated[list[UploadFile], File(description="Multiple files as UploadFile")]` (`tutorial003_an_py310.py`).

## Forms and files together

`docs_src/request_forms_and_files/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile

app = FastAPI()


@app.post("/files/")
async def create_file(
    file: Annotated[bytes, File()],
    fileb: Annotated[UploadFile, File()],
    token: Annotated[str, Form()],
):
    return {
        "file_size": len(file),
        "token": token,
        "fileb_content_type": fileb.content_type,
    }
```

**You can't mix** `Form`/`File` parameters with JSON `Body` parameters in one operation: the request body is `multipart/form-data`, not `application/json`. That's how HTTP works, not a FastAPI limitation. If you need structured data alongside a file, send it as form fields (or a JSON string in a form field you parse yourself).

## Form models

Group form fields in a Pydantic model and declare it with `Form()` (`docs_src/request_form_models/tutorial001_an_py310.py`):

```python
from typing import Annotated

from fastapi import FastAPI, Form
from pydantic import BaseModel

app = FastAPI()


class FormData(BaseModel):
    username: str
    password: str


@app.post("/login/")
async def login(data: Annotated[FormData, Form()]):
    return data
```

FastAPI reads each field from the form and validates the model. To reject unexpected fields, forbid extras (`tutorial002_an_py310.py`):

```python
class FormData(BaseModel):
    username: str
    password: str
    model_config = {"extra": "forbid"}
```

A client sending an extra field (e.g. `extra=Mr. Poopybutthole`) gets a 422 error with type `extra_forbidden`. The same model approach exists for [query, header and cookie parameters](query-parameters.md).

## Related

- [Request Body](request-body.md) — JSON bodies
- [Extra Data Types](extra-data-types-and-examples.md) — base64 bytes in JSON as an alternative to uploads
- [Custom Responses](../responses/custom-responses.md) — `FileResponse` for downloads
