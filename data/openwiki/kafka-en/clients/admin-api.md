---
type: api-guide
title: Admin API
description: How to use the Kafka Admin client (org.apache.kafka.clients.admin.Admin) to manage topics, brokers, configs, ACLs and other objects, with the admin client configuration keys and their exact defaults.
tags: [admin, clients, api, configuration, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-f45042d05f4d591a882525b6
    resource: repo://docs/apis/_index.md
  - id: openwiki-source-fb16218d4cbce612e8abfc90
    resource: repo://docs/generated/admin_client_config.html
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
  - id: openwiki-source-8fc85a5d9163aa6c044434d0
    resource: repo://docs/security/security-model.md
  - id: openwiki-source-cb5db7dc8b6de446ac6791ef
    resource: repo://examples/src/main/java/kafka/examples/Utils.java
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Admin API

The Admin API "supports managing and inspecting topics, brokers, acls, and other Kafka objects". It is one of the six core Kafka APIs (Producer, Consumer, Share Consumer, Streams, Connect, Admin) and ships in the same `kafka-clients` artifact as the producer and consumer. The entry point is the interface `org.apache.kafka.clients.admin.Admin`; its configuration constants live in `org.apache.kafka.clients.admin.AdminClientConfig`.

## Dependency

```xml
<dependency>
	<groupId>org.apache.kafka</groupId>
	<artifactId>kafka-clients</artifactId>
	<version>4.3.1</version>
</dependency>
```

(The version shown is the one the documentation's snippet uses; match it to your cluster/client release.)

## Creating a client and managing topics

The `examples` module contains a complete, runnable use of the Admin client in `kafka.examples.Utils.recreateTopics(...)`. It:

1. Builds a `Properties` object with `AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG` and `AdminClientConfig.CLIENT_ID_CONFIG`.
2. Opens the client with `Admin.create(props)` in a try-with-resources block (the client must be closed).
3. Calls `admin.deleteTopics(...)` and waits with `.all().get()`, tolerating `UnknownTopicOrPartitionException`.
4. Creates topics with `admin.createTopics(List<NewTopic>)`, retrying while the broker still reports `TopicExistsException` (topic deletion is asynchronous on the broker).

```java
Properties props = new Properties();
props.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
props.put(AdminClientConfig.CLIENT_ID_CONFIG, "client-" + UUID.randomUUID());
try (Admin admin = Admin.create(props)) {
    // delete topics if present
    try {
        admin.deleteTopics(Arrays.asList(topicNames)).all().get();
    } catch (ExecutionException e) {
        if (!(e.getCause() instanceof UnknownTopicOrPartitionException)) {
            throw e;
        }
    }
    // create topics in a retry loop
    while (true) {
        // use default RF to avoid NOT_ENOUGH_REPLICAS error with minISR > 1
        short replicationFactor = -1;
        List<NewTopic> newTopics = Arrays.stream(topicNames)
            .map(name -> new NewTopic(name, numPartitions, replicationFactor))
            .collect(Collectors.toList());
        try {
            admin.createTopics(newTopics).all().get();
            break;
        } catch (ExecutionException e) {
            if (!(e.getCause() instanceof TopicExistsException)) {
                throw e;
            }
            TimeUnit.MILLISECONDS.sleep(1_000);
        }
    }
}
```

Key points:

- Admin calls are asynchronous and return result objects wrapping `KafkaFuture`s; errors surface as `ExecutionException` whose `getCause()` is the Kafka exception.
- Passing a replication factor of `-1` to `NewTopic` lets the broker apply its `default.replication.factor`.

## What else the Admin API is used for

Many operations described elsewhere in this wiki are Admin API operations, which the `bin/*.sh` tools wrap:

| Task | Admin API / tool | See |
| --- | --- | --- |
| Create, delete, describe, alter topics and partitions | `createTopics`, `deleteTopics`; `kafka-topics.sh` | [Basic operations](../operations/topic-and-cluster-administration.md) |
| Change broker/topic/client configs dynamically | `kafka-configs.sh` | [Broker configuration](../configuration/broker-configuration.md) |
| Cordon brokers or log directories before decommissioning | `cordoned.log.dirs` set "via the Admin API" (`kafka-configs.sh --alter --add-config cordoned.log.dirs=...`) | [Basic operations](../operations/topic-and-cluster-administration.md) |
| Manage ACLs | `createAcls` / `deleteAcls`, gated by ACLs on the `Cluster` resource; `kafka-acls.sh` | [Authorization and ACLs](../security/authorization-and-acls.md) |
| Create/renew/expire delegation tokens | Admin APIs or `kafka-delegation-tokens.sh` | [SASL](../security/sasl-authentication.md) |
| Manage consumer/share groups | `kafka-consumer-groups.sh`, `kafka-share-groups.sh` | [Managing groups](../operations/managing-groups.md) |

Cordoning example (broker 1):

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config cordoned.log.dirs="*" --entity-type brokers --entity-name 1
Completed updating config for broker 1.
```

### Brokers vs. controllers

An Admin client normally bootstraps from brokers through `bootstrap.servers`. It can also talk directly to the KRaft controller quorum with `bootstrap.controllers`; command-line tools expose this as `--bootstrap-controller` (for example to uncordon a log directory while its broker is offline, or to describe features with `kafka-features.sh --bootstrap-controller localhost:9093 describe`). Since Kafka 4.0, the `--zookeeper` option of admin tools has been removed; use `--bootstrap-server` (or `--bootstrap-controller`).

Tools accept client configuration (security settings, etc.) with `--command-config <file>`.

## Security notes

The Admin API is part of the control plane. The Kafka security model points out that producer/consumer traffic, the Admin API, and JMX each have distinct authentication and authorization stories, and securing one does not secure the others. Configure `security.protocol`, `ssl.*` and `sasl.*` on the admin client just as for producers and consumers (see [SSL](../security/ssl-encryption-and-authentication.md) and [SASL](../security/sasl-authentication.md)).

## Admin client configuration

The full table comes from `docs/generated/admin_client_config.html`. The most important settings:

| Config | Type | Default | Notes |
| --- | --- | --- | --- |
| `bootstrap.servers` | list | `""` | Initial host/port pairs; include more than one for resilience. Importance high. |
| `bootstrap.controllers` | list | `""` | host/port pairs of the KRaft controller quorum, for talking to controllers directly. |
| `bootstrap.resolve.timeout.ms` | long | `0` | `0` = synchronous DNS resolution at construction (failures raise `ConfigException`); positive = asynchronous resolution with this time budget, failing later with `BootstrapResolutionException` (evolving feature). |
| `client.id` | string | `""` | Logical application name included in requests. |
| `default.api.timeout.ms` | int | `60000` (1 minute) | Default timeout for client operations that do not specify one. |
| `request.timeout.ms` | int | `30000` (30 seconds) | Max wait for a response before resending or failing. |
| `retries` | int | `2147483647` | Recommended to leave at MAX_VALUE or zero and bound retrying with timeouts. |
| `retry.backoff.ms` / `retry.backoff.max.ms` | long | `100` / `1000` | Exponential backoff between retries. |
| `reconnect.backoff.ms` / `reconnect.backoff.max.ms` | long | `50` / `1000` | Backoff for reconnecting to brokers. |
| `connections.max.idle.ms` | long | `300000` (5 minutes) | Close idle connections. |
| `metadata.max.age.ms` | long | `300000` (5 minutes) | Forced metadata refresh period. |
| `metadata.recovery.strategy` | string | `rebootstrap` | `none` or `rebootstrap`: whether to repeat bootstrap when no known broker is reachable. |
| `metadata.recovery.rebootstrap.trigger.ms` | long | `300000` (5 minutes) | How long without metadata before rebootstrapping. |
| `security.protocol` | string | `PLAINTEXT` | One of `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, `SASL_SSL`. |
| `sasl.mechanism` | string | `GSSAPI` | SASL mechanism for client connections. |
| `ssl.protocol` | string | `TLSv1.3` | |
| `ssl.enabled.protocols` | list | `TLSv1.2,TLSv1.3` | |
| `ssl.keystore.type` / `ssl.truststore.type` | string | `JKS` | `JKS`, `PKCS12`, `PEM` supported. |
| `ssl.endpoint.identification.algorithm` | string | `https` | Server hostname verification. |
| `client.dns.lookup` | string | `use_all_dns_ips` | Or `resolve_canonical_bootstrap_servers_only`. |
| `socket.connection.setup.timeout.ms` / `.max.ms` | long | `10000` / `30000` | |
| `send.buffer.bytes` / `receive.buffer.bytes` | int | `131072` / `65536` | `-1` uses OS default. |
| `enable.metrics.push` | boolean | `false` | Push client metrics to the cluster when a subscription matches. |
| `metric.reporters` | list | `org.apache.kafka.common.metrics.JmxReporter` | |
| `metrics.recording.level` | string | `INFO` | `INFO`, `DEBUG`, `TRACE`. |
| `config.providers` | list | `""` | Load secrets from external sources; see [config providers](../configuration/config-providers-and-system-properties.md). |

Most of these keys are shared with the producer and consumer; see [client configuration](../configuration/client-configuration.md).

## Related pages

- [Kafka APIs overview](apis-overview.md)
- [Producer, consumer and admin client configuration](../configuration/client-configuration.md)
- [Basic operations](../operations/topic-and-cluster-administration.md)
