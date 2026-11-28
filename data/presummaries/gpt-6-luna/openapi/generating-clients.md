- **Generating SDK Clients**
  - FastAPI publishes an OpenAPI schema that can generate client libraries (SDKs) with autocompletion for methods, request payloads, and responses; build-time errors can reveal API changes.
  - Generators: OpenAPI Generator supports many languages; Hey API (`@hey-api/openapi-ts`) is for TypeScript; more are listed on OpenAPI.Tools under SDK generators. FastAPI emits **OpenAPI 3.1**, so the generator must support 3.1.

- **Make the schema client-friendly**
  - Declare request bodies and responses with models so generators know their types. `Item` and `ResponseMessage` appear as schemas in `/openapi.json` and become client types.
  - Example: `Item(BaseModel)` has `name: str` and `price: float`; `ResponseMessage(BaseModel)` has `message: str`. `create_item` uses `@app.post("/items/", response_model=ResponseMessage)` and accepts `item: Item`; `get_items` uses `@app.get("/items/", response_model=list[Item])`.

- **Generate a TypeScript client**
  - With the app running: `npx @hey-api/openapi-ts -i http://localhost:8000/openapi.json -o src/client`.

- **Group with tags**
  - Tags let generators split the client into services. Operations tagged `items` and `users` produce, for example, `ItemsService` and `UsersService`.

- **Clean method names**
  - Generators name methods from each operation’s **operation ID**. FastAPI’s default ID combines function name, path, and method to guarantee uniqueness (example: `create_item_items__post`); a generated call can be `ItemsService.createItemItemsPost({name: "Plumbus", price: 5})`.
  - **Custom `generate_unique_id_function`:** FastAPI uses one unique ID per path operation for the operation ID and generated request/response model names. It takes an `APIRoute` and returns a string. Example: `def custom_generate_unique_id(route: APIRoute): return f"{route.tags[0]}-{route.name}"`, configured with `FastAPI(generate_unique_id_function=custom_generate_unique_id)`. IDs then look like `items-create_item`.
  - You must guarantee uniqueness yourself: every operation needs at least one tag (or `route.tags[0]` fails), and function names must be unique per tag. Set the parameter on `APIRouter` or in `include_router()` too; decorator `operation_id=` overrides it.

- **Preprocess the schema for the generator**
  - Since clients already group by tag, the `items-` prefix is redundant (example result `ItemsService.itemsCreateItem`). Download `openapi.json`; for each path operation, take `operation["tags"][0]`, remove `f"{tag}-"` from its `operationId`, and write the JSON back. A JavaScript version is in `docs_src/generate_clients/tutorial004.js`.
  - Generate with `npx @hey-api/openapi-ts -i ./openapi.json -o src/client`; result: `ItemsService.createItem({name: "Plumbus", price: 5})`.

- **Tips and related**
  - Regenerate whenever the backend changes (e.g. in CI or a package script); type errors reveal mismatches early.
  - Existing clients broken by `Item-Input` / `Item-Output` schemas: see `separate_input_output_schemas` in Dataclasses, Separate OpenAPI Schemas and Pydantic v1 to v2. The Full Stack FastAPI Template includes an automatically generated frontend client.
  - Related: Extending OpenAPI; API Metadata and Docs UIs.
