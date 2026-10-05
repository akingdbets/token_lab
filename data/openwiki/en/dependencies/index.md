# Files

- [Advanced Dependencies](advanced-dependencies.md) - Parameterized dependencies using callable class instances, the Depends(use_cache, scope) options, and how the timing of exit code in dependencies with yield has changed across FastAPI versions (StreamingResponse, except, background tasks).
- [Dependencies in Decorators, Routers and Globally](decorator-and-global-dependencies.md) - Run dependencies whose return values you don't need via dependencies=[Depends(...)] on a path operation decorator, an APIRouter, include_router(), or the whole FastAPI app, and how they are ordered.
- [Dependencies with yield](dependencies-with-yield.md) - Write setup/teardown dependencies with yield (DB sessions, connections), handle and re-raise exceptions correctly, understand execution order and the request vs function scope, and use context managers inside dependencies.
- [Dependency Injection Basics, Classes and Sub-dependencies](dependency-injection-basics.md) - Declare dependencies with Depends() and Annotated, share them with type aliases, use classes as dependencies (including the Depends() shortcut), build sub-dependency graphs, and control per-request caching with use_cache.
