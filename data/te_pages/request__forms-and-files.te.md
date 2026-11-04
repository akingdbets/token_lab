---
type: guide
title: Forms and File Uploads
description: Receive HTML form fields with Form(), uploaded files with File() as bytes or UploadFile, optional and multiple files, forms and files together, Pydantic form models (with extra='forbid'), and the python-multipart requirement.
tags: [forms, form, file-upload, file, UploadFile, multipart, python-multipart, form-models]
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

H1: Forms and File Uploads

FORMS/files USE FORM ENCODINGS, NOT JSON:
- `application/x-www-form-urlencoded`: PLAIN HTML FORMS; NO files.
- `multipart/form-data`: FORMS WITH files.

`Form()` OR `File()` DECLARATION → read data FROM FORM Body, NOT JSON OR
QUERY STRING.

REQUIREMENT: INSTALL `python-multipart` (INCLUDED IN `fastapi[standard]`):

```bash
uv add python-multipart
```

WITHOUT IT, DECLARING FORM/FILE PARAMETERS RAISES `RuntimeError` WITH
INSTALL INSTRUCTIONS (`ensure_multipart_is_installed()` IN
`fastapi/dependencies/utils.py`). INSTALLING UNRELATED `multipart` BY MISTAKE
ALSO PRODUCES A SPECIFIC ERROR.

H2: Form fields: `Form()`

`docs_src/request_forms/tutorial001_an_py310.py`:

```python
from typing import Annotated

from fastapi import FastAPI, Form

app = FastAPI()


@app.post("/login/")
async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    return {"username": username}
```

- `Form` SUBCLASS OF `Body`; SUPPORTS SAME VALIDATION/METADATA
  (`min_length`, `alias`, `examples`, …).
- WITHOUT `Form()`, `str` PARAMETERS ARE read as QUERY PARAMETERS.
- OAUTH2 "password flow" REQUIRES `username` AND `password` as FORM FIELDS;
  `OAuth2PasswordRequestForm` READS THEM
  ([Security Basics](../security/oauth2-password-flow.md)).

H2: files: `File()` and `UploadFile`

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

TWO OPTIONS:

| | `bytes` + `File()` | `UploadFile` |
|---|---|---|
| STORAGE | WHOLE CONTENT **IN MEMORY** | **SPOOLED** FILE: MEMORY UP TO A LIMIT, THEN DISK |
| GOOD FOR | SMALL files | LARGE files (IMAGES, VIDEOS, BINARIES) |
| METADATA | NONE | `filename`, `content_type`, `size`, `headers` |
| NEEDS `File()` | YES (ELSE QUERY/Body PARAM) | NO; type SUFFICES (`File()` ONLY FOR METADATA) |

`UploadFile` (SUBCLASS OF STARLETTE'S) HAS:

- ATTRIBUTES: `filename` (ORIGINAL name, e.g. `myimage.jpg`),
  `content_type` (e.g. `image/jpeg`), `size`, `headers`, AND `file`
  (UNDERLYING `SpooledTemporaryFile`; FILE-LIKE OBJECT FOR LIBRARIES THAT
  EXPECT ONE).
- `async` METHODS: `await file.read(size)`, `await file.write(data)`,
  `await file.seek(offset)` (e.g. `seek(0)` TO RE-read), `await file.close()`.

IN PLAIN `def` ENDPOINTS, USE SYNC FILE DIRECTLY:
`contents = file.file.read()`. UPLOADED files CLOSE AUTOMATICALLY AFTER THE
REQUEST (THROUGH FASTAPI'S EXIT-STACK MIDDLEWARE).

H3: Optional files and metadata

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

(`tutorial001_02_an_py310.py`.) ADD description WITH
`File(description="A file read as UploadFile")`
(`tutorial001_03_an_py310.py`).

H3: Multiple files

SEND SEVERAL files UNDER SAME FORM FIELD name (`tutorial002_an_py310.py`):

```python
@app.post("/files/")
async def create_files(files: Annotated[list[bytes], File()]):
    return {"file_sizes": [len(file) for file in files]}


@app.post("/uploadfiles/")
async def create_upload_files(files: list[UploadFile]):
    return {"filenames": [file.filename for file in files]}
```

MATCHING HTML USES `<input name="files" type="file" multiple>` INSIDE A FORM
WITH `enctype="multipart/form-data"`. WITH METADATA:
`Annotated[list[UploadFile], File(description="Multiple files as UploadFile")]`
(`tutorial003_an_py310.py`).

H2: Forms and files together

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
CANNOT MIX `Form`/`File` PARAMETERS WITH JSON `Body` PARAMETERS IN ONE OPERATION.
REQUEST Body: `multipart/form-data`, NOT `application/json`.
THIS IS HOW HTTP WORKS; NOT A FastAPI LIMITATION.
STRUCTURED data + FILE: SEND as FORM FIELDS, OR as JSON STRING IN FORM FIELD
THAT YOU PARSE YOURSELF.

H2: FORM MODELS

GROUP FORM FIELDS IN PYDANTIC MODEL; DECLARE WITH `Form()`
(`docs_src/request_form_models/tutorial001_an_py310.py`):

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

FastAPI READS EACH FIELD FROM FORM; VALIDATES MODEL.
TO REJECT UNEXPECTED FIELDS, FORBID EXTRAS (`tutorial002_an_py310.py`):

```python
class FormData(BaseModel):
    username: str
    password: str
    model_config = {"extra": "forbid"}
```

CLIENT SENDING extra FIELD (e.g. `extra=Mr. Poopybutthole`) GETS 422 ERROR,
type `extra_forbidden`.
SAME MODEL APPROACH EXISTS FOR [QUERY, HEADER AND COOKIE PARAMETERS](query-parameters.md).

H2: RELATED

- [REQUEST Body](request-body.md) — JSON BODIES
- [extra data TYPES](extra-data-types-and-examples.md) — base64 bytes IN JSON
  as ALTERNATIVE TO UPLOADS
- [CUSTOM RESPONSES](../responses/custom-responses.md) —
  `FileResponse` FOR DOWNLOADS
