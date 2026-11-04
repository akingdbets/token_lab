---
type: guide
title: Deploying with docker
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
H1: DEPLOYING WITH docker
CONTAINERS (USUALLY docker IMAGES) PACKAGE app + PYTHON RUNTIME + DEPENDENCIES;
RESULT: REPRODUCIBLE, ISOLATED DEPLOYMENTS
CONTAINERS=COMMONEST FASTAPI DEPLOYMENT METHOD
RELATED CONCEPTS: [DEPLOYMENT CONCEPTS, SERVERS AND workers](deployment-concepts-and-servers.md)
CONTAINER RUNS ONE MAIN PROCESS (`CMD`); LIFETIME=PROCESS LIFETIME
H2: PROJECT LAYOUT
⟦code-0⟧
`requirements.txt` LISTS PINNED DEPENDENCIES INSTALLED WITH `pip` INSIDE IMAGE
FOR PROJECTS MANAGED WITH `uv` (`uv add "fastapi[standard]" pydantic`,
VERSIONS LOCKED IN `uv.lock`), EXPORT FOR CONTAINER BUILD;
REGENERATE WHENEVER `uv.lock` CHANGES:
⟦code-1⟧
H2: THE DOCKERFILE
⟦code-2⟧
STEP BY STEP:
1. START FROM OFFICIAL PYTHON BASE IMAGE
2. SET `/code` AS WORKING DIRECTORY
3. COPY ONLY `requirements.txt` FIRST
4. INSTALL DEPENDENCIES; `--no-cache-dir` KEEPS IMAGE SMALLER
5. COPY APPLICATION code
6. START PRODUCTION SERVER WITH `fastapi run`; IT USES uvicorn
H3: WHY COPY REQUIREMENTS FIRST (LAYER cache)
docker CACHES EACH INSTRUCTION AS A LAYER; REUSES IT IF INPUTS UNCHANGED
DEPENDENCIES CHANGE RARELY; code CHANGES OFTEN
COPY `requirements.txt` + INSTALL BEFORE COPYING `./app`:
code CHANGE REBUILDS ONLY LAST LAYERS, NOT EVERY PACKAGE;
SAVES MINUTES PER BUILD
H3: ALWAYS USE THE EXEC FORM OF `CMD`
⟦code-3⟧
SHELL FORM WRAPS SERVER IN `/bin/sh`; IT DOES NOT FORWARD SIGNALS
EXEC FORM: FASTAPI RECEIVES STOP SIGNAL, SHUTS DOWN GRACEFULLY,
AND RUNS SHUTDOWN PART OF [LIFESPAN EVENTS](../app-structure/lifespan-events.md)
SHELL FORM: e.g., `docker compose` TAKES ~10 SECONDS TO STOP SERVICES
H3: BEHIND A TLS TERMINATION proxy
IF proxy (NGINX, TRAEFIK, OR CLOUD LOAD BALANCER) HANDLES HTTPS
IN FRONT OF CONTAINER, add `--proxy-headers`:
SERVER TRUSTS `X-Forwarded-*` headers AND GENERATES CORRECT `https://` URLs
⟦code-4⟧
SEE [SUB-APPLICATIONS, PROXIES AND WSGI](../app-structure/sub-applications-proxy-and-wsgi.md)
FOR Forwarded headers AND `root_path`
H2: BUILD AND run
⟦code-5⟧
THEN OPEN `http://127.0.0.1/docs`
H3: SINGLE-FILE APPS
IF ONLY `main.py` (no PACKAGE):
⟦code-6⟧
`fastapi run` DETECTS STANDALONE MODULE AND IMPORTS IT CORRECTLY
H2: DEPLOYMENT CONCEPTS WITH CONTAINERS
```
.
├── app
│   ├── __init__.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```
```bash
uv export --format requirements-txt --no-dev --no-emit-project --output-file requirements.txt
```
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
```Dockerfile
# ✅ Do this
CMD ["fastapi", "run", "app/main.py", "--port", "80"]

# ⛔️ Don't do this
CMD fastapi run app/main.py --port 80
```
```Dockerfile
CMD ["fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80"]
```
```bash
docker build -t myimage .
docker run -d --name mycontainer -p 80:80 myimage
```
```Dockerfile
FROM python:3.14

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./main.py /code/

CMD ["fastapi", "run", "main.py", "--port", "80"]
```
- HTTPS: USUALLY HANDLED BY ANOTHER COMPONENT (Traefik, A CLOUD LOAD BALANCER,
  A Kubernetes INGRESS); NOT INSIDE YOUR app CONTAINER.
- STARTUP/RESTARTS: HANDLED BY CONTAINER RUNTIME/ORCHESTRATOR
  (docker RESTART POLICIES, docker compose, Kubernetes).
- REPLICATION:
  - IN A CLUSTER (Kubernetes, ETC.), run ONE uvicorn PROCESS PER CONTAINER;
    REPLICATE CONTAINERS; CLUSTER LOAD BALANCER DISTRIBUTES TRAFFIC.
    DON’T add `--workers`: ANOTHER PROCESS MANAGER INSIDE THE CONTAINER
    ONLY ADDS COMPLEXITY.
  - SPECIAL CASES: SIMPLE app ON ONE SERVER, OR docker compose ON ONE
    MACHINE WHERE CONTAINER REPLICATION IS AWKWARD; run SEVERAL workers
    IN ONE CONTAINER:

⟦code-7⟧

- MEMORY: ONE PROCESS PER CONTAINER GIVES PREDICTABLE PER-CONTAINER MEMORY
  FOOTPRINT, DECLARABLE AS LIMITS; WITH MULTIPLE workers, ENSURE
  PROCESSES × MEMORY FITS.
- PREVIOUS STEPS (MIGRATIONS): WITH MANY CONTAINERS, run IN A SEPARATE
  SINGLE CONTAINER FIRST (e.g., A Kubernetes *Init Container*); WITH ONE
  CONTAINER, run IN THAT CONTAINER RIGHT BEFORE app START.

H2: DON’T USE THE OLD BASE IMAGE

THE FORMER `tiangolo/uvicorn-gunicorn-fastapi` IMAGE IS DEPRECATED.
IT EXISTED BECAUSE uvicorn ONCE COULDN’T MANAGE WORKER PROCESSES,
REQUIRING gunicorn. NOW `fastapi run --workers` / `uvicorn --workers`
DO THAT; BUILD YOUR OWN IMAGE AS ABOVE—ABOUT THE SAME AMOUNT OF code.

H2: WHERE TO DEPLOY THE IMAGE

docker compose ON A SINGLE SERVER, A Kubernetes CLUSTER, docker Swarm,
Nomad, OR A CLOUD SERVICE THAT RUNS CONTAINERS. docs ALSO DESCRIBE USING
`uv` IN IMAGES (SEE THE uv docker GUIDE).

H2: RELATED

- [DEPLOYMENT CONCEPTS, SERVERS AND workers](deployment-concepts-and-servers.md)
- [HTTPS, TLS TERMINATION AND CLOUD PROVIDERS](https-and-cloud.md)
    ```Dockerfile
    CMD ["fastapi", "run", "app/main.py", "--port", "80", "--workers", "4"]
    ```
