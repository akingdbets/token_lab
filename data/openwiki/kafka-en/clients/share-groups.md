---
type: concept-guide
title: Share Groups and the Share Consumer
description: Queue-style cooperative consumption with share groups and KafkaShareConsumer — how records are acquired under time-limited locks, the acknowledge/release/reject/renew outcomes, delivery counting, acknowledgement modes, dead-letter queues, CLI management and all share-related configs with defaults.
tags: [share-groups, share-consumer, queues, dlq, consumer, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-3aaf8c12008d71877ad44336
    resource: repo://docs/generated/consumer_config.html
  - id: openwiki-source-d1d07002e3510c7facdf9351
    resource: repo://docs/generated/group_config.html
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Share Groups and the Share Consumer

## Why share groups

Consumer groups give strong ordering and scalability by assigning each partition to a single member, but some traditional messaging (queue) workloads don't fit that model. **Share groups** are another group type, existing alongside consumer groups, for applications that need finer-grained sharing of partitions and records. Members are called **share consumers** and use `org.apache.kafka.clients.consumer.KafkaShareConsumer` (artifact `org.apache.kafka:kafka-clients`).

Fundamental differences from consumer groups:

- Share consumers **cooperatively** consume records, and a partition may be assigned to **multiple consumers**.
- The number of consumers in a share group **can exceed the number of partitions**.
- Records are **acknowledged individually** (the system is still optimized for batch processing).
- **Delivery attempts are counted**, enabling automatic handling of unprocessable records.

All share consumers in one share group subscribed to a topic cooperatively consume that topic. Different share groups consume the same topic independently. Each share consumer can set its subscription dynamically, though in practice all members usually subscribe to the same topics.

## Acquisition locks and outcomes

When a share consumer fetches, it receives available records from any matching topic-partition. Each record is **acquired** with a **time-limited acquisition lock**; while acquired, it is unavailable to other consumers in the same share group.

- Lock duration defaults to **30 seconds**, set with the group config `share.record.lock.duration.ms`. When it elapses the lock is released automatically and the record becomes available for another delivery attempt.

While holding the lock, the consumer can:

| Outcome | Effect |
| --- | --- |
| **Acknowledge** (accept) | Processing succeeded. |
| **Release** | Make the record available for another delivery attempt. |
| **Reject** | The record is unprocessable; no further delivery attempts. |
| **Renew** | Extend the delivery attempt because processing is still in progress (enabled by group config `share.renew.acknowledge.enable`, default `true`). |
| Do nothing | Lock expires and the record is released automatically. |

The cluster caps how many records per topic-partition can be acquired by a share group at once (`group.share.partition.max.record.locks`, default `2000`; per-group `share.partition.max.record.locks`). When the limit is reached, fetches return no more records until acquired records drop (e.g. as locks time out). Combined with lock expiry, this ensures delivery progresses even when consumers fail.

Records exceeding the delivery limit (`share.delivery.count.limit`, default `5`) are no longer delivered; with a DLQ configured they are written to the dead-letter topic.

## Acknowledgement and acquire modes (client configs)

| Config | Default | Meaning |
| --- | --- | --- |
| `share.acknowledgement.mode` | `implicit` | `implicit`: must **not** call `ShareConsumer.acknowledge()`; delivery is acknowledged implicitly on the next `poll()` or commit. `explicit`: must call `ShareConsumer.acknowledge()` for records. |
| `share.acquire.mode` | `BATCH_OPTIMIZED` | `batch_optimized`: a `poll()` may return more than `max.poll.records` to align with batch boundaries. `record_limit`: never exceed `max.poll.records`. |

Illustrative explicit-mode loop (types from `org.apache.kafka.clients.consumer`):

```java
Properties props = new Properties();
props.put("bootstrap.servers", "localhost:9092");
props.put("group.id", "my-share-group");
props.put("share.acknowledgement.mode", "explicit");
props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");

try (KafkaShareConsumer<String, String> consumer = new KafkaShareConsumer<>(props)) {
    consumer.subscribe(List.of("topic1"));
    while (true) {
        ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
        for (ConsumerRecord<String, String> record : records) {
            try {
                process(record);
                consumer.acknowledge(record, AcknowledgeType.ACCEPT);
            } catch (RetryableProcessingError e) {
                consumer.acknowledge(record, AcknowledgeType.RELEASE);
            } catch (Exception e) {
                consumer.acknowledge(record, AcknowledgeType.REJECT);
            }
        }
        consumer.commitSync();
    }
}
```

See the `KafkaShareConsumer` javadoc for the authoritative API.

## Dead-letter queues (DLQ)

Share-group DLQs require the `share.version` feature at level **≥ 2**:

```bash
$ bin/kafka-features.sh --bootstrap-server localhost:9092 describe | grep share.version
Feature: share.version   SupportedMinVersion: 0   SupportedMaxVersion: 2   FinalizedVersionLevel: 2   Epoch: 106
```

Set the DLQ topic for a share group:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.topic.name=dlq.gs1dlqtopic" --entity-type groups --entity-name my-share-group
Completed updating config for group my-share-group.
```

Enable automatic DLQ topic creation (cluster-wide, default disabled, KIP-1191):

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.auto.create.topics.enable=true" --entity-type brokers --entity-default
```

To use your own pre-created topic as a DLQ, mark it after creation (auto-created topics get this automatically):

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.group.enable=true" --entity-type topics --entity-name dlq.gs1dlqtopic
```

DLQ topic names must start with the prefix `errors.deadletterqueue.topic.name.prefix` (default `dlq.`; `""` removes the restriction):

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.topic.name.prefix=com.mycompany.dlq." --entity-type brokers --entity-default
```

By default DLQ records contain only metadata headers about the source record (topic, partition, offset). To also copy the source key and value:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.copy.record.enable=true" --entity-type groups --entity-name my-share-group
```

## Managing share groups

`bin/kafka-share-groups.sh` lists, describes, resets offsets of and deletes share groups (only groups without active members can be deleted):

```bash
$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --describe --group my-share-group --members
GROUP           CONSUMER-ID            HOST            CLIENT-ID              #PARTITIONS  ASSIGNMENT
my-share-group  94wrSQNmRda9Q6sk6jMO6Q /127.0.0.1      console-share-consumer 1            topic1:0
my-share-group  EfI0sha8QSKSrL_-I_zaTA /127.0.0.1      console-share-consumer 1            topic1:0
```

Both members share partition `topic1:0`. The `START-OFFSET` shown by `--describe` is the earliest offset of in-flight records being evaluated for delivery. Full CLI reference: [Managing groups](../operations/managing-groups.md).

## Configuration reference

### Group-level configs (`--entity-type groups`)

| Config | Default | Valid |
| --- | --- | --- |
| `share.record.lock.duration.ms` | `30000` (30 s) | ≥ 1000 |
| `share.delivery.count.limit` | `5` | ≥ 2 |
| `share.partition.max.record.locks` | `2000` | ≥ 100 |
| `share.auto.offset.reset` | `latest` | `latest`, `earliest`, `by_duration:<ISO-8601>` |
| `share.isolation.level` | `read_uncommitted` | `read_committed` delivers only committed transactional records |
| `share.renew.acknowledge.enable` | `true` | |
| `share.heartbeat.interval.ms` | `5000` | |
| `share.session.timeout.ms` | `45000` | |
| `share.assignment.interval.ms` | `1000` | |
| `errors.deadletterqueue.topic.name` | `""` (no DLQ) | |
| `errors.deadletterqueue.copy.record.enable` | `false` | |

### Broker configs

| Config | Default | Notes |
| --- | --- | --- |
| `group.share.record.lock.duration.ms` | `30000` | Bounded by `group.share.min/max.record.lock.duration.ms` (`15000` / `60000`). |
| `group.share.delivery.count.limit` | `5` | Valid 2–10; group values bounded by `group.share.min/max.delivery.count.limit` (`2` / `10`). |
| `group.share.partition.max.record.locks` | `2000` | Group values bounded by `group.share.min/max.partition.max.record.locks` (`100` / `4000`). |
| `group.share.max.size` | `200` | Max members per share group (1–1000). |
| `group.share.assignors` | `simple` | Single entry used by all groups. |
| `group.share.heartbeat.interval.ms` / `group.share.session.timeout.ms` | `5000` / `45000` | |
| `group.share.max.share.sessions` | `2000` | Per broker. |
| `share.coordinator.state.topic.num.partitions` | `50` | Share-group state topic; don't change after deployment. |
| `share.coordinator.state.topic.replication.factor` | `3` | Topic creation fails until the cluster has this many brokers. |
| `share.coordinator.state.topic.min.isr` | `2` | |
| `share.coordinator.threads` | `1` | |
| `errors.deadletterqueue.auto.create.topics.enable` | `false` | Cluster-wide dynamic. |
| `errors.deadletterqueue.topic.name.prefix` | `dlq.` | Cluster-wide dynamic. |

## Related pages

- [Consumer groups and rebalance protocols](consumer-groups-and-rebalance.md)
- [Managing consumer and share groups](../operations/managing-groups.md)
- [Share group monitoring](../monitoring/broker-and-kraft-metrics.md)
