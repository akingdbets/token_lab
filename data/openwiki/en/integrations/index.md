# Files

- [Background Tasks](background-tasks.md) - Run work after the response is sent using a BackgroundTasks parameter and add_task, add tasks from dependencies, how tasks attach to returned responses, and when to use a real task queue like Celery instead.
- [GraphQL and OpenTelemetry Integrations](graphql-and-opentelemetry.md) - Add a GraphQL endpoint with Strawberry's GraphQLRouter (or other ASGI GraphQL libraries), and use FastAPI's built-in OpenTelemetry support for traces, metrics and logs via OTLP environment variables or the telemetry= configuration dict.
- [SQL Databases with SQLModel](sql-databases.md) - Connect FastAPI to a SQL database with SQLModel — engine, per-request Session dependency with yield, table creation, CRUD endpoints, and the HeroBase/Hero/HeroPublic/HeroCreate/HeroUpdate multiple-model pattern with PATCH updates.
- [WebSockets](websockets.md) - Build WebSocket endpoints with @app.websocket and the WebSocket class, send and receive text/bytes/JSON, use Depends, Query, Cookie and other parameters, reject connections with WebSocketException, handle WebSocketDisconnect and broadcast to multiple clients.
