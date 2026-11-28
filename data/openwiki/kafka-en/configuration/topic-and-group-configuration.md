---
type: configuration-reference
title: Topic and Group Configuration
description: How per-topic config overrides relate to broker defaults and how to set, describe and remove them with kafka-topics.sh and kafka-configs.sh, a full table of topic configs with defaults and server default properties, and the dynamic group-level configs for consumer, share and streams groups.
tags: [configuration, topics, groups, kafka-configs, retention, reference]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-1a722a7d3b85933782ce7873
    resource: repo://docs/configuration/topic-configs.md
  - id: openwiki-source-d1d07002e3510c7facdf9351
    resource: repo://docs/generated/group_config.html
  - id: openwiki-source-f4274905cb9bcde320b4f874
    resource: repo://docs/generated/topic_config.html
  - id: openwiki-source-8e13573fed29070c5b35d6db
    resource: repo://docs/streams/developer-guide/streams-rebalance-protocol.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Topic and Group Configuration

## Topic configs: server default vs. per-topic override

Topic configs have a **server default** (a broker property, the "Server Default Property") and an optional **per-topic override**. The server default only applies to topics without an explicit override. Broker defaults can themselves be changed dynamically at cluster level (see [Broker configuration](broker-configuration.md#what-can-be-changed-dynamically)).

Set overrides at creation time with `--config`:

```bash
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic my-topic --partitions 1 \
  --replication-factor 1 --config max.message.bytes=64000 --config flush.messages=1
```

Change, describe, remove later with `kafka-configs.sh`:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my-topic \
  --alter --add-config max.message.bytes=128000

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my-topic --describe

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my-topic \
  --alter --delete-config max.message.bytes
```

From Java, the [Admin API](../clients/admin-api.md) can pass configs in `NewTopic` and alter them later.

## Topic config reference

Defaults are from `docs/generated/topic_config.html`. "—" means no server default property.

### Retention, segments and cleanup

| Topic config | Default | Server default property |
| --- | --- | --- |
| `cleanup.policy` | `delete` | `log.cleanup.policy` |
| `retention.ms` | `604800000` (7 days) | `log.retention.ms` |
| `retention.bytes` | `-1` | `log.retention.bytes` |
| `segment.bytes` | `1073741824` (1 GiB) | `log.segment.bytes` |
| `segment.ms` | `604800000` (7 days) | `log.roll.ms` |
| `segment.jitter.ms` | `0` | `log.roll.jitter.ms` |
| `segment.index.bytes` | `10485760` (10 MiB) | `log.index.size.max.bytes` |
| `index.interval.bytes` | `4096` | `log.index.interval.bytes` |
| `file.delete.delay.ms` | `60000` | `log.segment.delete.delay.ms` |
| `preallocate` | `false` | `log.preallocate` |
| `flush.messages` | `9223372036854775807` | `log.flush.interval.messages` |
| `flush.ms` | `9223372036854775807` | `log.flush.interval.ms` |

### Compaction

| Topic config | Default | Server default property |
| --- | --- | --- |
| `delete.retention.ms` | `86400000` (1 day) | `log.cleaner.delete.retention.ms` |
| `min.cleanable.dirty.ratio` | `0.5` | `log.cleaner.min.cleanable.ratio` |
| `min.compaction.lag.ms` | `0` | `log.cleaner.min.compaction.lag.ms` |
| `max.compaction.lag.ms` | `9223372036854775807` | `log.cleaner.max.compaction.lag.ms` |

### Messages and compression

| Topic config | Default | Server default property |
| --- | --- | --- |
| `max.message.bytes` | `1048588` | `message.max.bytes` |
| `max.decompressed.message.bytes` | `2147483639` | `max.decompressed.message.bytes` |
| `compression.type` | `producer` | `compression.type` |
| `compression.gzip.level` / `compression.lz4.level` / `compression.zstd.level` | `-1` / `9` / `3` | same names |
| `message.timestamp.type` | `CreateTime` | `log.message.timestamp.type` |
| `message.timestamp.before.max.ms` | `9223372036854775807` | `log.message.timestamp.before.max.ms` |
| `message.timestamp.after.max.ms` | `3600000` (1 hour) | `log.message.timestamp.after.max.ms` |

`max.decompressed.message.bytes` bounds the **decompressed** size of a single record (unlike `max.message.bytes`, which bounds the compressed batch); larger records are rejected with `InvalidRecordException`. It is enforced on produce validation of compressed batches, during compaction and for timestamp offset lookups.

### Replication and availability

| Topic config | Default | Server default property |
| --- | --- | --- |
| `min.insync.replicas` | `1` | `min.insync.replicas` |
| `unclean.leader.election.enable` | `false` | `unclean.leader.election.enable` |
| `leader.replication.throttled.replicas` | `""` | — |
| `follower.replication.throttled.replicas` | `""` | — |

Throttled replica lists use `[PartitionId]:[BrokerId],...` or `*` (see [throttled reassignment](../operations/topic-and-cluster-administration.md)).

### Tiered storage

| Topic config | Default | Server default property |
| --- | --- | --- |
| `remote.storage.enable` | `false` | — |
| `local.retention.ms` | `-2` (use `retention.ms`) | `log.local.retention.ms` |
| `local.retention.bytes` | `-2` (use `retention.bytes`) | `log.local.retention.bytes` |
| `remote.copy.lag.ms` | `0` | `log.remote.copy.lag.ms` |
| `remote.copy.lag.bytes` | `-1` | `log.remote.copy.lag.bytes` |
| `remote.log.copy.disable` | `false` | — |
| `remote.log.delete.on.disable` | `false` | — |

`remote.copy.lag.ms` / `remote.copy.lag.bytes` are the time and size upload-eligibility checks for non-active segments (`0` = upload immediately; `-1` = derive from effective local retention). `remote.log.copy.disable=true` makes tiered data read-only and switches expiration to the topic-wide `retention.*`. Enable `remote.log.delete.on.disable` when changing `remote.storage.enable` from `true` to `false`. Details: [Tiered storage](../operations/tiered-storage.md).

### Share groups

| Topic config | Default |
| --- | --- |
| `errors.deadletterqueue.group.enable` | `false` — must be `true` for a topic to be used as a share-group DLQ |

## Group configs

Group configs are **dynamic, per-group** settings stored in the cluster and set with `kafka-configs.sh --entity-type groups`. They override broker-level group coordinator defaults within the broker's allowed min/max bounds.

```bash
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --alter --entity-type groups --entity-name wordcount \
  --add-config streams.num.standby.replicas=1

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter \
  --add-config "errors.deadletterqueue.topic.name=dlq.gs1dlqtopic" --entity-type groups --entity-name my-share-group
```

### Consumer groups (`group.protocol=consumer`)

| Config | Default |
| --- | --- |
| `consumer.heartbeat.interval.ms` | `5000` (5 s) |
| `consumer.session.timeout.ms` | `45000` (45 s) |
| `consumer.assignment.interval.ms` | `1000` (1 s) |

### Share groups

| Config | Default |
| --- | --- |
| `share.record.lock.duration.ms` | `30000` |
| `share.delivery.count.limit` | `5` |
| `share.partition.max.record.locks` | `2000` |
| `share.auto.offset.reset` | `latest` |
| `share.isolation.level` | `read_uncommitted` |
| `share.renew.acknowledge.enable` | `true` |
| `share.heartbeat.interval.ms` / `share.session.timeout.ms` | `5000` / `45000` |
| `share.assignment.interval.ms` | `1000` |
| `errors.deadletterqueue.topic.name` | `""` |
| `errors.deadletterqueue.copy.record.enable` | `false` |

### Streams groups (`group.protocol=streams`)

| Config | Default |
| --- | --- |
| `streams.session.timeout.ms` | `45000` |
| `streams.heartbeat.interval.ms` | `5000` |
| `streams.num.standby.replicas` | `0` |
| `streams.initial.rebalance.delay.ms` | `3000` |
| `streams.assignment.interval.ms` | `1000` |
| `streams.assignor.name` | `null` (first of broker `group.streams.assignors`) |
| `streams.rack.aware.assignment.tags` | `""` |

In the streams rebalance protocol, session timeout, heartbeat interval and number of standby replicas are **group-level** configs; setting them on the client is ignored.

## Related pages

- [Storage, log segments and retention](../concepts/storage-and-retention.md)
- [Log compaction](../concepts/log-compaction.md)
- [Consumer groups](../clients/consumer-groups-and-rebalance.md), [Share groups](../clients/share-groups.md), [Streams rebalancing](../streams/running-and-rebalancing.md)
