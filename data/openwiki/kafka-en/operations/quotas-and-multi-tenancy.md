---
type: "Reference"
title: "Quotas and Multi-Tenancy"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
  - id: openwiki-source-0473e4d896842f9b96b387fc
    resource: repo://docs/operations/multi-tenancy.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---


# Quotas and Multi-Tenancy

## Client quotas

Brokers can enforce quotas on requests so clients can't monopolize broker resources. Two types apply to each **group of clients sharing a quota**:

1. **Network bandwidth quotas** — byte-rate thresholds (since 0.9).
2. **Request rate quotas** — CPU utilization thresholds as a percentage of network and I/O threads (since 0.11).

**Why:** high-volume or high-request-rate clients can saturate the network, monopolize brokers and effectively DoS other clients and the brokers themselves. Quotas matter most in large multi-tenant clusters and let you enforce API limits by contract when running Kafka as a service.

### Client groups

- A client's identity is its **user principal** (the authenticated user; for unauthenticated clusters, a grouping chosen by the broker via a configurable `PrincipalBuilder`) and its **client-id** (a logical name set by the application with `client.id`).
- Quotas can be defined for `(user, client-id)`, `user` or `client-id` groups. For a connection, **the most specific matching quota applies**, and **all connections in a group share it** — e.g. a 10 MB/s produce quota for `(user="test-user", client-id="test-client")` is shared by all producer instances with that user and client-id.

### Precedence

1. matching user and client-id quotas
2. matching user and default client-id quotas
3. matching user quota
4. default user and matching client-id quotas
5. default user and default client-id quotas
6. default user quota
7. matching client-id quota
8. default client-id quota

Quota overrides and defaults are stored in the **metadata log**, read by all brokers and **effective immediately** — no rolling restart needed.

### Bandwidth quotas

A byte-rate threshold per client group, **defined per broker**: each group can publish/fetch up to X bytes/sec **per broker** before being throttled.

### Request rate quotas

The percentage of time a group may use request handler I/O threads and network threads **of each broker** within a quota window. `n%` means `n%` of one thread, out of a total of `((num.io.threads + num.network.threads) * 100)%`. Since thread counts usually follow core counts, this effectively caps a group's share of broker CPU.

### Enforcement

- Quotas are per broker rather than cluster-wide, avoiding the need to share usage state between brokers.
- On violation, the broker computes the delay needed to bring the client under quota and **immediately returns a response with that delay** (fetch responses contain no data), then **mutes the client's channel** until the delay is over. Clients honoring the delay also stop sending to that broker, so throttled clients are blocked from both sides. Even old clients that ignore the delay are throttled by the muted socket.
- Usage is measured over many small windows (e.g. 30 windows of 1 second) to detect and correct violations quickly; large windows (e.g. 10 × 30 s) cause bursts followed by long stalls.

