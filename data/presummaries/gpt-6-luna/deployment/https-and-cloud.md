- **How HTTPS works (for developers)**
  - HTTPS is not a switch inside FastAPI. A trusted third party issues certificates; they expire and must be renewed.
  - TLS encrypts at the TCP level, below HTTP, before the server knows the requested domain. TCP knows IP addresses, while the domain is in HTTP data; without extensions, each IP would need one certificate.
  - SNI (Server Name Indication) lets one process on one IP/port present the right certificate for several domains. After TLS is established, the protocol remains HTTP, encrypted.

- **The TLS termination proxy**
  - Only one process can listen on a given IP + port; HTTPS uses `443`. A proxy holds certificates, listens on `443`, performs the TLS handshake and picks a certificate via SNI, decrypts requests and forwards plain HTTP to the app (e.g. Uvicorn on port `8000`), then encrypts responses.
  - It can route multiple applications/domains on one server. Options: Traefik and Caddy (automatic certificate renewal), Nginx, HAProxy; cloud load balancers or Kubernetes ingress usually serve this role.
  - Register a domain and point its DNS `A` record to the server’s public IP. Typical flow: Browser → DNS lookup → IP → TLS (`443`, SNI) → proxy → HTTP → FastAPI (Uvicorn).
  - **Let's Encrypt** (Linux Foundation) issues free, automated, short-lived (~3 months) certificates. A program, often Traefik or Caddy, periodically proves domain ownership (e.g. HTTP or DNS challenges) and renews without downtime.

- **Forwarded headers**
  - The app receives plain HTTP and needs proxy-sent `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-For` plus server trust to know original scheme, host and client IP. Otherwise redirects and generated URLs use `http://`, not `https://`.
  - `fastapi run --forwarded-allow-ips="*"` or, in containers, `--proxy-headers`. See Sub-applications, Proxies and WSGI for stripped prefixes and `root_path`. `HTTPSRedirectMiddleware` can force HTTPS; usually the proxy handles redirects.

- **FastAPI Cloud**
  - Built by the FastAPI author and team; primary sponsor of FastAPI open source projects. Deploy with `fastapi deploy`. The CLI (in `fastapi-cli[standard]` via `fastapi[standard]`) detects the app, opens a browser login if needed, builds/deploys, and prints a URL such as `https://myapp.fastapicloud.dev`. It handles HTTPS, replication with request-based autoscaling, and other deployment concepts.
  - `[tool.fastapi] entrypoint` in `pyproject.toml` helps app discovery; the FastAPI editor extension can deploy and stream logs. To avoid the cloud CLI, install `standard-no-fastapi-cloud-cli` instead of `standard`.

- **Other cloud providers**
  - Any provider works; follow its FastAPI or container guide. Render and Railway sponsor FastAPI and document deployments. Most container platforms run the image from Deploying with Docker directly.
