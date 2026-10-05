---
type: guide
title: 폼 데이터와 파일 업로드
description: python-multipart 설치 후 Form()으로 폼 필드 받기, Pydantic 폼 모델과 extra="forbid", File()로 bytes 받기와 UploadFile(filename, content_type, file, async read/write/seek/close), 선택적·다중 파일 업로드, 폼과 파일을 함께 받는 방법, JSON Body와 섞을 수 없는 이유를 설명한다.
tags: [forms, file-upload, uploadfile, multipart, python-multipart, form-models]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-03T04:04:39.409Z
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
  - id: openwiki-source-d63d1037ec8b7a9207062f9d
    resource: repo://docs/en/docs/tutorial/request-form-models.md
  - id: openwiki-source-347a202fba06a2bc8c842096
    resource: repo://docs/en/docs/tutorial/request-forms-and-files.md
  - id: openwiki-source-9314293a530bc6d7c261690e
    resource: repo://fastapi/datastructures.py
  - id: openwiki-source-e9da4f4f8b86e8868bdad790
    resource: repo://fastapi/dependencies/utils.py
  - id: openwiki-source-0e9a2a0518ebbbeae0aa9f66
    resource: repo://fastapi/params.py
generated: { by: "claude-code", at: "2026-10-03T04:04:39.409Z" }
---

# 폼 데이터와 파일 업로드

JSON 대신 **폼 필드**나 **파일**을 받아야 할 때 `Form`, `File`, `UploadFile`을 쓴다.

## 사전 요구사항: python-multipart