Monitor throttling with `throttle-time` (and `byte-rate` / `request-time`) on `kafka.server:type={Produce|Fetch|Request},user=…,client-id=…`, and client-side throttle-time metrics (see [Monitoring](../monitoring/broker-and-kraft-metrics.md#quotas-connections-and-coordinators)).

## Setting quotas

By default clients have an **unlimited** quota. Quota keys: `producer_byte_rate`, `consumer_byte_rate` (bytes/sec per broker), `request_percentage` (percent of a thread), and `controller_mutation_rate` (rate of topic create/delete/alter operations, KIP-599).

```bash
# (user=user1, client-id=clientA)
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type users --entity-name user1 --entity-type clients --entity-name clientA
Updated config for entity: user-principal 'user1', client-id 'clientA'.

# user=user1
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type users --entity-name user1

# client-id=clientA
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type clients --entity-name clientA
```

Defaults use `--entity-default` instead of `--entity-name`:

```bash
# default client-id quota for user1
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type users --entity-name user1 --entity-type clients --entity-default

# default user quota
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type users --entity-default

# default client-id quota
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config 'producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200' --entity-type clients --entity-default
```

Describe:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --describe --entity-type users --entity-name user1 --entity-type clients --entity-name clientA
Configs for user-principal 'user1', client-id 'clientA' are producer_byte_rate=1024,consumer_byte_rate=2048,request_percentage=200

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --describe --entity-type users --entity-default
Quota configs for the default user-principal are consumer_byte_rate=2048.0, request_percentage=200.0, producer_byte_rate=1024.0

# all users / all (user, client) pairs
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --describe --entity-type users
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --describe --entity-type users --entity-type clients
```

Remove with `--alter --delete-config producer_byte_rate,...` on the same entity. Replication traffic during reassignments has its own throttles (`leader.replication.throttled.rate` etc.; see [Basic operations](topic-and-cluster-administration.md#limiting-bandwidth-during-data-migration)).

## Multi-tenancy

Kafka is often a central platform shared by many teams. Running such a cluster well means preventing "noisy neighbors" and meeting SLAs. Areas to address:

### User spaces (namespaces) via topic naming

Topics can be created and deleted but **not renamed** (renaming means creating a new topic, copying data and deleting the old one). So define logical spaces with a **hierarchical topic naming structure**, combined with prefixed ACLs:

- By team: `<organization>.<team>.<dataset>.<event-name>` — e.g. `acme.infosec.telemetry.logins`
- By project/product: `<project>.<product>.<event-name>` — e.g. `mobility.payments.suspicious`

Avoid putting changeable or redundant information in names (intended consumer, partition count, other settings).

Enforce naming:

- **Prefixed ACLs** (KIP-290) — e.g. team A may only create topics starting with `payments.teamA.`.
- A custom **`CreateTopicPolicy`** (KIP-108, `create.topic.policy.class.name`) for strict patterns; `AlterConfigPolicy` (`alter.config.policy.class.name`) restricts config changes.
- Deny topic creation to normal users and create topics through an external process/automation.
- Set `auto.create.topics.enable=false` on brokers (but don't rely on it alone).

### Topic configuration

Use per-topic settings such as `retention.bytes` and `retention.ms` to bound storage and meet legal requirements like GDPR (see [Storage and retention](../concepts/storage-and-retention.md)).

### Security

Encrypt traffic, authenticate clients and brokers, and — the most common multi-tenant task — **authorize** with ACLs. Hierarchical names let you grant access with **prefixed ACLs** (`--resource-pattern-type prefixed`):

```bash
# Grant permissions to user Alice
$ bin/kafka-acls.sh \
    --bootstrap-server localhost:9092 \
    --add --allow-principal User:Alice \
    --producer \
    --resource-pattern-type prefixed --topic acme.infosec.
```

This grants Alice producer rights on all `acme.infosec.*` topics. See [Authorization and ACLs](../security/authorization-and-acls.md).

### Isolation with quotas

- **Client quotas** (per user principal) apply regardless of topic, so they are an effective way to allocate resources. **Request rate quotas often matter more than bandwidth quotas**, because excessive broker CPU for request processing reduces the bandwidth a broker can serve.
- **`controller_mutation_rate`** quotas prevent floods of concurrent topic create/delete/alter operations.
- **Server quotas** limit new-connection rate, max connections per broker (`max.connections`) and per IP (`max.connections.per.ip`, `max.connections.per.ip.overrides`).

### Monitoring and metering

Track failed authentication rate, request latency, consumer lag, number of consumer groups, quota metrics and per-tenant storage — e.g. partition size via `kafka.log:type=Log,name=Size,topic=…,partition=…` — and alert when tenants approach their storage budget. See [Monitoring](../monitoring/broker-and-kraft-metrics.md).

### Inter-cluster sharing and data contracts

- Share data across clusters/regions with [MirrorMaker](geo-replication-mirrormaker.md).
- Define **data contracts** with event schemas so producers and consumers agree on formats; this is typically done with a **schema registry** (not included in Kafka; third-party implementations exist).

## Related pages

- [Authorization and ACLs](../security/authorization-and-acls.md)
- [Basic operations](topic-and-cluster-administration.md)
- [Broker configuration](../configuration/broker-configuration.md)
