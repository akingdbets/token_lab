---
type: guide
title: Deploying with Docker
description: Build a container image for a FastAPI app with a cache-friendly Dockerfile, run it with fastapi run in exec-form CMD, enable proxy headers behind a TLS proxy, and decide between one process per container or multiple workers.
tags: [docker, containers, dockerfile, deployment, kubernetes, workers, proxy-headers]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-ed6347a02d439d7adb60c660
    resource: repo://docs/en/docs/deployment/docker.md
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Deploying with Docker

Containers (usually Docker images) package your app with its Python runtime and dependencies, giving reproducible, isolated deployments. They are the most common way to deploy FastAPI. Concepts referenced here are explained in [Deployment Concepts, Servers and Workers](deployment-concepts-and-servers.md).

A container runs **one main process** (the `CMD`); the container lives as long as that process does.

## Project layout

```
.
├── app
│   ├── __init__.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```

`requirements.txt` lists the pinned dependencies installed with `pip` inside the image. If you manage the project with `uv` (`uv add "fastapi[standard]" pydantic`, versions locked in `uv.lock`), export it for the container build and regenerate it whenever `uv.lock` changes:

```bash
uv export --format requirements-txt --no-dev --no-emit-project --output-file requirements.txt
```

## The Dockerfile

```Dockerfile
FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["fastapi", "run", "app/main.py", "--port", "80"]

# If running behind a proxy like Nginx or Traefik add --proxy-headers
# CMD ["fastapi", "run", "app/main.py", "--port", "80", "--proxy-headers"]
```

Step by step:

1. Start from the official Python base image.
2. Set `/code` as the working directory.
3. Copy **only** `requirements.txt` first.
4. Install dependencies (`--no-cache-dir` keeps the image smaller).
5. Copy the application code.
6. Start the production server with `fastapi run` (which uses Uvicorn).

### Why copy requirements first (layer cache)

Docker caches each instruction as a layer and reuses it if the inputs didn't change. Dependencies change rarely; code changes often. Copying `requirements.txt` and installing **before** copying `./app` means a code change only rebuilds the last layers, instead of reinstalling every package — saving minutes per build.

### Always use the exec form of `CMD`

```Dockerfile
# ✅ Do this
CMD ["fastapi", "run", "app/main.py", "--port", "80"]

# ⛔️ Don't do this
CMD fastapi run app/main.py --port 80
```

The shell form wraps the server in `/bin/sh`, which doesn't forward signals. With the exec form, FastAPI receives the stop signal, shuts down gracefully and runs the shutdown part of [lifespan events](../app-structure/lifespan-events.md). (With the shell form you'll notice, e.g., `docker compose` taking ~10 seconds to stop services.)

### Behind a TLS termination proxy

If a proxy (Nginx, Traefik, a cloud load balancer) handles HTTPS in front of the container, add `--proxy-headers` so the server trusts `X-Forwarded-*` headers and generates correct `https://` URLs:

```Dockerfile
CMD ["fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80"]
```

See [Sub-applications, Proxies and WSGI](../app-structure/sub-applications-proxy-and-wsgi.md) for forwarded headers and `root_path`.

## Build and run

```bash
docker build -t myimage .
docker run -d --name mycontainer -p 80:80 myimage
```

Then open `http://127.0.0.1/docs`.

### Single-file apps

If you only have `main.py` (no package):

```Dockerfile
FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./main.py /code/

CMD ["fastapi", "run", "main.py", "--port", "80"]
```

`fastapi run` detects that the file is a standalone module and imports it correctly.

## Deployment concepts with containers

- **HTTPS**: usually handled by another component (Traefik, a cloud load balancer, a Kubernetes ingress) — not inside your app container.
- **Running on startup and restarts**: handled by the container runtime/orchestrator (Docker restart policies, Docker Compose, Kubernetes).
- **Replication**:
  - In a **cluster** (Kubernetes etc.), run **one Uvicorn process per container** and replicate containers; the cluster's load balancer distributes traffic. Don't add `--workers` — another process manager inside the container only adds complexity.
  - For **special cases** — a simple app on a single server, or Docker Compose on one machine where replicating containers is awkward — run several workers in one container:

    ```Dockerfile
    CMD ["fastapi", "run", "app/main.py", "--port", "80", "--workers", "4"]
    ```
- **Memory**: one process per container gives a predictable per-container memory footprint you can declare as limits; with multiple workers, ensure processes × memory fits.
- **Previous steps (migrations)**: with many containers, run them in a separate single container first (e.g. a Kubernetes *Init Container*); with one container, run them in the container right before starting the app.

## Don't use the old base image

The former `tiangolo/uvicorn-gunicorn-fastapi` image is **deprecated**. It existed because Uvicorn once couldn't manage worker processes, requiring Gunicorn. Now `fastapi run --workers` / `uvicorn --workers` do that, so build your own image as above — it's about the same amount of code.

## Where to deploy the image

Docker Compose on a single server, a Kubernetes cluster, Docker Swarm, Nomad, or a cloud service that runs containers. The docs also describe using `uv` in images (see the uv Docker guide).

## Related

- [Deployment Concepts, Servers and Workers](deployment-concepts-and-servers.md)
- [HTTPS, TLS Termination and Cloud Providers](https-and-cloud.md)
