- **Streaming overview**
  - Streaming sends data as produced, without waiting for the full result; useful for AI/LLM output, logs, progress updates, large files, and long lists.
  - Write a generator path operation using `yield` instead of `return`. `response_class` and the return annotation determine the format:
    - JSON Lines: default response class; `application/jsonl`.
    - Raw text/bytes: `response_class=StreamingResponse` (or a subclass); no `Content-Type` by default, or the subclass’s `media_type`.
    - SSE: `response_class=EventSourceResponse`; `text/event-stream`.
  - `async def` generators use `AsyncIterable[T]`; plain `def` generators use `Iterable[T]` and are iterated in a threadpool.

- **JSON Lines**
  - One JSON object per newline, without array brackets or commas, so clients can process lines as they arrive.
  - With `AsyncIterable[Item]` or `Iterable[Item]`, FastAPI extracts `Item` as the stream item type and validates, filters, and serializes each yielded value with Pydantic, honoring `response_model_*` options. A bad item raises `ResponseValidationError`; the item schema appears in OpenAPI.
  - Without an annotation, items use `jsonable_encoder` + `json.dumps` instead (slower, no validation). The response is a `StreamingResponse` with `media_type="application/jsonl"`; headers set on an injected `Response` are copied to it.

- **Raw strings and bytes: `StreamingResponse`**
  - Each yielded chunk is passed through as-is. The annotation is only for your editor: FastAPI does not convert or validate chunks. You must encode them and add newlines if the client expects them.
  - For async generators, FastAPI yields control between chunks (`anyio.sleep(0)`) so client disconnects can cancel the stream.
  - Plain `StreamingResponse` sends no `Content-Type`. Subclass it with a `media_type` (e.g. `PNGStreamingResponse.media_type = "image/png"`). The `with` block closes the file after the generator finishes. Regular files are blocking, so a plain `def` generator in a threadpool is often appropriate; `FileResponse` is simpler for whole files on disk. You can also return `StreamingResponse(generator, media_type=...)`.

- **Server-Sent Events (SSE)**
  - SSE uses `text/event-stream`, supported by browsers through `EventSource` with automatic reconnection. Events are text blocks with `data`, `event`, `id`, and `retry` fields, separated by blank lines.
  - Import `EventSourceResponse` from `fastapi.sse`. Each yielded item becomes an event with JSON `data`; annotated items are validated. `def` + `Iterable[Item]` and unannotated variants also work.
  - `ServerSentEvent` fields: `data` is JSON-encoded (Pydantic models via `model_dump_json()`); `raw_data` is sent as-is and is mutually exclusive with `data`; `event` is a single-line type name for `addEventListener(name, ...)`; `id` is sent back as `Last-Event-ID`; `retry` is milliseconds; `comment` is a `:` line ignored by `EventSource` (e.g. pings). `ServerSentEvent` items skip stream-item validation, allowing mixed payload types.
  - On reconnect, read `Last-Event-ID` as a normal header parameter and resume from the next ID.
  - Any method works for SSE, including `POST` for MCP or chat-style streams with a request body. Browser `EventSource` only does `GET`; use `fetch()` streaming or an SSE client library for `POST`.
  - FastAPI sends a `: ping` comment every **15 seconds** when the generator is idle, and sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`.

- **Streaming, dependencies and background tasks**
  - `yield` dependencies with default request scope are torn down after the stream finishes, so a DB session can be used while streaming. If the resource is needed only briefly, close it early or use `Depends(scope="function")`.
