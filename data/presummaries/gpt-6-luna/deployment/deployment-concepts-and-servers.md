## Deployment

- Deploying makes an app available to users, typically on a remote machine running continuously, efficiently, and reliably. Options include doing it yourself, using containers such as Docker, or a managed service such as FastAPI Cloud; the same concepts apply.

## Running the server: `fastapi run`

- FastAPI is an ASGI application; an ASGI server runs it. `fastapi[standard]` includes Uvicorn and the CLI.
- `fastapi run main.py` starts a production server listening on `0.0.0.0:8000`, with auto-reload off. `fastapi dev` listens on `127.0.0.1` with reload on.
- The CLI finds the `app` object in the module or the `[tool.fastapi] entrypoint` from `pyproject.toml`, and prints the import string it uses (e.g. `main:app`).
- Equivalent Uvicorn command: `uvicorn main:app --host 0.0.0.0 --port 80`. `main:app` means the `app` object in module `main` (like `from main import app`). Other ASGI servers include Hypercorn and Daphne.
- **Don't use `--reload` in production**: it uses much more resources and is less stable.

## Multiple workers

- A single Python process uses one CPU core for your code. Multiple workers use several cores:
  - `fastapi run --workers 4 main.py`
  - `uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4`
- A manager listens on the port and distributes requests. Each worker is a separate process with its own memory; an ML model loaded at startup is loaded once per worker, multiplying memory use.
- On Kubernetes and similar orchestrators, usually do **not** use workers: run one Uvicorn process per container and let the cluster replicate containers.

## The deployment concepts

- Address HTTPS/TLS termination and certificate renewal (Traefik, Caddy, Nginx + Certbot, HAProxy, Kubernetes ingress, cloud load balancers); startup on machine boot and crash restarts (Docker, Kubernetes, Docker Compose, systemd, Supervisor, cloud service).
- Plan replication (processes, machines, load balancer; `--workers`, Kubernetes replicas, multiple containers), memory (RAM per process × processes; monitoring, `htop`), and previous steps such as DB migrations (Kubernetes Init Container, startup script).
- Small errors inside a request are handled by FastAPI: the client gets a 500 and the process keeps serving. A whole-process crash needs an external supervisor to restart it.
- Previous steps such as migrations must run in a **single** process, even if multiple workers start afterward, to avoid conflicting parallel migrations. Lifespan code runs **per process**, so it is not for one-time migrations with multiple workers.
- Aim to use a good share of CPU/RAM (e.g. 50–90%): idle servers waste money; saturated ones swap or crash. Measure and adjust.

## Pinning FastAPI versions

- FastAPI is still `0.x`: PATCH releases (e.g. `0.112.1` → `0.112.2`) are bug fixes and non-breaking changes; MINOR releases (`0.112` → `0.113`) may add features and breaking changes.
- Pin to a minor range (`fastapi[standard]>=0.112.0,<0.113.0`) or exact version (`fastapi[standard]==0.112.0`). Upgrade deliberately: have tests, bump the version, run tests, fix, re-pin, and check release notes.
- **Don't pin Starlette**; each FastAPI version requires a compatible Starlette range. **Pydantic** can be pinned to any version that works within FastAPI's supported range; this version requires `pydantic>=2.9.0`.

## Related

- Deploying with Docker; HTTPS, TLS Termination and Cloud Providers; Sub-applications, Proxies and WSGI (`--forwarded-allow-ips`, `--root-path`); First Steps and the FastAPI CLI.
