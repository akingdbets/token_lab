---
type: configuration-reference
title: Producer, Consumer and Admin Client Configuration
description: How Kafka Java client configuration works and a consolidated reference of producer, consumer/share consumer and admin client configs with exact defaults — connection and bootstrap, retries and timeouts, metadata recovery, security, metrics and client-specific settings — including the places where the same key has different defaults per client.
tags: [configuration, producer, consumer, admin, clients, reference]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-c0219d66466d8c4fa7aafa17
    resource: repo://docs/configuration/admin-configs.md
  - id: openwiki-source-c32915851278cdd7a1b19065
    resource: repo://docs/configuration/consumer-configs.md
  - id: openwiki-source-50a2f7726fb8582e8218fb05
    resource: repo://docs/configuration/producer-configs.md
  - id: openwiki-source-fb16218d4cbce612e8abfc90
    resource: repo://docs/generated/admin_client_config.html
  - id: openwiki-source-3aaf8c12008d71877ad44336
    resource: repo://docs/generated/consumer_config.html
  - id: openwiki-source-42c50a2642f2eaaa407a11fe
    resource: repo://docs/generated/producer_config.html
  - id: openwiki-source-fbbc17e7aea2c678c3c8a51a
    resource: repo://docs/security/encryption-and-authentication-using-ssl.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Producer, Consumer and Admin Client Configuration

Kafka's Java clients are configured with a `java.util.Properties` (or `Map`) passed to the constructor — `new KafkaProducer<>(props)`, `new KafkaConsumer<>(props)`, `new KafkaShareConsumer<>(props)`, `Admin.create(props)`. Constants live in `ProducerConfig`, `ConsumerConfig` and `AdminClientConfig`. Command-line tools take the same keys from a file passed with `--command-config` (or `--producer.config` / `--consumer.config` for console tools).

The authoritative tables are generated into `docs/generated/producer_config.html`, `docs/generated/consumer_config.html` (consumer **and** share consumer) and `docs/generated/admin_client_config.html`. Secrets can be externalized with [config providers](config-providers-and-system-properties.md) via `config.providers`.

## Common configs (all three clients)

| Config | Producer | Consumer | Admin | Notes |
| --- | --- | --- | --- | --- |
| `bootstrap.servers` | — | — | `""` | Required. Initial `host:port` list; include several brokers. |
| `bootstrap.resolve.timeout.ms` | `0` | `0` | `0` | `0` = synchronous DNS at construction (fails with `ConfigException`); >0 = async resolution, failing later with `BootstrapResolutionException`. |
| `client.id` | `""` | `""` | `""` | Logical application name in server request logs and quotas. |
| `client.dns.lookup` | `use_all_dns_ips` | `use_all_dns_ips` | `use_all_dns_ips` | Or `resolve_canonical_bootstrap_servers_only`. |
| `request.timeout.ms` | `30000` | `30000` | `30000` | |
| `connections.max.idle.ms` | `540000` (9 min) | `540000` (9 min) | `300000` (5 min) | |
| `send.buffer.bytes` | `131072` | `131072` | `131072` | `-1` = OS default. |
| `receive.buffer.bytes` | `32768` | `65536` | `65536` | |
| `reconnect.backoff.ms` / `.max.ms` | `50` / `1000` | `50` / `1000` | `50` / `1000` | Exponential with jitter. |
| `retry.backoff.ms` / `.max.ms` | `100` / `1000` | `100` / `1000` | `100` / `1000` | |
| `socket.connection.setup.timeout.ms` / `.max.ms` | `10000` / `30000` | same | same | |
| `metadata.max.age.ms` | `300000` | `300000` | `300000` | Forced metadata refresh. |
| `metadata.recovery.strategy` | `rebootstrap` | `rebootstrap` | `rebootstrap` | `none` fails when no known broker is reachable. |
| `metadata.recovery.rebootstrap.trigger.ms` | `300000` | `300000` | `300000` | |
| `metadata.cluster.check.enable` | `true` | `true` | `true` | Send cluster/node info to detect misrouted connections. |
| `security.protocol` | `PLAINTEXT` | `PLAINTEXT` | `PLAINTEXT` | `SSL`, `SASL_PLAINTEXT`, `SASL_SSL`. |
| `enable.metrics.push` | `true` | `true` | `false` | Push client metrics when a cluster subscription matches. |
| `metric.reporters` | `org.apache.kafka.common.metrics.JmxReporter` | same | same | |
| `metrics.recording.level` | `INFO` | `INFO` | `INFO` | `INFO`, `DEBUG`, `TRACE`. |
| `metrics.num.samples` / `metrics.sample.window.ms` | `2` / `30000` | same | same | |
| `config.providers` | `""` | `""` | `""` | |
| `security.providers` | `null` | `null` | `null` | `SecurityProviderCreator` classes. |

