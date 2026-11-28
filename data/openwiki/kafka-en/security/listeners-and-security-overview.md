---
type: security-guide
title: Security Overview, Listeners and Security Model
description: Kafka's security features (SSL/TLS, SASL mechanisms, authorization), how to configure listeners and security protocols for brokers and KRaft controllers (listeners, advertised.listeners, listener.security.protocol.map, inter.broker.listener.name, controller.listener.names), the Kafka, Connect and Streams security models and their trust assumptions, at-rest and audit considerations, and how to add security to a running cluster with rolling bounces.
tags: [security, listeners, tls, sasl, security-model, connect, streams, operations]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-ddf60b45320ebb624268e1cb
    resource: repo://docs/security/incorporating-security-features-in-a-running-cluster.md
  - id: openwiki-source-23a1b5a32c4f095d9146173d
    resource: repo://docs/security/listener-configuration.md
  - id: openwiki-source-745d71f8c4aad694bdcf6ea1
    resource: repo://docs/security/security-model-connect.md
  - id: openwiki-source-22e18b414528a165fe2684dc
    resource: repo://docs/security/security-model-streams.md
  - id: openwiki-source-8fc85a5d9163aa6c044434d0
    resource: repo://docs/security/security-model.md
  - id: openwiki-source-5fc7de114ce0e076a46c43e4
    resource: repo://docs/security/security-overview.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Security Overview, Listeners and Security Model

## Supported security features

1. **Authentication** of connections from clients, other brokers and tools using **SSL** (mTLS) or **SASL**:
   - SASL/GSSAPI (Kerberos) — since 0.9.0.0
   - SASL/PLAIN — since 0.10.0.0
   - SASL/SCRAM-SHA-256 and SASL/SCRAM-SHA-512 — since 0.10.2.0
   - SASL/OAUTHBEARER — since 2.0
2. **Encryption** in transit (client↔broker, broker↔broker, broker↔tools) with SSL/TLS. Enabling SSL costs some performance, depending on CPU and JVM.
3. **Authorization** of client operations.
4. **Pluggable authorization**, including external authorization services.

Security is optional — non-secured clusters and mixes of authenticated/unauthenticated and encrypted/unencrypted clients are supported. Detailed guides: [SSL](ssl-encryption-and-authentication.md), [SASL and delegation tokens](sasl-authentication.md), [Authorization and ACLs](authorization-and-acls.md).

## Listeners

Each server defines the listeners on which it accepts requests; each listener has its own authentication and encryption.

```text
{LISTENER_NAME}://{hostname}:{port}
```

```properties
listeners=CLIENT://localhost:9092
listener.security.protocol.map=CLIENT:SSL,BROKER:PLAINTEXT
```

- `listeners` — at least one per server; comma-separated.
- `listener.security.protocol.map` — maps each listener name to a protocol (case-insensitive): `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL`. Default: `SASL_SSL:SASL_SSL,PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT`.
- If each listener uses a different protocol you may use protocol names as listener names (`listeners=SSL://localhost:9092,PLAINTEXT://localhost:9093`), but **explicit names are recommended** for clarity.
- `advertised.listeners` — what the broker tells clients to connect to after the first metadata fetch; treat it as part of your security configuration.

| Protocol | Authentication | Encryption |
| --- | --- | --- |
| `PLAINTEXT` | None | None |
| `SSL` | Optional mTLS | TLS |
| `SASL_PLAINTEXT` | SASL | None |
| `SASL_SSL` | SASL (+ optional mTLS) | TLS |

### Inter-broker and controller listeners (KRaft)

