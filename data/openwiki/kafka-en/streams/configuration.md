---
type: configuration-reference
title: Kafka Streams Configuration
description: How to configure a Kafka Streams application with StreamsConfig — required settings (application.id, bootstrap.servers), resiliency recommendations, processing.guarantee and exactly_once_v2, threading, state, caching, exception handlers, topology.optimization, rack-aware assignment, upgrade.from, client config prefixes (consumer./producer./admin./main.consumer./restore.consumer./global.consumer./topic.), Streams-specific client defaults and parameters Streams controls, with exact defaults.
tags: [streams, configuration, exactly-once, streamsconfig, reference]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-fa9845d6765316e55c7ef425
    resource: repo://docs/generated/streams_config.html
  - id: openwiki-source-4357ac0e69fa1ad4cc026043
    resource: repo://docs/streams/developer-guide/config-streams.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Kafka Streams Configuration

Streams is configured with a `java.util.Properties` passed to `new KafkaStreams(topology, props)`; constants are on `org.apache.kafka.streams.StreamsConfig`. Full generated table: `docs/generated/streams_config.html`.

```java
import java.util.Properties;
import org.apache.kafka.streams.StreamsConfig;

Properties settings = new Properties();
settings.put(StreamsConfig.APPLICATION_ID_CONFIG, "my-first-streams-application");
settings.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka-broker1:9092");
```

## Required

| Config | Meaning |
| --- | --- |
| `application.id` | Unique per application; **identical across all its instances**. Use alphanumerics, `.`, `-`, `_` (e.g. `hello_world-v1.0.0`). Used as the `client.id` prefix, the consumer `group.id`, the subdirectory under `state.dir`, and the prefix of internal topic names. Change it when deploying a new version unless you want to reuse existing internal topics and state. |
| `bootstrap.servers` | Kafka brokers, same as for producers/consumers. |

## Recommended for resiliency

| Parameter | Client | Default | Consider |
| --- | --- | --- | --- |
| `acks` | Producer (only for versions ≤ 2.8) | `"1"` | `"all"` (default since 3.0) |
| `replication.factor` | Streams (for brokers ≤ 2.3) | `-1` | `3` (brokers 2.4+: set broker `default.replication.factor=3`) |
| `min.insync.replicas` | Broker | `1` | `2` |
| `num.standby.replicas` | Streams | `0` | `1` |

```java
Properties streamsSettings = new Properties();
// for broker version 2.3 or older
//streamsSettings.put(StreamsConfig.REPLICATION_FACTOR_CONFIG, 3);
// for version 2.8 or older
//streamsSettings.put(StreamsConfig.producerPrefix(ProducerConfig.ACKS_CONFIG), "all");
streamsSettings.put(StreamsConfig.topicPrefix(TopicConfig.MIN_IN_SYNC_REPLICAS_CONFIG), 2);
streamsSettings.put(StreamsConfig.NUM_STANDBY_REPLICAS_CONFIG, 1);
```

Replication factor 3 lets internal topics tolerate 2 broker failures at the cost of 3× storage and some performance.

## Processing guarantee

`processing.guarantee`: `at_least_once` (**default**) or **`exactly_once_v2`** (requires brokers ≥ 2.5). `exactly_once` (EOS alpha, brokers ≥ 0.11.0) and `exactly_once_beta` are deprecated.

With exactly-once:

- `commit.interval.ms` default drops from `30000` to **`100`**.
- Consumers use `isolation.level=read_committed`, producers `enable.idempotence=true`.
- Producer `transaction.timeout.ms` defaults to **`10000`** and must be ≥ `commit.interval.ms` (else startup fails) and ≤ broker `transaction.max.timeout.ms`; raise it via `StreamsConfig.producerPrefix(ProducerConfig.TRANSACTION_TIMEOUT_CONFIG)` only if needed (higher values delay zombie fencing and can block `read_committed` readers longer). `delivery.timeout.ms` defaults to `Integer.MAX_VALUE`.
- By default EOS needs **at least three brokers**; for development lower broker `transaction.state.log.replication.factor` and `transaction.state.log.min.isr`.
- A replication factor below 3 effectively voids EOS — use **RF 3 with `min.insync.replicas=2`** for `__transaction_state`, `__consumer_offsets`, Streams internal topics and user topics.

```java
props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.EXACTLY_ONCE_V2);
```

