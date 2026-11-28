---
type: concept
title: Log Compaction
description: How Kafka log compaction keeps at least the latest value per key, tombstones and delete retention, the guarantees compaction gives consumers, how the log cleaner works, and the topic and broker configs (cleanup.policy, min.cleanable.dirty.ratio, min/max.compaction.lag.ms, delete.retention.ms, log.cleaner.*) with defaults.
tags: [log-compaction, retention, storage, topics, log-cleaner, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-43671512bec22cb048c82faf
    resource: repo://docs/configuration/broker-configs.md
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
  - id: openwiki-source-f4274905cb9bcde320b4f874
    resource: repo://docs/generated/topic_config.html
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Log Compaction

Log compaction guarantees that Kafka **always retains at least the last known value for each message key** within the log of a single topic partition. Plain retention throws data away after a time or size limit, which suits independent events such as logs. Compaction instead suits **change logs of keyed, mutable data** — e.g. database table changes.

Example: a topic of user email addresses keyed by user id:

```text
123 => bill@microsoft.com
        .
123 => bill@gatesfoundation.org
        .
123 => bill@gmail.com
```

With compaction, the log keeps at least `bill@gmail.com` for key `123`, so it always contains a full snapshot of the latest value for **every** key, and downstream consumers can restore their state from the topic without the full history.

Use cases:

1. **Database change subscription** — keep caches, search clusters and Hadoop in sync, and reload a cache or restore a failed node from a complete data set.
2. **Event sourcing** — the log of changes is the application's primary store.
3. **Journaling for high availability** — log local state changes so another process can reload them on failure (e.g. stream-processing aggregations; Kafka Streams changelog topics use this).

The policy is **per topic**, so one cluster can mix time/size-retained and compacted topics.

## How a compacted log looks

- The **head** of the log is a normal Kafka log with dense, sequential offsets.
- The **tail** is compacted. Messages keep their **original offsets** — offsets never change.
- Every offset remains a valid position even if its message was removed: a read from a removed offset returns the next message that does exist (e.g. offsets 36, 37 and 38 are equivalent if only 38 remains).

### Deletes and tombstones

A message with a key and a **null payload** is a delete, called a **tombstone**. It removes any earlier message with that key. Tombstones are themselves removed after the **delete retention point**, configured by `delete.retention.ms`.

Compaction runs in the background by periodically recopying log segments. It does not block reads and can be throttled to limit I/O impact on producers and consumers.

## Guarantees

1. A consumer that stays caught up within the head of the log sees **every** message, with sequential offsets. `min.compaction.lag.ms` sets a minimum time a message stays uncompacted; `max.compaction.lag.ms` sets the maximum delay before a message becomes eligible for compaction.
2. **Ordering is always maintained** — compaction removes messages but never reorders them.
3. **The offset of a message never changes.**
4. A consumer reading from the start sees at least the final state of all records in write order, and all tombstones **if** it reaches the head within `delete.retention.ms` (default 24 hours). A consumer lagging more than that can miss delete markers.

## How the log cleaner works

The log cleaner is a pool of background threads. Each thread:

1. Picks the log with the highest ratio of log head to log tail.
2. Builds a compact summary of the last offset for each key in the head.
3. Recopies the log from start to end, dropping keys that occur later. New clean segments are swapped in immediately, so the extra disk space needed is just one segment.
4. The summary is a space-compact hash table using **exactly 24 bytes per entry** — with 8 GB of cleaner buffer, one iteration can clean about 366 GB of log head (assuming 1 kB messages).

### Segment rolling and compaction lag

The **active segment is never compacted**, even if all its messages are older than `min.compaction.lag.ms`. Records become eligible only after the segment rolls, which for a compacted topic happens at the first of:

- the segment reaches `segment.bytes`, or
- its age reaches the smaller of `segment.ms` and `max.compaction.lag.ms`.

So `max.compaction.lag.ms` both (1) forces earlier segment rolling and (2) makes rolled records eligible even if the dirty ratio is below `min.cleanable.dirty.ratio`. Without it, logs that don't exceed `min.cleanable.dirty.ratio` are not compacted. The deadline is not a hard guarantee — it depends on cleaner thread availability. Monitor `uncleanable-partitions-count`, `max-clean-time-secs` and `max-compaction-delay-secs`.

## Enabling compaction

The cleaner is enabled by default; it compacts only topics whose cleanup policy includes `compact`.

Per topic:

```bash
bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic user-emails \
  --partitions 3 --replication-factor 3 --config cleanup.policy=compact

bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name user-emails \
  --alter --add-config cleanup.policy=compact,min.compaction.lag.ms=60000
```

As the broker default for topics without their own policy (`server.properties`):

```properties
log.cleanup.policy=compact
```

`cleanup.policy` values:

- `delete` (default) — discard old segments by retention time/size.
- `compact` — keep the latest value per key.
- `delete,compact` — discard old segments by retention *and* compact the retained ones.
- empty list — infinite retention; no cleanup at all.

With tiered storage enabled, local retention limits (`log.local.retention.ms`, `log.local.retention.bytes`) still apply to local segments.

## Configuration reference

### Topic configs (server default property in parentheses)

| Topic config | Default | Notes |
| --- | --- | --- |
| `cleanup.policy` (`log.cleanup.policy`) | `delete` | `compact`, `delete`, both, or empty. |
| `delete.retention.ms` (`log.cleaner.delete.retention.ms`) | `86400000` (1 day) | Tombstone retention; also the time a consumer starting at offset 0 has to finish reading. |
| `min.cleanable.dirty.ratio` (`log.cleaner.min.cleanable.ratio`) | `0.5` | By default don't clean a log where more than 50% is already compacted. |
| `min.compaction.lag.ms` (`log.cleaner.min.compaction.lag.ms`) | `0` | Minimum time uncompacted. |
| `max.compaction.lag.ms` (`log.cleaner.max.compaction.lag.ms`) | `9223372036854775807` | Maximum time ineligible for compaction. |
| `segment.bytes` | `1073741824` (1 GiB) | |
| `segment.ms` | `604800000` (7 days) | |

### Broker cleaner configs

| Config | Default | Notes |
| --- | --- | --- |
| `log.cleaner.enable` | `true` | **Deprecated**, removed in Kafka 5.0; do not set to `false`. |
| `log.cleaner.threads` | `1` | |
| `log.cleaner.dedupe.buffer.size` | `134217728` | Total dedupe memory across cleaner threads. |
| `log.cleaner.io.buffer.size` | `524288` | |
| `log.cleaner.io.buffer.load.factor` | `0.9` | |
| `log.cleaner.io.max.bytes.per.second` | `1.7976931348623157E308` (unlimited) | Throttle read+write I/O. |
| `log.cleaner.backoff.ms` | `15000` (15 seconds) | Sleep when nothing to clean. |

`log.cleaner.threads`, `log.cleaner.io.max.bytes.per.second`, `log.cleaner.dedupe.buffer.size`, `log.cleaner.io.buffer.size`, `log.cleaner.io.buffer.load.factor` and `log.cleaner.backoff.ms` can be updated dynamically at the cluster-default level and take effect on the next cleaning iteration:

```bash
bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type brokers --entity-default \
  --alter --add-config log.cleaner.threads=2
```

## Related pages

- [Storage, log segments and retention](storage-and-retention.md)
- [Topic and group configuration](../configuration/topic-and-group-configuration.md)
- [Kafka Streams state stores](../streams/state-stores-and-interactive-queries.md)
