## Middleware
- Runs for every request before the path operation and every response before it is returned. Useful for timing, logging, compression, host checks, CORS, and request IDs.

## Writing HTTP middleware
- Decorate an `async` function with `@app.middleware("http")`. It receives `request: Request` and `call_next`; `call_next(request)` passes the request to the rest of the app and returns the response.
- Run code before `call_next` to inspect/modify the request or return a response early; run code after it to modify the response.
- Custom headers conventionally use an `X-` prefix. Browser JS needs them listed in CORS `expose_headers` to read them cross-origin. `time.perf_counter()` is more precise than `time.time()` for durations.
- Exit code of `yield` dependencies runs after middleware; background tasks run after all middleware.
- `@app.middleware("http")` uses Starlette's `BaseHTTPMiddleware`. For high-performance or streaming-sensitive middleware, use a pure ASGI middleware class.

## Adding ASGI middleware classes
- Any ASGI middleware works; it need not be written for FastAPI. ASGI middleware classes take the app as their first argument. In FastAPI, use `app.add_middleware(UnicornMiddleware, some_config="rainbow")` to retain FastAPI exception handling and middleware stack. You can also pass `middleware=[Middleware(...)]` to `FastAPI(...)`.

## Execution order
- Each added middleware wraps the app built so far; the last added is outermost. For `MiddlewareA` then `MiddlewareB`: request `MiddlewareB → MiddlewareA → route`; response `route → MiddlewareA → MiddlewareB`. Applies to `@app.middleware()` and `add_middleware()`.
- Middleware is outside FastAPI exception handlers (sees their 404, 422, and custom-handler responses) and inside `ServerErrorMiddleware`, which turns unhandled exceptions into 500 responses.

## Built-in middleware
- FastAPI re-exports common Starlette middleware in `fastapi.middleware`.
- `HTTPSRedirectMiddleware` (`fastapi.middleware.httpsredirect`): redirects `http` to `https` and `ws` to `wss`. Behind a TLS termination proxy, trust forwarded headers (`--forwarded-allow-ips` / `--proxy-headers`) or requests appear as `http` and redirect in a loop; often the proxy handles redirects.
- `TrustedHostMiddleware` (`fastapi.middleware.trustedhost`): rejects disallowed `Host` headers with `400`. `allowed_hosts` accepts hostnames and wildcards such as `*.example.com`; `["*"]` or omitting the middleware allows any. `www_redirect` redirects non-www requests to the `www.` version of an allowed host; default `True`.
- `GZipMiddleware` (`fastapi.middleware.gzip`): compresses responses for clients sending `gzip` in `Accept-Encoding`. `minimum_size` skips responses smaller than the byte count; default `500`. `compresslevel` ranges 1 (fast, larger) to 9 (slow, smaller); default `9`.
- `CORSMiddleware`: see CORS. `fastapi.middleware.wsgi.WSGIMiddleware` is deprecated; use `a2wsgi`. Other examples include Uvicorn's `ProxyHeadersMiddleware` and MessagePack (`msgpack-asgi`); see Starlette middleware docs and the “awesome-asgi” list.

## Middleware vs dependencies
- Middleware applies to every request, including 404s, static files, and docs, and works on raw requests/responses. Dependencies apply to path operations, integrate with validation and OpenAPI, and can be scoped to a router or route.
- For per-route request/response customization with full FastAPI integration, use custom `APIRoute` classes.