See [Concepts: processing guarantees](core-concepts-and-architecture.md#processing-guarantees).

## Key settings and defaults

### Threads, tasks and assignment

| Config | Default | Notes |
| --- | --- | --- |
| `num.stream.threads` | `1` | Processing threads per instance. |
| `num.standby.replicas` | `0` | Standby copies of each stateful task. |
| `acceptable.recovery.lag` | `10000` | Max offsets a client may lag to be considered caught up for an active task. |
| `max.warmup.replicas` | `2` | Extra warmup standbys during rebalancing. |
| `probing.rebalance.interval.ms` | `600000` (10 min) | Probing rebalances to check warmups. |
| `task.assignor.class` | `null` (high-availability assignor) | Alternative: `org.apache.kafka.streams.processor.assignment.assignors.StickyTaskAssignor` (pre-KIP-441 default). |
| `rack.aware.assignment.strategy` | `none` | Uses `client.rack` and partition racks; tune with `rack.aware.assignment.traffic_cost` / `non_overlap_cost`. |
| `rack.aware.assignment.tags` | `""` | Client tag keys to spread standbys. |
| `group.protocol` | `classic` | `streams` enables the KIP-1071 protocol ([Running and rebalancing](running-and-rebalancing.md)). |
| `max.task.idle.ms` | `0` | Wait for data on all inputs before processing joins/merges (out-of-order trade-off). |
| `task.timeout.ms` | `300000` (5 min) | Max stall from internal errors/retries before failing. |
| `poll.ms` | `100` | Block time waiting for input. |
| `buffered.records.per.partition` | `1000` | |

### State and caching

| Config | Default | Notes |
| --- | --- | --- |
| `state.dir` | `${java.io.tmpdir}` | Must be **unique per instance** on a shared host; `<state.dir>/<application.id>/…`. Change from `/tmp` in production. |
| `statestore.cache.max.bytes` | `10485760` (10 MiB) | Record cache across all threads (`cache.max.bytes.buffering` is the older name). |
| `commit.interval.ms` | `30000` (`100` with EOS) | Commit / flush frequency. |
| `default.dsl.store` | `rocksDB` | `in_memory` alternative; or `dsl.store.suppliers.class` (default `BuiltInDslStoreSuppliers$RocksDBDslStoreSuppliers`). |
| `dsl.store.format` | `DEFAULT` | Timestamped or plain stores; `HEADERS` variants. |
| `rocksdb.config.setter` | `null` | `RocksDBConfigSetter` implementation ([memory management](state-stores-and-interactive-queries.md#memory-management)). |
| `state.cleanup.delay.ms` | `600000` (10 min) | Delete state for migrated partitions after this delay. |
| `state.cleanup.dir.max.age.ms` | `-1` | Purge old local state at startup. |
| `enable.transactional.statestores` | `false` | Buffer store writes in a transaction until commit; `statestore.uncommitted.max.bytes` (64 MiB) bounds them; `default.interactive.query.isolation.level` (`READ_UNCOMMITTED`). |
| `windowstore.changelog.additional.retention.ms` | `86400000` (1 day) | Extra changelog retention for window stores. |
| `allow.os.group.write.access` | `false` | |

### Serdes and time

| Config | Default |
| --- | --- |
| `default.key.serde` / `default.value.serde` | `null` (set them or pass Serdes explicitly) |
| `default.list.key/value.serde.type` / `.inner` | `null` |
| `windowed.inner.class.serde`, `window.size.ms` | `null` |
| `default.timestamp.extractor` | `org.apache.kafka.streams.processor.FailOnInvalidTimestamp` |

### Error handling

| Config | Default | Behaviour |
| --- | --- | --- |
| `deserialization.exception.handler` (deprecated name `default.deserialization.exception.handler`) | `LogAndFailExceptionHandler` | Return `FAIL` or `CONTINUE`; `LogAndContinueExceptionHandler` skips bad records. |
| `production.exception.handler` (deprecated `default.production.exception.handler`) | `DefaultProductionExceptionHandler` (always fails) | `FAIL`, `CONTINUE`, or `RETRY` (only for `RetriableException`; otherwise treated as `FAIL`). |
| `processing.exception.handler` | `LogAndFailProcessingExceptionHandler` | Handles exceptions thrown in processors. |
| `processing.exception.handler.global.enabled` | `false` | Also apply it to global store/KTable processing (deprecated). |
| `errors.dead.letter.queue.topic.name` | `null` | If set, the default handlers send a DLQ record to this topic. |

Example — ignore oversize records:

```java
public class IgnoreRecordTooLargeHandler implements ProductionExceptionHandler {
    public void configure(Map<String, Object> config) {}

    public ProductionExceptionHandlerResponse handle(final ErrorHandlerContext context,
                                                     final ProducerRecord<byte[], byte[]> record,
                                                     final Exception exception) {
        if (exception instanceof RecordTooLargeException) {
            return ProductionExceptionHandlerResponse.CONTINUE;
        } else {
            return ProductionExceptionHandlerResponse.FAIL;
        }
    }
}
props.put(StreamsConfig.PRODUCTION_EXCEPTION_HANDLER_CLASS_CONFIG, IgnoreRecordTooLargeHandler.class);
```

A custom deserialization handler can forward corrupt records to a quarantine/DLQ topic with its own `KafkaProducer` (side effects outside Streams' processing guarantees).

### Topology

| Config | Default | Notes |
| --- | --- | --- |
| `topology.optimization` | `none` | `all` (`StreamsConfig.OPTIMIZE`) or a list of `reuse.ktable.source.topics`, `merge.repartition.topics`, `single.store.self.join`. List specific ones in production so upgrades don't change topology unexpectedly. |
| `ensure.explicit.internal.resource.naming` | `false` | Require explicit names for all internal topics/stores ([naming](topology-naming-and-description.md)). |
| `processor.wrapper.class` | `NoOpProcessorWrapper` | Wrap every processor (logging/tracing); pass via `StreamsBuilder#new(TopologyConfig)` / `Topology#new(TopologyConfig)`. |
| `topology.description.push.enabled` | `true` | Push topology descriptions to brokers (streams groups with a topology description plugin). |
| `replication.factor` | `-1` (broker default) | For changelog and repartition topics. |
| `repartition.purge.interval.ms` | `30000` | Purge consumed records from repartition topics. |
| `upgrade.from` | `null` | Only for two-bounce upgrades to 3.4+ from versions below 3.4; remove after the second bounce. |
| `application.server` | `""` | `host:port` endpoint for interactive queries ([IQ](state-stores-and-interactive-queries.md)). |

**Optimizations need two steps** — set the config **and** pass the same properties to `build()`:

```java
Properties properties = new Properties();
properties.put(StreamsConfig.TOPOLOGY_OPTIMIZATION_CONFIG, StreamsConfig.OPTIMIZE);

// Step 2: pass properties to build() — this is required for optimizations to take effect
Topology topology = streamsBuilder.build(properties);

KafkaStreams myStream = new KafkaStreams(topology, properties);
```

### Other defaults

`client.id` (`<application.id>-<random-UUID>`), `request.timeout.ms` (`40000`), `connections.max.idle.ms` (`540000`), `receive.buffer.bytes` (`32768`), `send.buffer.bytes` (`131072`), `metrics.recording.level` (`INFO`), `log.summary.interval.ms` (`120000`), `enable.metrics.push` (`true`), `built.in.metrics.version` (`latest`), `metadata.recovery.strategy` (`rebootstrap`), `security.protocol` (`PLAINTEXT`).

## Configuring the embedded clients

Plain client keys apply to consumer, producer and admin alike:

```java
Properties streamsSettings = new Properties();
streamsSettings.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka-broker-01:9092");
streamsSettings.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, 60000);
```

Disambiguate shared names (`send.buffer.bytes`, `request.timeout.ms`, …) with prefixes:

```java
// same value for consumer, producer, and admin client
streamsSettings.put("PARAMETER_NAME", "value");
// different values
streamsSettings.put("consumer.PARAMETER_NAME", "consumer-value");
streamsSettings.put("producer.PARAMETER_NAME", "producer-value");
streamsSettings.put("admin.PARAMETER_NAME", "admin-value");
// or
streamsSettings.put(StreamsConfig.consumerPrefix("PARAMETER_NAME"), "consumer-value");
streamsSettings.put(StreamsConfig.producerPrefix("PARAMETER_NAME"), "producer-value");
streamsSettings.put(StreamsConfig.adminClientPrefix("PARAMETER_NAME"), "admin-value");
```

Per consumer type: `main.consumer.` (stream sources), `restore.consumer.` (state restoration), `global.consumer.` (global KTables):

```java
streamsSettings.put("consumer.PARAMETER_NAME", "general-consumer-value");
streamsSettings.put(StreamsConfig.restoreConsumerPrefix("PARAMETER_NAME"), "restore-consumer-value");
```

Internal repartition/changelog topic configs use `topic.`:

```java
streamsSettings.put(StreamsConfig.topicPrefix("PARAMETER_NAME"), "topic-value");
```

### Static membership

Set `group.instance.id` once per `KafkaStreams` instance (unique per instance); Streams appends the 1-based thread index (`ks-client-A` → `ks-client-A-1`, `ks-client-A-2`, …). Supported with `group.protocol=classic` and `streams`; with `streams` it requires **clients and brokers on Kafka 4.4+** (older brokers reject it and the client shuts down fatally).

### Streams defaults for client configs

| Parameter | Client | Streams default |
| --- | --- | --- |
| `auto.offset.reset` | Consumer | `earliest` |
| `linger.ms` | Producer | `100` |
| `max.poll.records` | Consumer | `1000` |
| `client.id` | — | `<application.id>-<random-UUID>` |
| `transaction.timeout.ms` (EOS) | Producer | `10000` |
| `delivery.timeout.ms` (EOS) | Producer | `Integer.MAX_VALUE` |

### Parameters controlled by Streams (user values ignored)

| Parameter | Client | Value |
| --- | --- | --- |
| `allow.auto.create.topics` | Consumer | `false` |
| `group.id` | Consumer | `application.id` |
| `enable.auto.commit` | Consumer | `false` — Streams commits explicitly |

Derived client IDs: consumer `<client.id>-StreamThread-<n>-consumer`, restore consumer `<client.id>-StreamThread-<n>-restore-consumer`, global consumer `<client.id>-global-consumer`, producer `<client.id>-StreamThread-<n>-producer` (EOS v1: `<client.id>-StreamThread-<n>-<taskId>-producer`), admin `<client.id>-admin`.

## Related pages

- [Running, scaling and rebalancing](running-and-rebalancing.md)
- [State stores, interactive queries and memory](state-stores-and-interactive-queries.md)
- [Serdes and data types](serdes-and-datatypes.md)
- [Streams metrics](../monitoring/client-metrics.md#kafka-streams-metrics)
