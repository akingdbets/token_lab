# Files

- [Deployment Concepts, Servers and Workers](deployment-concepts-and-servers.md) - The concepts every FastAPI deployment must address (HTTPS, startup, restarts, replication, memory, pre-start steps, resource use), running with fastapi run or Uvicorn, multiple worker processes, and pinning FastAPI versions.
- [Deploying with Docker](docker.md) - Build a container image for a FastAPI app with a cache-friendly Dockerfile, run it with fastapi run in exec-form CMD, enable proxy headers behind a TLS proxy, and decide between one process per container or multiple workers.
- [HTTPS, TLS Termination and Cloud Providers](https-and-cloud.md) - How HTTPS works from a developer's perspective (certificates, TLS, SNI, TLS termination proxies, Let's Encrypt renewal, forwarded headers) and deploying FastAPI to FastAPI Cloud with fastapi deploy or to other cloud providers.
