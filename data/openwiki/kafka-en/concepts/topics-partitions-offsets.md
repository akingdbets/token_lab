---
type: concept
title: Topics, Partitions, Offsets and Records
description: Kafka's core data model for users — events/records with key, value, timestamp and headers; topics as durable multi-producer multi-subscriber logs; partitions for scale and per-partition ordering; offsets as consumer positions; and the practical consequences of choosing and changing partition counts.
tags: [topics, partitions, offsets, records, ordering, data-model]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
  - id: openwiki-source-382bc16e26147a97f6cd7008
    resource: repo://docs/getting-started/introduction.md
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Topics, Partitions, Offsets and Records

## Events (records, messages)

An **event** records the fact that "something happened". The docs also call it a **record** or **message**. Every read and write in Kafka is in the form of events. An event has:

- a **key** (e.g. `"Alice"`),
- a **value** (e.g. `"Made a payment of $200 to Bob"`),
- a **timestamp** (e.g. `"Jun. 25, 2020 at 2:06 p.m."`),
- optional **headers** (metadata key/value pairs; keys are non-null, values may be null, order is preserved).

On the wire and on disk, records are always grouped into **record batches** (see [Storage and retention](storage-and-retention.md#record-batch-format-essentials)). A record's timestamp is either the producer's create time or the broker's append time, chosen by `message.timestamp.type` (`CreateTime` default, or `LogAppendTime`).

## Producers and consumers are decoupled

**Producers** publish events; **consumers** subscribe to and process them. They are fully decoupled — producers never wait for consumers — which is key to Kafka's scalability.

## Topics

Events are organized and durably stored in **topics** — loosely, a folder in a filesystem whose files are the events (e.g. a topic named `payments`).

- Topics are always **multi-producer and multi-subscriber**: zero or more producers and zero or more consumers.
- Events are **not deleted after consumption**. They can be read as often as needed; a per-topic retention setting decides how long to keep them. Performance is effectively constant with respect to data size, so long retention is fine (see [Storage and retention](storage-and-retention.md) and [Log compaction](log-compaction.md)).

Create, inspect and delete topics with `bin/kafka-topics.sh`:

```bash
$ bin/kafka-topics.sh --create --topic quickstart-events --bootstrap-server localhost:9092

$ bin/kafka-topics.sh --describe --topic quickstart-events --bootstrap-server localhost:9092
Topic: quickstart-events        TopicId: NPmZHyhbR9y00wMglMH2sg PartitionCount: 1       ReplicationFactor: 1	Configs:
Topic: quickstart-events Partition: 0    Leader: 0   Replicas: 0 Isr: 0

$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic my_topic_name \
    --partitions 20 --replication-factor 3 --config x=y

$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic my_topic_name
```

Topics can also be **auto-created** when data is first published to a non-existent topic (`auto.create.topics.enable`, default `true`; consumers additionally need `allow.auto.create.topics=true`, which is the default). Auto-created topics get `num.partitions` (default `1`) and `default.replication.factor` (default `1`) — tune these if you rely on auto-creation.

### Topic name limits

Each partition lives in its own folder named `<topic>-<partition id>` under the log directory. Since folder names are limited to 255 characters and partition counts are assumed to stay below 100,000, **topic names cannot be longer than 249 characters**.

## Partitions

A topic is **partitioned** — spread over "buckets" on different brokers — so clients can read and write to many brokers in parallel.

- A new event is **appended to one partition**.
- **Events with the same key are written to the same partition** (default partitioner: hash of the key), and **any consumer of a topic-partition reads its events in exactly the order they were written**. Ordering is guaranteed *per partition*, not across a topic.
- Producers choose the partition: by key hash, round-robin/sticky when there is no key, an explicit partition, or a custom `Partitioner` (see [Producer](../clients/producer.md#choosing-a-partition)).

Partition count matters:

- Each partition must fit entirely on a single server, so 20 partitions spread data and load over at most 20 servers (not counting replicas).
- Partition count caps **consumer parallelism**: within a consumer group each partition is consumed by exactly one member (share groups relax this; see [Share groups](../clients/share-groups.md)).

### Changing the partition count

```bash
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --alter --topic my_topic_name \
    --partitions 40
```

- **Kafka does not support reducing the number of partitions.**
- **Key distribution changes:** with `hash(key) % number_of_partitions`, keys can map to different partitions after the increase; existing data is not redistributed, so per-key ordering across the change is not preserved.
- **Possible data loss with `auto.offset.reset=latest`:** consumers may not see new partitions immediately and skip records produced in the gap. Prefer `auto.offset.reset=by_duration:<duration>` sized to the discovery latency — `PT5S` (or slightly above `group.consumer.heartbeat.interval.ms`, default 5000 ms) for the `consumer` group protocol, `PT6M` (slightly above `metadata.max.age.ms`, default 300000 ms) for `classic`. `by_duration` replays up to that much backlog for partitions without committed offsets and requires client/broker clock synchronization.
- **Metadata delay:** clients learn about new partitions on metadata refresh (`metadata.max.age.ms`).
- **Never** add partitions to internal topics: `__consumer_offsets`, `__transaction_state`, `__share_group_state`, `__cluster_metadata`.

## Offsets

Each record in a partition has a unique, monotonically increasing 64-bit **offset**. Offsets never change, even after compaction.

- A consumer's **position** in a partition is just the offset of the next record to read. Consumers control it: they can rewind to re-consume or skip ahead.
- Consumer groups **commit** offsets to the internal compacted topic `__consumer_offsets` so another member can resume after failure (see [Consumer](../clients/consumer.md#offsets-and-the-group-coordinator)).
- Because data isn't deleted on read, many consumers and groups can read the same topic independently:

```bash
$ bin/kafka-console-consumer.sh --topic quickstart-events --from-beginning --bootstrap-server localhost:9092
This is my first event
This is my second event
```

Consumer lag (log end offset minus committed offset) is shown by `kafka-consumer-groups.sh --describe` (see [Managing groups](../operations/managing-groups.md)).

## Replication

Every topic can be **replicated** — even across regions — so several brokers hold a copy of each partition. A common production setting is **replication factor 3**. Replication is per topic-partition; with replication factor 3, up to 2 servers can fail before you lose access to data, and the docs recommend 2 or 3 so machines can be bounced without interrupting consumption. See [Replication](replication.md).

## Related pages

- [Producer](../clients/producer.md) and [Consumer](../clients/consumer.md)
- [Replication, ISR and leader election](replication.md)
- [Basic operations](../operations/topic-and-cluster-administration.md)
- [Topic configuration](../configuration/topic-and-group-configuration.md)
