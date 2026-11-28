---
type: api-guide
title: Consumer
description: Using KafkaConsumer — the pull-based fetch model, the poll loop, consumer position and offset commits stored in __consumer_offsets, rebalance listeners, static membership, error handling, and the key consumer configs with their exact defaults.
tags: [consumer, clients, offsets, poll, configuration, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-3aaf8c12008d71877ad44336
    resource: repo://docs/generated/consumer_config.html
  - id: openwiki-source-53c13aa8261a2f7598093fc0
    resource: repo://docs/implementation/distribution.md
  - id: openwiki-source-ee2f8ef59177930ba5def59f
    resource: repo://examples/src/main/java/kafka/examples/Consumer.java
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Consumer

The Consumer API (`org.apache.kafka.clients.consumer.KafkaConsumer`, artifact `org.apache.kafka:kafka-clients`) reads streams of records from topics. For group membership and rebalance protocols see [Consumer groups and rebalance protocols](consumer-groups-and-rebalance.md); for queue-style consumption see [Share groups](share-groups.md).

## How consumption works

- **Pull, not push.** The consumer issues *fetch* requests to the brokers leading the partitions it wants. Each request carries the consumer's offset in the log and returns a chunk of the log starting there. The consumer controls its position and can rewind to re-consume data.
- **Long poll.** To avoid busy-waiting on an empty partition, a fetch can block until data arrives, optionally until at least `fetch.min.bytes` are available, waiting up to `fetch.max.wait.ms`.
- **Batching.** A pull consumer fetches all available records after its position (up to configurable size limits), giving good batching without extra latency.
- **Position = one integer per partition.** Within a consumer group, each partition is consumed by exactly one member at a time, so the consumed state is just the offset of the next record to read per partition. Committing it is cheap, and a consumer can deliberately rewind to an older offset (e.g. to reprocess after fixing a bug).

## Offsets and the group coordinator

The consumer tracks the maximum offset it has consumed in each partition and can **commit** offsets so it can resume after a restart.

1. Each consumer group is assigned to a broker called the **group coordinator**, based on the group name. The consumer finds it with a `FindCoordinatorRequest` to any broker, and must rediscover it if the coordinator moves.
2. On an `OffsetCommitRequest`, the coordinator appends the commit to the special **compacted** topic `__consumer_offsets`. It replies successfully only after **all replicas** of the offsets topic have received the offsets; if replication times out, the commit fails and the consumer may retry after backing off.
3. Because only the latest commit per partition matters, the brokers compact the offsets topic periodically. The coordinator also caches offsets in memory to serve offset fetches quickly.
4. If the coordinator just started or just took over a partition of the offsets topic, it may have to load the cache first; offset fetches then fail with `CoordinatorLoadInProgressException` and the consumer retries after backing off.

Commits are either **automatic** (`enable.auto.commit=true`, every `auto.commit.interval.ms`) or **manual** (`commitSync()` / `commitAsync()`). When no committed offset exists, or it is out of range, `auto.offset.reset` decides where to start.

## Example: a subscribing consumer

From `examples/src/main/java/kafka/examples/Consumer.java` (run via the [examples](examples.md)):

```java
public KafkaConsumer<Integer, String> createKafkaConsumer() {
    Properties props = new Properties();
    // bootstrap server config is required for consumer to connect to brokers
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
    props.put(ConsumerConfig.CLIENT_ID_CONFIG, "client-" + UUID.randomUUID());
    // consumer group id is required when we use subscribe(topics) for group management
    props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
    // sets static membership to improve availability (e.g. rolling restart)
    instanceId.ifPresent(id -> props.put(ConsumerConfig.GROUP_INSTANCE_ID_CONFIG, id));
    // disables auto commit when EOS is enabled, because offsets are committed with the transaction
    props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, readCommitted ? "false" : "true");
    props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, IntegerDeserializer.class);
    props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    if (readCommitted) {
        // skips ongoing and aborted transactions
        props.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
    }
    props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
    return new KafkaConsumer<>(props);
}
```

The poll loop:

```java
// the consumer instance is NOT thread safe
try (KafkaConsumer<Integer, String> consumer = createKafkaConsumer()) {
    consumer.subscribe(singleton(topic), this);   // this = ConsumerRebalanceListener
    while (!closed && remainingRecords > 0) {
        try {
            ConsumerRecords<Integer, String> records = consumer.poll(Duration.ofSeconds(1));
            for (ConsumerRecord<Integer, String> record : records) {
                // process record
            }
        } catch (AuthorizationException | UnsupportedVersionException
                 | RecordDeserializationException e) {
            // we can't recover from these exceptions
            shutdown();
        } catch (OffsetOutOfRangeException | NoOffsetForPartitionException e) {
            // invalid or no offset found without auto.reset.policy
            consumer.seekToEnd(e.partitions());
            consumer.commitSync();
        } catch (KafkaException e) {
            // log the exception and try to continue
        }
    }
}
```

Lessons encoded in the example:

- `KafkaConsumer` is **not thread-safe**; use one instance per thread.
- `poll()` also drives group membership: it updates the partition assignment and invokes the rebalance listener, then fetches from the last committed offset (or the `auto.offset.reset` policy). Call `poll()` often enough — the member is considered failed if `max.poll.interval.ms` elapses between calls (classic members also need heartbeats within `session.timeout.ms`).
- `AuthorizationException`, `UnsupportedVersionException` and `RecordDeserializationException` are fatal; `OffsetOutOfRangeException` / `NoOffsetForPartitionException` can be recovered by seeking; other `KafkaException`s can be logged and retried.

### Rebalance listener

`ConsumerRebalanceListener` has three callbacks:

| Callback | Typical use |
| --- | --- |
| `onPartitionsRevoked(Collection<TopicPartition>)` | Commit pending offsets when using manual commit (without EOS). |
| `onPartitionsAssigned(Collection<TopicPartition>)` | Load offsets from an external store or other initialization. |
| `onPartitionsLost(Collection<TopicPartition>)` | Partitions were reassigned before being revoked gracefully; do **not** commit (others likely own them), but clean up. |

### Reading transactional data

Set `isolation.level=read_committed` so `poll()` returns only committed transactional records (skipping ongoing and aborted transactions). When offsets are committed as part of a producer transaction (exactly-once), disable auto commit. See [Idempotence and transactions](../concepts/idempotence-and-transactions.md).

## Static membership

Set `group.instance.id` (`ConsumerConfig#GROUP_INSTANCE_ID_CONFIG`) to a unique, persistent value per instance to make it a static member. Restarts during deploys or config changes then do not trigger rebalances, which matters for large-state applications (e.g. Kafka Streams, where one id per `KafkaStreams` instance is enough). Requirements and behaviour:

- Brokers and clients 2.3 or later (`inter.broker.protocol.version` ≥ 2.3 for that generation of brokers); on older brokers the client throws `UnsupportedException`.
- Duplicate ids for different instances cause the broker to fence the duplicate with `org.apache.kafka.common.errors.FencedInstanceIdException`.

## Sample configuration file

`config/consumer.properties` (used with `--consumer.config` / `--command-config` in console tools):

```properties
bootstrap.servers=localhost:9092
client.id=test-consumer
isolation.level=read_uncommitted
group.id=test-consumer-group
auto.offset.reset=earliest
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
key.deserializer=org.apache.kafka.common.serialization.StringDeserializer
value.deserializer=org.apache.kafka.common.serialization.StringDeserializer
enable.auto.commit=true
auto.commit.interval.ms=5000
session.timeout.ms=30000
heartbeat.interval.ms=10000
max.poll.interval.ms=300000
fetch.min.bytes=1
fetch.max.wait.ms=500
fetch.max.bytes=52428800
max.partition.fetch.bytes=1048576
max.poll.records=500
```

## Key consumer configs and defaults

| Config | Default | Meaning |
| --- | --- | --- |
| `bootstrap.servers` | `""` | Initial brokers. |
| `key.deserializer` / `value.deserializer` | (none, required) | Classes implementing `org.apache.kafka.common.serialization.Deserializer`. |
| `group.id` | `null` | Required for `subscribe()` and Kafka-based offset storage. |
| `group.protocol` | `classic` | `classic` or `consumer` (KIP-848). |
| `auto.offset.reset` | `latest` | `latest`, `earliest`, `none`, or `by_duration:<ISO-8601 duration>` (reset to that far back from now). |
| `enable.auto.commit` | `true` | Periodic background commit. |
| `auto.commit.interval.ms` | `5000` (5 seconds) | |
| `isolation.level` | `read_uncommitted` | `read_committed` hides aborted/ongoing transactional records. |
| `max.poll.records` | `500` | Max records per `poll()`; does not change fetch behavior. |
| `max.poll.interval.ms` | `300000` (5 minutes) | Max time between `poll()` calls. |
| `session.timeout.ms` | `45000` (45 seconds) | Classic protocol failure detection. |
| `heartbeat.interval.ms` | `3000` (3 seconds) | Classic protocol heartbeats. |
| `fetch.min.bytes` | `1` | Min data per fetch response. |
| `fetch.max.wait.ms` | `500` | Max broker wait when `fetch.min.bytes` is not satisfied. |
| `fetch.max.bytes` | `52428800` (50 MiB) | Max data per fetch response. |
| `max.partition.fetch.bytes` | `1048576` (1 MiB) | Max data per partition per fetch. |
| `allow.auto.create.topics` | `true` | Only if the broker also allows `auto.create.topics.enable`. |
| `exclude.internal.topics` | `true` | Exclude internal topics from pattern subscriptions. |
| `client.rack` | `""` | Matches broker `broker.rack` for fetching from the closest replica. |
| `check.crcs` | `true` | Verify CRC32 of consumed records. |

All consumer configs (security, metrics, retries) are listed in [Client configuration](../configuration/client-configuration.md).

## Related pages

- [Consumer groups and rebalance protocols](consumer-groups-and-rebalance.md)
- [Managing groups with CLI tools](../operations/managing-groups.md) — e.g. resetting offsets with `kafka-consumer-groups.sh`
- [Message delivery semantics](../concepts/delivery-semantics.md)
- [Consumer metrics](../monitoring/client-metrics.md)
