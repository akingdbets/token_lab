---
type: guide
title: HTTPS, TLS Termination and cloud Providers
description: How HTTPS works from a developer's perspective (certificates, TLS, SNI, TLS termination proxies, Let's Encrypt renewal, Forwarded headers) and deploying FastAPI to FastAPI cloud with fastapi deploy or to other cloud providers.
tags: [https, TLS, SNI, lets-encrypt, proxy, fastapi-cloud, cloud, deployment]
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

H1: HTTPS, TLS Termination and cloud Providers

H2: How HTTPS works (For developers)

HTTPS ISN'T A SWITCH ENABLED INSIDE FastAPI.
KEY FACTS:
- SERVER NEEDS CERTIFICATES FROM A TRUSTED THIRD PARTY.
  CERTIFICATES EXPIRE ∧ REQUIRE RENEWAL.
- ENCRYPTION OCCURS AT TCP LEVEL (TLS), BELOW HTTP,
  BEFORE SERVER KNOWS REQUESTED DOMAIN.
- TCP KNOWS ONLY IP ADDRESSES; DOMAIN IS IN HTTP DATA.
  WITHOUT EXTENSIONS, EACH IP NEEDS ONE CERTIFICATE.
- Server Name Indication(SNI) TLS EXTENSION LETS ONE
  PROCESS ON ONE IP/PORT PRESENT THE RIGHT CERTIFICATE
  For EACH OF SEVERAL DOMAINS.
- AFTER TLS CONNECTION ESTABLISHES, PROTOCOL REMAINS
  PLAIN HTTP, BUT ENCRYPTED.

H3: The TLS termination proxy

ONLY ONE PROCESS CAN LISTEN ON A GIVEN IP + PORT
(HTTPS USES `443`).
COMMON SETUP: ONE TLS TERMINATION PROXY:
1. HOLDS ALL CERTIFICATES ∧ LISTENS ON PORT 443.
2. PERFORMS TLS HANDSHAKE; PICKS CERTIFICATE VIA SNI.
3. DECRYPTS REQUEST ∧ FORWARDS PLAIN HTTP TO YOUR APP
   (e.g., Uvicorn RUNNING FastAPI ON PORT 8000).
4. ENCRYPTS APP'S PLAIN HTTP RESPONSE ∧ SENDS IT BACK.

PROXY CAN ROUTE TO MULTIPLE APPLICATIONS/DOMAINS
ON SAME SERVER.
OPTIONS: Traefik ∧ Caddy (BOTH CAN RENEW CERTIFICATES
AUTOMATICALLY), Nginx ∧ HAProxy.
IN cloud, LOAD BALANCER OR Kubernetes INGRESS USUALLY
PLAYS THIS ROLE.

TYPICAL REQUEST FLOW:

```
Browser ──DNS lookup──▶ IP of someapp.example.com
Browser ──TLS (443, SNI)──▶ TLS termination proxy ──HTTP──▶ FastAPI (Uvicorn)
```

BEFORE THIS, REGISTER A DOMAIN ∧ POINT DNS `A` RECORD
TO YOUR SERVER'S PUBLIC IP.

H3: Let's Encrypt and renewal

Let's Encrypt (Linux Foundation) ISSUES FREE, AUTOMATED,
SHORT-LIVED (~3 months) CERTIFICATES.
A PROGRAM, OFTEN THE PROXY ITSELF (Traefik, Caddy),
PERIODICALLY PROVES DOMAIN OWNERSHIP (e.g., VIA HTTP
OR DNS CHALLENGES) ∧ RENEWS CERTIFICATES WITHOUT DOWNTIME.

H3: Forwarded headers

APP RECEIVES PLAIN HTTP FROM PROXY; IT DOESN'T KNOW
ORIGINAL SCHEME, Host OR CLIENT IP UNLESS PROXY SENDS
`X-Forwarded-Proto`, `X-Forwarded-Host` AND
`X-Forwarded-For`, AND SERVER IS TOLD TO TRUST THEM:

```bash
fastapi run --forwarded-allow-ips="*"     # or, in containers: --proxy-headers
```

OTHERWISE, REDIRECTS ∧ GENERATED URLs POINT TO `http://`
INSTEAD OF `https://`.
DETAILS, PLUS STRIPPED PATH PREFIXES ∧ `root_path`,
IN [SUB-APPLICATIONS, PROXIES AND WSGI](../app-structure/sub-applications-proxy-and-wsgi.md).
`HTTPSRedirectMiddleware` CAN FORCE HTTPS AT APP LEVEL
(SEE [MIDDLEWARE](../middleware/middleware.md)),
BUT PROXY HANDLES REDIRECTS IN MOST DEPLOYMENTS.

H2: FastAPI cloud

FastAPI cloud IS BUILT BY THE FastAPI AUTHOR ∧ TEAM;
IT IS ALSO THE PRIMARY SPONSOR OF FastAPI OPEN SOURCE
PROJECTS.
DEPLOYMENT: ONE COMMAND:

```bash
fastapi deploy
```
CLI (INCLUDED VIA `fastapi-cli[standard]` IN `fastapi[standard]`) DETECTS YOUR APP;
OPENS BROWSER TO LOG IN IF NEEDED; BUILDS AND DEPLOYS APP; PRINTS URL SUCH AS
URL:https://myapp.fastapicloud.dev.
FASTAPI cloud HANDLES HTTPS, REPLICATION WITH REQUEST-BASED AUTOSCALING, AND
OTHER DEPLOYMENT CONCEPTS.
CONFIGURING `[tool.fastapi] entrypoint` IN `pyproject.toml` HELPS FASTAPI cloud
FIND YOUR APP; FASTAPI EDITOR EXTENSION CAN ALSO DEPLOY AND STREAM LOGS.
IF YOU DO NOT WANT cloud CLI, INSTALL `standard-no-fastapi-cloud-cli` EXTRA
INSTEAD OF `standard`.

H2: OTHER cloud PROVIDERS

FASTAPI IS OPEN SOURCE AND STANDARDS-BASED, SO ANY PROVIDER WORKS: FOLLOW YOUR
PROVIDER'S FASTAPI OR CONTAINER GUIDE.
PROVIDERS THAT SPONSOR FASTAPI AND DOCUMENT FASTAPI DEPLOYMENTS INCLUDE RENDER
AND RAILWAY.
MOST CONTAINER PLATFORMS RUN IMAGE FROM [DEPLOYING WITH DOCKER](docker.md)
DIRECTLY.

H2: RELATED

- [DEPLOYMENT CONCEPTS, SERVERS AND WORKERS](deployment-concepts-and-servers.md)
- [DEPLOYING WITH DOCKER](docker.md)