- `inter.broker.listener.name` — the listener used **exclusively between brokers** (mainly replication). If unset, it is chosen by `security.inter.broker.protocol` (default `PLAINTEXT`).
- `controller.listener.names` — the listener(s) controllers use. It **cannot be the same** as the inter-broker listener.
- Controllers receive requests from controllers and brokers, so **every broker must define the controller listener's security settings** even if it doesn't host a controller (it just doesn't list it in `listeners`).
- Hosts/ports in `controller.quorum.bootstrap.servers` must route to the exposed controller listeners.
- A controller accepts requests on all `controller.listener.names`; with several, the **first** is used for outbound requests — useful for migrating the controller listener to a new port or protocol with two rolls.

Broker-only node:

```properties
process.roles=broker
listeners=BROKER://localhost:9092
inter.broker.listener.name=BROKER
controller.quorum.bootstrap.servers=localhost:9093
controller.listener.names=CONTROLLER
listener.security.protocol.map=BROKER:SASL_SSL,CONTROLLER:SASL_SSL
```

Combined broker+controller node — the controller listener is also in `listeners`:

```properties
process.roles=broker,controller
listeners=BROKER://localhost:9092,CONTROLLER://localhost:9093
inter.broker.listener.name=BROKER
controller.quorum.bootstrap.servers=localhost:9093
controller.listener.names=CONTROLLER
listener.security.protocol.map=BROKER:SASL_SSL,CONTROLLER:SASL_SSL
```

Convention: use a **separate listener for clients**, so inter-broker and controller listeners can be isolated at the network level. Clients never use the controller listener — requests bound for the controller are forwarded by brokers. Listeners can be added/removed dynamically ([Broker configuration](../configuration/broker-configuration.md#what-can-be-changed-dynamically)).

## The Kafka security model

### Assumptions

- **Security is off by default**: a fresh cluster accepts unauthenticated `PLAINTEXT` on every listener with no authorization. Production must configure authentication, authorization and encryption before exposure to untrusted networks.
- **Trusted operators**: anyone with shell access to brokers/controllers or their disks can read every topic, forge principals and rewrite ACLs.
- **Trusted broker fleet**: any host able to authenticate on inter-broker/controller listeners is inside the trust boundary.
- **Trusted JVM and classpath**, and **pluggable interfaces grant code execution** — authorizers, (de)serializers, connectors, transforms, config providers run with the host process's privileges; only install trusted plugins.
- **Data plane vs control plane**: producer/consumer traffic, the Admin API and JMX each have separate auth stories — securing one doesn't secure the others.
- **No encryption at rest.**
- Report vulnerabilities privately to `security@kafka.apache.org` (not public JIRA/GitHub/mailing lists).

### Network boundary

1. Bind external listeners only to interfaces reachable by intended clients.
2. Treat `advertised.listeners` as security configuration.
3. Never expose the controller listener to client networks; keep inter-broker/controller traffic on a dedicated internal `SSL`/`SASL_SSL` listener firewalled from clients.

### Authentication

- **mTLS** (`ssl.client.auth=required`): principal from the certificate DN via `ssl.principal.mapping.rules` or a custom `KafkaPrincipalBuilder`. **Recommended for broker-to-broker and controller-to-broker** traffic (no shared passwords, rotates with PKI).
- **SASL** (`sasl.enabled.mechanisms` per listener): `GSSAPI` (if you run a KDC), `SCRAM-SHA-256`/`SCRAM-SHA-512` (credentials in cluster metadata, managed with `kafka-configs.sh`), `OAUTHBEARER` (the default unsecured implementation is **for testing only** — production must configure JWKS and validation), `PLAIN` (**only inside `SASL_SSL`**, never `SASL_PLAINTEXT`).
- **Delegation tokens**: short-lived tokens used as SCRAM credentials by frameworks (Spark, Flink, Connect) fanning out to many tasks; they inherit the requester's principal and ACLs and expire per `delegation.token.expiry.time.ms`.

### Authorization defaults

- **No authorizer configured → all authenticated principals have full access** (identity without authorization).
- Authorizer configured, no matching ACL → **denied**, except `super.users` (treat that list like a root password).
- `allow.everyone.if.no.acl.found=true` is a transitional aid only.

### Encryption in transit

- Disable TLS below 1.2; prefer TLS 1.3.
- Use **separate keystores** for inter-broker and client-facing listeners.
- Keep `ssl.endpoint.identification.algorithm=https` on clients (default since 2.0).
- Rotate keystores dynamically with `kafka-configs.sh --entity-type brokers --alter --add-config ...`.
- Connect, MirrorMaker 2 and Streams use the same `ssl.*`/`sasl.*` client configs — secure them too.

### Encryption at rest

Kafka writes log segments, indexes, snapshots and controller metadata as plain bytes. Options, in increasing cost:

1. Filesystem or block-device encryption (protects against disk theft, not broker logins).
2. Message-level encryption by producers with an external KMS (the only option protecting data from broker operators; prevents broker/Streams features that read payloads).
3. Tiered storage with a remote store that encrypts.

### Audit logging and secrets

- Authorizer decisions go to the log4j logger `kafka.authorizer.logger`: `INFO` logs denials, `DEBUG` also allowed requests. Ship to append-only storage off-broker; there is no built-in tamper-evident audit trail. `kafka.request.logger` gives verbose per-request detail (off by default).
- Use `ConfigProvider`s instead of cleartext secrets, with `allowed.paths` set on file-based providers ([config providers](../configuration/config-providers-and-system-properties.md)). Note: the security model page mentions `password.encoder.secret` for encrypting sensitive dynamic configs, but the KRaft differences page lists the `password.encoder.*` configs as removed and states sensitive data is **not** encrypted in KRaft — see [ZooKeeper to KRaft](../operations/zookeeper-to-kraft-migration.md).
- **JMX** is operator-only and unauthenticated by default: disable it, bind it to localhost with an exporter, or enable `com.sun.management.jmxremote.authenticate=true` with TLS.

### Scope of the model

Out of scope: development/test tooling (Trogdor, `tests/`, `release/`), end-of-life releases, accumulated base-image CVEs in already-published Docker images (rebuild/patch images yourself). The attack surface is brokers, controllers, client/inter-broker/controller listeners, the Admin API and JMX. Not vulnerabilities by themselves: open default clusters, authorized actions by trusted principals, Streams application-level bugs.

## Kafka Connect security model

Connect workers authenticate to Kafka like any client; on top of that:

- **The REST API is unauthenticated by default** — anyone reaching it can create, reconfigure, stop or delete connectors, and since plugins run arbitrary code, effectively run code on workers.
- **No per-connector isolation**: any API caller can act on every connector and read its config.
- **One Kafka principal per worker** shared by all connectors; connectors can override internal client configs (including credentials) unless `connector.client.config.override.policy` restricts it. Default is `All`; **since 4.2.0 `Allowlist` is recommended** (default in 5.0). Class-loading overrides (`sasl.jaas.config`, `sasl.login.class`) are code-execution vectors.
- State in distributed mode lives in `config.storage.topic`, `offset.storage.topic`, `status.storage.topic` (inline secrets end up in the config topic) — protect with ACLs. Standalone offsets live in `offset.storage.file.filename`.

Recommendations:

1. Never expose the REST API to untrusted networks; use a management network or reverse proxy.
2. Use `admin.listeners` to separate or disable `/admin` endpoints.
3. Prefer `https` listeners (also encrypts inter-worker forwarding; `listeners.https.*` for REST-specific TLS).
4. Add authentication via a reverse proxy or `rest.extension.classes` — the built-in `BasicAuthSecurityRestExtension` does JAAS HTTP basic auth; its reference `PropertyFileLoginModule` stores cleartext credentials and is **not for production**.
5. Partition the worker principal's ACLs by topic prefix; give distrusting teams **separate Connect clusters**.
6. Prefer `ConfigProvider` references — only the template (`${alias:fields}`) is stored in the config topic — but REST callers who know a template can usually still resolve the value.

Details: [Connect REST API and operations](../connect/rest-api-and-operations.md#security).

## Kafka Streams security model

- Streams is a **client library** running inside your application; its boundary is the application's — no separate network surface.
- An app authenticates as **one principal**, needing ACLs on its source topics, internal repartition/changelog topics (typically `<application.id>-*`) and the consumer group `<application.id>`.
- Local state stores live on disk, protected only by the host filesystem (not encrypted by Kafka).

See [Running Streams apps](../streams/running-and-rebalancing.md) for Streams security configuration.

## Adding security to a running cluster

Secure a live cluster in phases (rolling restarts, SIGTERM for clean stops, wait for replicas to rejoin the ISR before the next node). A `PLAINTEXT` port stays open until the end:

1. Bounce brokers to **open the secured port(s)**.
2. Restart **clients** against the secured port.
3. Bounce again to switch **broker-to-broker** traffic (if required).
4. Final bounce to **close `PLAINTEXT`**.

Example — SSL for clients and brokers:

```properties
# bounce 1
listeners=PLAINTEXT://broker1:9091,SSL://broker1:9092
# clients
bootstrap.servers = [broker1:9092,...]
security.protocol = SSL
# bounce 2
listeners=PLAINTEXT://broker1:9091,SSL://broker1:9092
security.inter.broker.protocol=SSL
# bounce 3
listeners=SSL://broker1:9092
security.inter.broker.protocol=SSL
```

Example — SSL between brokers plus SASL_SSL for clients:

```properties
# bounce 1
listeners=PLAINTEXT://broker1:9091,SSL://broker1:9092,SASL_SSL://broker1:9093
# clients
bootstrap.servers = [broker1:9093,...]
security.protocol = SASL_SSL
# bounce 2
listeners=PLAINTEXT://broker1:9091,SSL://broker1:9092,SASL_SSL://broker1:9093
security.inter.broker.protocol=SSL
# bounce 3
listeners=SSL://broker1:9092,SASL_SSL://broker1:9093
security.inter.broker.protocol=SSL
```

Client↔broker and broker↔broker protocols must be changed in **separate** bounces.

## Related pages

- [Encryption and authentication with SSL](ssl-encryption-and-authentication.md)
- [Authentication with SASL](sasl-authentication.md)
- [Authorization and ACLs](authorization-and-acls.md)
- [Broker configuration](../configuration/broker-configuration.md)