Security keys (`ssl.*`, `sasl.*`) are identical across clients, e.g. `ssl.protocol=TLSv1.3`, `ssl.enabled.protocols=TLSv1.2,TLSv1.3`, `ssl.keystore.type=JKS`, `ssl.truststore.type=JKS`, `ssl.endpoint.identification.algorithm=https`, `sasl.mechanism=GSSAPI`. See [SSL](../security/ssl-encryption-and-authentication.md) and [SASL](../security/sasl-authentication.md).

Example client security file (`client-ssl.properties`) used by tools:

```properties
security.protocol=SSL
ssl.truststore.location=/var/private/ssl/client.truststore.jks
ssl.truststore.password=test1234
```

```bash
$ bin/kafka-console-producer.sh --bootstrap-server localhost:9093 --topic test --command-config client-ssl.properties
```

## Producer-specific configs

| Config | Default |
| --- | --- |
| `key.serializer` / `value.serializer` | required |
| `acks` | `all` |
| `enable.idempotence` | `true` |
| `retries` | `2147483647` |
| `delivery.timeout.ms` | `120000` |
| `max.in.flight.requests.per.connection` | `5` |
| `batch.size` | `16384` |
| `linger.ms` | `5` (was `0` before 4.0) |
| `buffer.memory` | `33554432` |
| `max.block.ms` | `60000` |
| `max.request.size` | `1048576` |
| `compression.type` | `none` (`gzip`, `snappy`, `lz4`, `zstd`) |
| `compression.gzip.level` / `compression.lz4.level` / `compression.zstd.level` | `-1` / `9` / `3` |
| `partitioner.class` | `null` |
| `partitioner.ignore.keys` | `false` |
| `partitioner.adaptive.partitioning.enable` | `true` |
| `partitioner.availability.timeout.ms` | `0` |
| `partitioner.rack.aware` | `false` |
| `client.rack` | `""` |
| `metadata.max.idle.ms` | `300000` |
| `interceptor.classes` | `""` |
| `transactional.id` | `null` |
| `transaction.timeout.ms` | `60000` |
| `transaction.two.phase.commit.enable` | `false` |

Details: [Producer](../clients/producer.md).

## Consumer-specific configs

| Config | Default |
| --- | --- |
| `key.deserializer` / `value.deserializer` | required |
| `group.id` | `null` |
| `group.protocol` | `classic` (`consumer` for KIP-848) |
| `group.remote.assignor` | `null` |
| `group.instance.id` | `null` |
| `heartbeat.interval.ms` | `3000` (classic only) |
| `session.timeout.ms` | `45000` (classic only) |
| `partition.assignment.strategy` | `RangeAssignor`, `CooperativeStickyAssignor` (classic only) |
| `max.poll.interval.ms` | `300000` |
| `max.poll.records` | `500` |
| `auto.offset.reset` | `latest` (`earliest`, `none`, `by_duration:<ISO-8601>`) |
| `enable.auto.commit` | `true` |
| `auto.commit.interval.ms` | `5000` |
| `isolation.level` | `read_uncommitted` |
| `fetch.min.bytes` | `1` |
| `fetch.max.wait.ms` | `500` |
| `fetch.max.bytes` | `52428800` |
| `max.partition.fetch.bytes` | `1048576` |
| `default.api.timeout.ms` | `60000` |
| `allow.auto.create.topics` | `true` |
| `exclude.internal.topics` | `true` |
| `check.crcs` | `true` |
| `client.rack` | `""` |
| `interceptor.classes` | `""` |

Share consumer only: `share.acknowledgement.mode` (`implicit`) and `share.acquire.mode` (`BATCH_OPTIMIZED`). Details: [Consumer](../clients/consumer.md), [Consumer groups](../clients/consumer-groups-and-rebalance.md), [Share groups](../clients/share-groups.md).

## Admin-specific configs

| Config | Default |
| --- | --- |
| `bootstrap.controllers` | `""` — talk directly to the KRaft controller quorum |
| `default.api.timeout.ms` | `60000` |
| `retries` | `2147483647` |

Details: [Admin API](../clients/admin-api.md).

## Tips

- **Timeouts compose:** for producers keep `delivery.timeout.ms` ≥ `request.timeout.ms` + `linger.ms`; for consumers `max.poll.interval.ms` bounds processing time between polls.
- **Infinite retries, bounded time:** the docs recommend leaving `retries` at its maximum (or zero) and controlling retry duration with timeouts.
- **Rebootstrapping** (`metadata.recovery.strategy=rebootstrap`) helps clients that talk to brokers rarely, when all known brokers may have changed.
- Kafka Streams and Connect pass these keys through to their embedded clients using prefixes (`producer.`, `consumer.`, `admin.`, …) — see [Streams configuration](../streams/configuration.md) and [Connect workers](../connect/overview-and-running.md).

## Related pages

- [Producer](../clients/producer.md), [Consumer](../clients/consumer.md), [Admin API](../clients/admin-api.md)
- [Broker configuration](broker-configuration.md)
- [Client metrics](../monitoring/client-metrics.md)
