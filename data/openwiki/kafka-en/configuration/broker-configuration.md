---
type: configuration-reference
title: Broker and Controller Configuration
description: The essential KRaft broker and controller settings, the sample server/broker/controller properties files shipped in config/, key broker defaults (networking, threads, internal topics, logs), and how to change broker configs dynamically with kafka-configs.sh including precedence rules, SSL keystore/truststore rotation, thread pools and listeners.
tags: [configuration, broker, controller, kraft, dynamic-config, kafka-configs]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-98fcaee386917e9bff205032
    resource: repo://config/server.properties
  - id: openwiki-source-43671512bec22cb048c82faf
    resource: repo://docs/configuration/broker-configs.md
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Broker and Controller Configuration

Kafka servers run in **KRaft mode** and are configured with a properties file (traditionally `server.properties`). The full generated reference is `docs/generated/kafka_config.html` (also documented in the Scala class `kafka.server.KafkaConfig`).

## Essential configs

| Config | Default | Purpose |
| --- | --- | --- |
| `node.id` | (required) | Node ID for the roles this process plays. |
| `log.dirs` | `null` → falls back to `log.dir` = `/tmp/kafka-logs` | Data directories (comma-separated). |
| `process.roles` | (required) | `broker`, `controller`, or `broker,controller` (combined). |
| `controller.quorum.bootstrap.servers` | `""` | `host:port` endpoints used to bootstrap the cluster metadata quorum. |
| `controller.listener.names` | (required) | Listener names used by the controller. |

Also commonly set: `listeners` (default `PLAINTEXT://:9092`), `advertised.listeners`, `listener.security.protocol.map`, `inter.broker.listener.name`. See [KRaft cluster setup](../operations/kraft-cluster-setup.md) and [listeners](../security/listeners-and-security-overview.md).

`broker.id` (default `-1`) is **deprecated and will be removed in Kafka 5.0** — use `node.id`. `controller.quorum.voters` is the older static way to define voters; prefer `controller.quorum.bootstrap.servers`.

## Sample properties files

`config/server.properties` — a combined broker + controller node for development:

```properties
process.roles=broker,controller
node.id=1
controller.quorum.bootstrap.servers=localhost:9093
listeners=PLAINTEXT://:9092,CONTROLLER://:9093
inter.broker.listener.name=PLAINTEXT
advertised.listeners=PLAINTEXT://localhost:9092,CONTROLLER://localhost:9093
controller.listener.names=CONTROLLER
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT,SASL_SSL:SASL_SSL
num.network.threads=3
num.io.threads=8
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600
log.dirs=/tmp/kraft-combined-logs
num.partitions=1
num.recovery.threads.per.data.dir=2
offsets.topic.replication.factor=1
share.coordinator.state.topic.replication.factor=1
share.coordinator.state.topic.min.isr=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
log.retention.hours=168
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000
```

`config/broker.properties` (broker-only, `node.id=2`, `listeners=PLAINTEXT://localhost:9092`, `log.dirs=/tmp/kraft-broker-logs`) and `config/controller.properties` (controller-only, `node.id=1`, `listeners=CONTROLLER://:9093`, `advertised.listeners=CONTROLLER://localhost:9093`, `log.dirs=/tmp/kraft-controller-logs`) show the split-role layout. Note the internal-topic replication factors of `1` — fine for one node, but production clusters should use the defaults (`3`, with min ISR `2`).

## Key broker defaults

| Area | Config | Default |
| --- | --- | --- |
| Network | `listeners` | `PLAINTEXT://:9092` |
| | `listener.security.protocol.map` | `SASL_SSL:SASL_SSL,PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT` |
| | `socket.send.buffer.bytes` / `socket.receive.buffer.bytes` | `102400` |
| | `socket.request.max.bytes` | `104857600` (100 MiB) |
| | `queued.max.requests` | `500` |
| | `max.connections` / `max.connections.per.ip` | `2147483647` |
| Threads | `num.network.threads` | `3` |
| | `num.io.threads` | `8` |
| | `background.threads` | `10` |
| | `num.replica.fetchers` | `1` |
| | `num.recovery.threads.per.data.dir` | `2` |
| Topics | `num.partitions` | `1` |
| | `default.replication.factor` | `1` |
| | `auto.create.topics.enable` | `true` |
| | `delete.topic.enable` | `true` |
| | `min.insync.replicas` | `1` |
| Internal topics | `offsets.topic.replication.factor` | `3` |
| | `transaction.state.log.replication.factor` / `.min.isr` | `3` / `2` |
| | `share.coordinator.state.topic.replication.factor` / `.min.isr` | `3` / `2` |
| Logs | `log.retention.hours` | `168` |
| | `log.segment.bytes` | `1073741824` |
| | `log.retention.check.interval.ms` | `300000` |
| | `message.max.bytes` | `1048588` |
| KRaft | `metadata.log.dir` | `null` (first log dir) |
| | `controller.quorum.fetch.timeout.ms` | `2000` |
| | `controller.quorum.election.timeout.ms` | `1000` |
| | `controller.quorum.auto.join.enable` | `false` |
| | `initial.broker.registration.timeout.ms` | `60000` |
| | `broker.session.timeout.ms` / `broker.heartbeat.interval.ms` | `9000` / `2000` |

