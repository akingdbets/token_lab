---
type: guide
title: Deployment Concepts, Servers and Workers
description: The concepts every FastAPI deployment must address (HTTPS, startup, restarts, replication, memory, pre-start steps, resource use), running with fastapi run or Uvicorn, multiple worker processes, and pinning FastAPI versions.
tags: [deployment, uvicorn, fastapi-run, workers, processes, replication, versions]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-c4942803a280a2e51c833734
    resource: repo://docs/en/docs/deployment/concepts.md
  - id: openwiki-source-8475fe88ce83cde8cb6ff8c8
    resource: repo://docs/en/docs/deployment/manually.md
  - id: openwiki-source-522eb3366590e7fcffb51437
    resource: repo://docs/en/docs/deployment/server-workers.md
  - id: openwiki-source-59423393aef62df38afc5cc7
    resource: repo://docs/en/docs/deployment/versions.md
  - id: openwiki-source-9bc15a21c009b14775a3dd72
    resource: repo://docs/en/docs/fastapi-cli.md
  - id: openwiki-source-dc198b5a2f25036adad646d4
    resource: repo://fastapi/cli.py
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# Deployment Concepts, Servers and Workers

To **deploy** an app means making it available to users: typically on a remote machine, running continuously, efficiently and reliably. You can do it yourself, use containers ([Docker](docker.md)), or a managed service such as FastAPI Cloud (see [HTTPS, TLS Termination and Cloud Providers](https-and-cloud.md)). Whatever you choose, the same concepts apply.

## Running the server: `fastapi run`

FastAPI is an ASGI application; an **ASGI server** runs it. `fastapi[standard]` includes **Uvicorn** and the CLI:

```bash
fastapi run main.py
```

`fastapi run` starts a **production** server: it listens on `0.0.0.0:8000` and has auto-reload **off** (unlike `fastapi dev`, which listens on `127.0.0.1` with reload on). It finds the `app` object in the module (or the `[tool.fastapi] entrypoint` from `pyproject.toml`) and prints the import string it uses (e.g. `main:app`).

Equivalent with Uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 80
```

`main:app` means "the `app` object in module `main`" (like `from main import app`). Other ASGI servers include Hypercorn and Daphne.

**Don't use `--reload` in production** — it uses much more resources and is less stable; it's a development convenience.

## Multiple workers

A single Python process uses one CPU core for your code. To use several cores, run several worker processes:

```bash
fastapi run --workers 4 main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

A manager process listens on the port and distributes requests to the workers. Each worker is a separate process with its **own memory**: an ML model loaded at startup is loaded once per worker, so memory use multiplies.

On **Kubernetes** and similar orchestrators you usually do **not** use workers; run one Uvicorn process per container and let the cluster replicate containers.

## The deployment concepts

| Concept | Question to answer | Example tools |
|---------|-------------------|---------------|
| **Security – HTTPS** | Who terminates TLS and renews certificates? | Traefik, Caddy, Nginx + Certbot, HAProxy, Kubernetes ingress, cloud load balancers |
| **Running on startup** | What starts the server when the machine boots (not you in an SSH session)? | Docker, Kubernetes, Docker Compose, systemd, Supervisor, a cloud service |
| **Restarts** | What restarts the process after a crash? | Same tools as above |
| **Replication** | How many processes, on how many machines, behind which load balancer? | `--workers`, Kubernetes replicas, multiple containers |
| **Memory** | How much RAM does each process need × number of processes? | Monitoring, `htop` |
| **Previous steps before starting** | Who runs DB migrations etc. **once**, before processes start? | Kubernetes Init Container, a startup script |

Notes:

- **Small errors** inside a request are handled by FastAPI — the client gets a 500 and the process keeps serving. **Crashes** of the whole process need an external supervisor to restart it.
- **Previous steps** (like migrations) must run in a **single** process even if you then start many workers, otherwise parallel migrations can conflict.
- **Resource utilization**: aim to use a good share of CPU/RAM (e.g. 50–90%) — idle servers waste money, saturated ones swap or crash. Measure and adjust.

Lifespan code ([Lifespan Events](../app-structure/lifespan-events.md)) runs **per process**, so it is not the place for one-time migrations when you run multiple workers.

## Pinning FastAPI versions

FastAPI is still `0.x`. Following semantic-versioning conventions for pre-1.0 software:

- **PATCH** releases (`0.112.1` → `0.112.2`) are bug fixes and non-breaking changes.
- **MINOR** releases (`0.112` → `0.113`) may add features *and* breaking changes.

So pin to a minor range, or an exact version:

```txt
fastapi[standard]>=0.112.0,<0.113.0
# or
fastapi[standard]==0.112.0
```

Upgrade deliberately: have tests ([Testing with TestClient](../testing/testing-basics.md)), bump the version, run the tests, fix, then re-pin. Check the release notes for changes.

- **Don't pin Starlette** — each FastAPI version requires a compatible Starlette range itself.
- **Pydantic** can be pinned to any version that works for you within FastAPI's supported range (this version requires `pydantic>=2.9.0`).

## Related

- [Deploying with Docker](docker.md)
- [HTTPS, TLS Termination and Cloud Providers](https-and-cloud.md)
- [Sub-applications, Proxies and WSGI](../app-structure/sub-applications-proxy-and-wsgi.md) — `--forwarded-allow-ips`, `--root-path`
- [First Steps and the FastAPI CLI](../getting-started/first-steps.md)
