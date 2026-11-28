- **Declaring the status code**
  - Pass `status_code` to a path operation decorator such as `@app.get()` or `@app.post()`. It is a decorator parameter, not a function parameter; it sets the response status and documents it in OpenAPI.
  - It accepts an `int` or an `IntEnum` such as Python’s `http.HTTPStatus`, normalized to `int`.
  - Use named constants from `fastapi.status` (re-exported from Starlette) for readability and autocompletion:
    ```python
    from fastapi import FastAPI, status
    @app.post("/items/", status_code=status.HTTP_201_CREATED)
    ```

- **Status code ranges**
  - `100–199`: informational; can’t have a body and are rarely used directly.
  - `200–299`: success; `200` OK (default), `201` Created, `204` No Content (no body).
  - `300–399`: redirection; `304` Not Modified must not have a body.
  - `400–499`: client error; `404` Not Found, `400` generic client error, `422` validation error.
  - `500–599`: server error; produced automatically for unhandled errors.
  - `is_body_allowed_for_status_code` identifies codes that forbid a body: below 200, `204`, `205`, `304`. FastAPI documents no response body and sends an empty body for these, even if the function returns something.
  - To return errors, **raise** `HTTPException` instead of choosing an error status here.

- **Additional status codes**
  - `status_code` declares the main status. To sometimes return another, directly return a `Response` such as `JSONResponse` with that status.
  - Example: an existing item returns `200` with the item; a new item returns `JSONResponse(status_code=status.HTTP_201_CREATED, content=item)`.
  - A directly returned response is not validated or filtered by any response model; serialize its content yourself. OpenAPI does not know about the extra status; document it with `responses={201: {...}}`.

- **Changing the status code per request**
  - Declare a `Response` parameter and set `response.status_code` to change the status dynamically while using the response model.
  - FastAPI injects a temporary `Response`; its `status_code` overrides the decorator’s `status_code` for that response (`_build_response_args` in `fastapi/routing.py`). The return value is still serialized through the response model. The same can be done inside dependencies; the object also sets headers and cookies.

- **Related:** Custom Responses; Path Operation Configuration.
