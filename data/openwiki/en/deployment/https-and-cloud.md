---
type: guide
title: HTTPS, TLS Termination and Cloud Providers
description: How HTTPS works from a developer's perspective (certificates, TLS, SNI, TLS termination proxies, Let's Encrypt renewal, forwarded headers) and deploying FastAPI to FastAPI Cloud with fastapi deploy or to other cloud providers.
tags: [https, tls, sni, lets-encrypt, proxy, fastapi-cloud, cloud, deployment]
verified:
  - by: openwiki/0.7.0
    at: 2026-10-05T02:25:02.861Z
sources:
  - id: openwiki-source-48121ae2ef6cd4e287e2cecb
    resource: repo://docs/en/docs/deployment/cloud.md
  - id: openwiki-source-05b2dcec8163d7ab916d681f
    resource: repo://docs/en/docs/deployment/fastapicloud.md
  - id: openwiki-source-4ed3f158b6c4f6079e2aec29
    resource: repo://docs/en/docs/deployment/https.md
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
generated: { by: "claude-code", at: "2026-10-05T02:25:02.861Z" }
---

# HTTPS, TLS Termination and Cloud Providers

## How HTTPS works (for developers)

HTTPS is not a switch you turn on inside FastAPI. Key facts:

- The server needs **certificates** acquired from a trusted third party. Certificates **expire** and must be **renewed**.
- Encryption happens at the **TCP level** (TLS), **below HTTP**, before the server knows which domain was requested.
- TCP knows only IP addresses; the domain lives in HTTP data. Without extensions, that would mean one certificate per IP.
- The **SNI** (Server Name Indication) TLS extension lets one process on one IP/port present the right certificate for each of several domains.
- After the TLS connection is established, the protocol is still plain **HTTP** — just encrypted.

### The TLS termination proxy

Only one process can listen on a given IP + port (HTTPS uses `443`). So the common setup is a single **TLS termination proxy** that:

1. Holds all certificates and listens on port 443.
2. Performs the TLS handshake, picking the certificate via SNI.
3. Decrypts the request and forwards **plain HTTP** to your app (e.g. Uvicorn running FastAPI on port 8000).
4. Encrypts the app's plain HTTP response and sends it back.

It can route to multiple applications/domains on the same server. Options include **Traefik** and **Caddy** (both can renew certificates automatically), **Nginx** and **HAProxy**; in the cloud, a load balancer or Kubernetes ingress usually plays this role.

Typical request flow:

```
Browser ──DNS lookup──▶ IP of someapp.example.com
Browser ──TLS (443, SNI)──▶ TLS termination proxy ──HTTP──▶ FastAPI (Uvicorn)
```

Before any of this you register a **domain** and point a DNS `A` record to your server's public IP.

### Let's Encrypt and renewal

**Let's Encrypt** (Linux Foundation) issues free, automated, short-lived (~3 months) certificates. A program — often the proxy itself (Traefik, Caddy) — periodically proves domain ownership (e.g. via HTTP or DNS challenges) and renews certificates without downtime.

### Forwarded headers

Because your app receives plain HTTP from the proxy, it doesn't know the original scheme, host or client IP unless the proxy sends `X-Forwarded-Proto`, `X-Forwarded-Host` and `X-Forwarded-For` **and** the server is told to trust them:

```bash
fastapi run --forwarded-allow-ips="*"     # or, in containers: --proxy-headers
```

Otherwise redirects and generated URLs would point to `http://` instead of `https://`. Details, plus stripped path prefixes and `root_path`, in [Sub-applications, Proxies and WSGI](../app-structure/sub-applications-proxy-and-wsgi.md). `HTTPSRedirectMiddleware` can force HTTPS at the app level (see [Middleware](../middleware/middleware.md)), but in most deployments the proxy handles redirects.

## FastAPI Cloud

**FastAPI Cloud** is built by the FastAPI author and team (and is the primary sponsor of the FastAPI open source projects). Deploying is one command:

```bash
fastapi deploy
```

The CLI (included via `fastapi-cli[standard]` in `fastapi[standard]`) detects your app, opens the browser to log in if needed, builds and deploys it, and prints a URL such as `https://myapp.fastapicloud.dev`. FastAPI Cloud takes care of HTTPS, replication with request-based autoscaling, and other deployment concepts. Configuring `[tool.fastapi] entrypoint` in `pyproject.toml` helps it find your app; the FastAPI editor extension can also deploy and stream logs.

If you don't want the cloud CLI, install the `standard-no-fastapi-cloud-cli` extra instead of `standard`.

## Other cloud providers

FastAPI is open source and standards-based, so any provider works: follow your provider's FastAPI or container guide. Providers that sponsor FastAPI and document FastAPI deployments include **Render** and **Railway**. Most container platforms run the image from [Deploying with Docker](docker.md) directly.

## Related

- [Deployment Concepts, Servers and Workers](deployment-concepts-and-servers.md)
- [Deploying with Docker](docker.md)