Topic-level defaults are explained in [Storage and retention](../concepts/storage-and-retention.md) and [Log compaction](../concepts/log-compaction.md); group coordinator configs in [Consumer groups](../clients/consumer-groups-and-rebalance.md).

## Updating broker configs dynamically

Since Kafka 1.1 some broker configs can change without restart. Each config's **update mode** says how:

- `read-only` — requires a broker restart.
- `per-broker` — may be updated dynamically for each broker.
- `cluster-wide` — may be updated dynamically as a cluster-wide default (and per broker for testing).

```bash
# alter for broker 0
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-name 0 --alter --add-config log.cleaner.threads=2

# describe dynamic configs of broker 0
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-name 0 --describe

# remove an override (revert to static/default)
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-name 0 --alter --delete-config log.cleaner.threads

# cluster-wide default for all brokers
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-default --alter --add-config log.cleaner.threads=2
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-default --describe

# change a logger level on broker 0
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --broker-logger 0 --add-config org.apache.kafka.server.quota.ClientQuotaManager\$ThrottledChannelReaper=DEBUG --alter
```

For controllers, use `--bootstrap-controller` instead of `--bootstrap-server` (see [ZooKeeper to KRaft differences](../operations/zookeeper-to-kraft-migration.md)).

### Precedence

1. Dynamic per-broker config stored in the metadata log
2. Dynamic cluster-wide default stored in the metadata log
3. Static config from `server.properties`
4. Kafka default

### What can be changed dynamically

- **SSL keystore of a listener** (per broker, one request): `ssl.keystore.type`, `ssl.keystore.location`, `ssl.keystore.password`, `ssl.key.password`, prefixed with `listener.name.{listenerName}.`. For the inter-broker listener the new keystore must be trusted by that listener's truststore; sign new certificates with the same CA to avoid client auth failures.
- **SSL truststore of a listener** (per broker): `ssl.truststore.type`, `ssl.truststore.location`, `ssl.truststore.password` with the listener prefix. For the inter-broker listener the existing keystore must be trusted by the new truststore; removing CA certs can break client authentication.
- **Default topic configs** (cluster default), applied to topics without an override: `log.segment.bytes`, `log.roll.ms`, `log.roll.hours`, `log.roll.jitter.ms`, `log.roll.jitter.hours`, `log.index.size.max.bytes`, `log.flush.interval.messages`, `log.flush.interval.ms`, `log.retention.bytes`, `log.retention.ms`, `log.retention.minutes`, `log.retention.hours`, `log.index.interval.bytes`, `log.cleaner.delete.retention.ms`, `log.cleaner.min.compaction.lag.ms`, `log.cleaner.max.compaction.lag.ms`, `log.cleaner.min.cleanable.ratio`, `log.cleanup.policy`, `log.segment.delete.delay.ms`, `unclean.leader.election.enable`, `min.insync.replicas`, `max.message.bytes`, `compression.type`, `log.preallocate`, `log.message.timestamp.type`.
- **Log cleaner** (cluster default, next cleaning iteration): `log.cleaner.threads`, `log.cleaner.io.max.bytes.per.second`, `log.cleaner.dedupe.buffer.size`, `log.cleaner.io.buffer.size`, `log.cleaner.io.buffer.load.factor`, `log.cleaner.backoff.ms`.
- **Thread pools** (cluster default, limited to `currentSize / 2` … `currentSize * 2` per update): `num.network.threads`, `num.io.threads`, `num.replica.fetchers`, `num.recovery.threads.per.data.dir`, `log.cleaner.threads`, `background.threads`, `remote.log.reader.threads`, `remote.log.manager.copier.thread.pool.size`, `remote.log.manager.expiration.thread.pool.size`, `remote.log.manager.follower.thread.pool.size`.
- **Connection quotas** (cluster default, new connections): `max.connections.per.ip`, `max.connections.per.ip.overrides`.
- **Listeners** (per broker): `listeners`, `advertised.listeners`, `listener.security.protocol.map`, plus the new listener's security configs with prefix `listener.name.{listenerName}.` (SASL listeners need `sasl.jaas.config` with listener and mechanism prefix). The inter-broker listener is set statically with `inter.broker.listener.name` or `security.inter.broker.protocol`; to move it, add the new listener everywhere, then do a rolling restart with the new `inter.broker.listener.name`.

Example — rotate a listener keystore on broker 0:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-name 0 --alter \
  --add-config listener.name.ssl.ssl.keystore.location=/var/private/ssl/kafka.server.keystore.jks,listener.name.ssl.ssl.keystore.password=test1234,listener.name.ssl.ssl.key.password=test1234
```

## Related pages

- [KRaft cluster setup](../operations/kraft-cluster-setup.md)
- [Security overview and listeners](../security/listeners-and-security-overview.md)
- [Topic and group configuration](topic-and-group-configuration.md)
- [Configuration providers](config-providers-and-system-properties.md) — keep passwords out of properties files
