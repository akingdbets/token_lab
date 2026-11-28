---
type: concept
title: Storage, Log Segments and Retention
description: How Kafka stores partitions on disk — page-cache-centric persistence, batching and zero-copy sendfile, partition directories and log segment files, how writes, reads, deletes and crash recovery work, time/size retention and flush configs, and the record batch format essentials.
tags: [storage, log-segments, retention, page-cache, zero-copy, record-format, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-f4274905cb9bcde320b4f874
    resource: repo://docs/generated/topic_config.html
  - id: openwiki-source-2e1676fb398aa6228cb197e0
    resource: repo://docs/implementation/log.md
  - id: openwiki-source-ce6664c421a6343b18916cf8
    resource: repo://docs/implementation/message-format.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Storage, Log Segments and Retention

## Why Kafka relies on the filesystem

Kafka stores and caches messages on the filesystem and leans on the **OS page cache** instead of an in-process cache:

- Linear disk reads/writes are extremely fast and well optimized by the OS (read-ahead, write-behind). The docs' example: linear writes on a JBOD of six 7200rpm SATA RAID-5 disks reach ~600 MB/s, versus ~100 kB/s for random writes — a 6000× difference.
- The OS will devote all free memory to disk caching; a JVM cache would duplicate it, suffer high object overhead and GC pauses. Using the page cache gives a cache of up to 28–30 GB on a 32 GB machine without GC penalties, and it stays warm across broker restarts.
- So all data is **immediately written to the persistent log without necessarily flushing to disk** — i.e. into the page cache — and durability comes from replication.

The log is a simple append/read structure: all operations are **O(1)**, reads don't block writes or each other, and performance doesn't depend on data size. That makes it cheap to **retain data for a long time** (e.g. a week) rather than deleting it once consumed.

## Efficiency: batching and zero-copy

- The protocol is built around groups of messages (record batches): network requests, log appends and consumer fetches all move large linear chunks, eliminating many small I/Os.
- Producer, broker and consumer share one **binary format**, so chunks move between them without modification.
- The broker serves fetches with **`sendfile`** (zero-copy) straight from page cache to socket, avoiding the four copies and two system calls of a normal read/write path. Data is copied into page cache once and reused for every consumer; with caught-up consumers you may see **no disk reads at all**.
- **TLS exception:** TLS runs in user space (in-kernel `SSL_sendfile` is not supported), so `sendfile` is **not used when SSL is enabled**.
- Batches compressed by the producer stay compressed on disk and on the wire (see [Producer](../clients/producer.md#end-to-end-batch-compression)). The topic config `compression.type` (default `producer`) can keep the producer's codec or force `gzip`, `snappy`, `lz4`, `zstd` or `uncompressed`.

## On-disk layout

A topic `my-topic` with two partitions is stored as two directories, `my-topic-0` and `my-topic-1`, under the broker's `log.dirs` (or `log.dir`, default `/tmp/kafka-logs`). Each partition directory contains **segment files** named after the offset of their first message: the first is `00000000000000000000.log`, and each following file starts roughly one maximum segment size later. Each message is identified by its 64-bit **offset** in the partition.

### Writes

Appends always go to the last (active) segment, which **rolls** to a new file when it reaches `segment.bytes` (default 1 GiB) or `segment.ms` (default 7 days). Two flush parameters bound data loss on an OS crash: a message count (`flush.messages` / `log.flush.interval.messages`) and a time (`flush.ms` / `log.flush.interval.ms`). Both default to effectively infinite: Kafka **recommends not setting them** and relying on replication plus the OS's background flush.

### Reads

A read gives a 64-bit offset and a max chunk size. The broker binary-searches an in-memory range per segment to find the file, computes the file position, and returns messages from there (the offset index is sparse, controlled by `index.interval.bytes`, default 4096). Abnormally large messages can be read by retrying with a larger buffer; `max.message.bytes` bounds message size. Asking for an offset that no longer exists returns an out-of-range error, and the consumer resets according to `auto.offset.reset` (see [Consumer](../clients/consumer.md)).

### Deletes (retention)

Data is deleted **one segment at a time**, by time and/or size:

- **Time:** a segment's age is the **largest record timestamp** in it; it becomes deletable when that exceeds `retention.ms`.
- **Size:** disabled by default (`retention.bytes=-1`). When set, the oldest segments are deleted until the **partition** is within the limit (multiply by partition count for the topic total).
- If both are set, a segment eligible under either is deleted.
- The active segment is not deleted, so data in a slow-to-roll segment can outlive `retention.ms` until the segment rolls.
- Deletes use a copy-on-write segment list so reads continue on a consistent snapshot. Files are removed after `file.delete.delay.ms` (default 1 minute).

Retention is checked every `log.retention.check.interval.ms` (default 5 minutes). For key-based retention see [Log compaction](log-compaction.md); for offloading old segments see [Tiered storage](../operations/tiered-storage.md).

### Crash recovery

On startup, recovery scans the newest segment and validates each entry (size + offset within the file length and CRC32 match). On corruption the log is truncated to the last valid offset. This handles both lost blocks and garbage blocks appended when the inode size was updated before the data was written. `num.recovery.threads.per.data.dir` (default `2`) parallelizes recovery.

## Setting retention

Topic overrides take precedence over broker defaults:

```bash
# create with overrides
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic my-topic --partitions 1 \
  --replication-factor 1 --config max.message.bytes=64000 --config flush.messages=1

# change later
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my-topic \
  --alter --add-config retention.ms=86400000,retention.bytes=10737418240
```

| Topic config | Broker default property | Default |
| --- | --- | --- |
| `retention.ms` | `log.retention.ms` (falls back to `log.retention.minutes`, then `log.retention.hours`=`168`) | `604800000` (7 days); `-1` = no time limit |
| `retention.bytes` | `log.retention.bytes` | `-1` (no limit) |
| `segment.bytes` | `log.segment.bytes` | `1073741824` (1 GiB), min 1 MiB |
| `segment.ms` | `log.roll.ms` / `log.roll.hours`=`168` | `604800000` (7 days) |
| `segment.jitter.ms` | `log.roll.jitter.ms` / `log.roll.jitter.hours`=`0` | `0` |
| `segment.index.bytes` | `log.index.size.max.bytes` | `10485760` (10 MiB) |
| `index.interval.bytes` | `log.index.interval.bytes` | `4096` |
| `flush.messages` | `log.flush.interval.messages` | `9223372036854775807` |
| `flush.ms` | `log.flush.interval.ms` | `9223372036854775807` |
| `file.delete.delay.ms` | `log.segment.delete.delay.ms` | `60000` |
| `max.message.bytes` | `message.max.bytes` | `1048588` (largest record batch, after compression) |
| `message.timestamp.type` | `log.message.timestamp.type` | `CreateTime` (or `LogAppendTime`) |
| `message.timestamp.before.max.ms` / `after.max.ms` | `log.message.timestamp.*` | `9223372036854775807` / `3600000` (1 hour) |
| `compression.type` | `compression.type` | `producer` |
| `preallocate` | `log.preallocate` | `false` |
| `local.retention.ms` / `local.retention.bytes` | `log.local.retention.*` | `-2` (= use `retention.*`; tiered storage only) |

## Record batch format (essentials)

Records are always written in **record batches** (magic value 2). Batch header fields: `baseOffset`, `batchLength`, `partitionLeaderEpoch`, `magic`, `crc`, `attributes`, `lastOffsetDelta`, `baseTimestamp`, `maxTimestamp`, `producerId`, `producerEpoch`, `baseSequence`, `recordsCount`, then the records.

- `attributes` bits 0–2 give compression (0 none, 1 gzip, 2 snappy, 3 lz4, 4 zstd); bit 3 timestamp type; bit 4 transactional; bit 5 control batch; bit 6 delete-horizon set.
- Batch size on disk = `batchLength` + 12 bytes. The CRC (CRC-32C) covers everything from `attributes` to the end, excluding `partitionLeaderEpoch`.
- With compression, the compressed records follow `recordsCount`.
- **Control batches** hold a single control record (e.g. transaction commit/abort markers) that is never returned to applications.
- Each record has `length`, `attributes`, `timestampDelta`, `offsetDelta`, `key`, `value` and **headers**. Header keys are non-null, values may be null, and header order is preserved. Lengths use Protobuf-style varints.
- Compaction preserves the first and last offset/sequence numbers of a batch (to keep producer state), so empty batches can remain in a compacted log.

Full details: [Wire protocol and internals](../reference/protocol-and-internals.md).

## Related pages

- [Log compaction](log-compaction.md)
- [Tiered storage](../operations/tiered-storage.md)
- [Hardware, OS and filesystems](../operations/hardware-os-and-deployment.md)
- [Topic configuration](../configuration/topic-and-group-configuration.md)