폼과 파일 업로드에는 [`python-multipart`](https://github.com/Kludex/python-multipart)가 필요하다(`fastapi[standard]`에 포함).

```console
$ uv add python-multipart
```

설치되지 않았거나 이름이 같은 다른 `multipart` 패키지가 설치되어 있으면, `Form`/`File` 파라미터를 가진 경로 작업을 정의할 때 FastAPI가 설치 방법을 안내하는 `RuntimeError`를 발생시킨다.

## 폼 필드: Form

```Python
from typing import Annotated

from fastapi import FastAPI, Form

app = FastAPI()


@app.post("/login/")
async def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    return {"username": username}
```

- `Body`, `Query`처럼 검증·예제·별칭(예: `user-name`) 등 같은 설정을 쓸 수 있다. `Form`은 `Body`를 상속한 클래스다.
- `Form`을 명시해야 한다. 그렇지 않으면 쿼리 파라미터나 JSON 본문으로 해석된다.
- 예: OAuth2 "password flow" 명세는 `username`과 `password`를 **JSON이 아닌 폼 필드**로 보내도록 요구한다([OAuth2 비밀번호 흐름](../security/oauth2-password-flow.md)).

### 인코딩

- 파일이 없는 폼: `application/x-www-form-urlencoded`
- 파일이 포함된 폼: `multipart/form-data`

자세한 내용은 [MDN의 POST 문서](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST)를 참고한다.

> 하나의 경로 작업에 `Form`(및 `File`) 파라미터를 여러 개 선언할 수 있지만, **JSON으로 받을 `Body` 필드는 함께 선언할 수 없다**. 요청 본문이 `application/json`이 아니라 폼 인코딩이기 때문이다. 이는 FastAPI가 아니라 HTTP 프로토콜의 제약이다.

## 폼 모델

Pydantic 모델로 폼 필드를 묶을 수 있다(FastAPI 0.113.0+).

```Python
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

FastAPI가 요청의 폼 데이터에서 **각 필드**를 추출해 정의한 모델을 만들어 준다. `/docs`에도 각 폼 필드가 표시된다.

### 추가 폼 필드 금지

드물지만 모델에 선언된 필드 외의 폼 필드를 **금지**하려면 `extra="forbid"`를 쓴다(FastAPI 0.114.0+).

```Python
class FormData(BaseModel):
    username: str
    password: str
    model_config = {"extra": "forbid"}
```

`extra` 필드를 보내면 오류가 반환된다.

```JSON
{
    "detail": [
        {
            "type": "extra_forbidden",
            "loc": ["body", "extra"],
            "msg": "Extra inputs are not permitted",
            "input": "Mr. Poopybutthole"
        }
    ]
}
```

같은 방식의 쿼리·헤더·쿠키 모델은 [쿼리 파라미터](./query-parameters.md), [헤더와 쿠키](./headers-and-cookies.md)를 참고한다.

## 파일 업로드: File과 UploadFile

```Python
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

`File`은 `Form`을 상속한 클래스다. `File`을 명시해야 쿼리 파라미터나 JSON 본문으로 해석되지 않는다. 파일은 "폼 데이터"로 업로드된다.

### bytes

타입을 `bytes`로 선언하면 FastAPI가 파일을 읽어 내용을 `bytes`로 준다. **전체 내용이 메모리에 저장**되므로 작은 파일에 적합하다.

### UploadFile

`UploadFile`은 `bytes`보다 여러 장점이 있다.

- 기본값에 `File()`을 쓸 필요가 없다.
- "스풀(spooled)" 파일을 사용한다. 일정 크기까지는 메모리에, 넘으면 디스크에 저장되어 이미지·동영상 같은 큰 파일도 메모리를 다 쓰지 않고 처리한다.
- 업로드된 파일의 메타데이터를 얻을 수 있다.
- [file-like](https://docs.python.org/3/glossary.html#term-file-like-object) `async` 인터페이스를 가진다.
- 실제 Python [`SpooledTemporaryFile`](https://docs.python.org/3/library/tempfile.html#tempfile.SpooledTemporaryFile) 객체를 노출하므로 file-like 객체를 기대하는 다른 라이브러리에 바로 넘길 수 있다.

속성:

| 속성 | 설명 |
| --- | --- |
| `filename` | 업로드된 원래 파일 이름(`str`, 예: `myimage.jpg`) |
| `content_type` | 콘텐츠 타입(MIME, 예: `image/jpeg`) |
| `file` | `SpooledTemporaryFile` — 실제 Python 파일 객체 |
| `size`, `headers` | 크기(바이트), 업로드 파트의 헤더(Starlette 제공) |

`async` 메서드(내부 `SpooledTemporaryFile`의 메서드를 스레드풀에서 실행):

- `write(data)`: `str` 또는 `bytes` 쓰기
- `read(size)`: `size`(`int`) 바이트/문자 읽기
- `seek(offset)`: `offset` 바이트 위치로 이동. 예: `await myfile.seek(0)`은 처음으로 이동하며, 한 번 `await myfile.read()`한 뒤 다시 읽을 때 유용하다.
- `close()`: 파일 닫기

```Python
# async def 경로 작업 안에서
contents = await myfile.read()

# 일반 def 경로 작업 안에서
contents = myfile.file.read()
```

FastAPI의 `UploadFile`은 Starlette의 `UploadFile`을 상속하고 Pydantic 및 FastAPI 다른 부분과 호환되도록 일부를 추가한 것이다. 폼으로 받은 업로드 파일은 요청 처리가 끝나면 FastAPI가 자동으로 닫는다([요청 처리 흐름](../internals/request-lifecycle.md)).

### 선택적 파일

기본값 `None`과 함께 선언한다.

```Python
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

### 추가 메타데이터

`UploadFile`과 함께 `File()`을 써서 설명 등을 추가할 수 있다.

```Python
@app.post("/files/")
async def create_file(file: Annotated[bytes, File(description="A file read as bytes")]):
    return {"file_size": len(file)}


@app.post("/uploadfile/")
async def create_upload_file(
    file: Annotated[UploadFile, File(description="A file read as UploadFile")],
):
    return {"filename": file.filename}
```

## 여러 파일 업로드

같은 "폼 필드"에 여러 파일을 보내려면 `list[bytes]` 또는 `list[UploadFile]`로 선언한다.

```Python
from typing import Annotated

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.post("/files/")
async def create_files(files: Annotated[list[bytes], File()]):
    return {"file_sizes": [len(file) for file in files]}


@app.post("/uploadfiles/")
async def create_upload_files(files: list[UploadFile]):
    return {"filenames": [file.filename for file in files]}


@app.get("/")
async def main():
    content = """
<body>
<form action="/files/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
<form action="/uploadfiles/" enctype="multipart/form-data" method="post">
<input name="files" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)
```

메타데이터도 `Annotated[list[UploadFile], File(description="Multiple files as UploadFile")]`처럼 추가할 수 있다.

## 폼과 파일 함께 받기

```Python
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

파일과 폼 필드가 폼 데이터로 업로드되고, FastAPI가 각각을 받는다. 이 경우에도 JSON `Body` 필드는 함께 선언할 수 없다(`multipart/form-data`로 인코딩되므로).

## 관련 페이지

- [요청 본문](./request-body.md)
- [OAuth2 비밀번호 흐름](../security/oauth2-password-flow.md) — `OAuth2PasswordRequestForm`
- [JSON의 base64 bytes](./nested-models-and-data-types.md)
- [응답 직접 반환](../responses/custom-responses.md) — 파일 다운로드는 `FileResponse`
