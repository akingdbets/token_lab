---
type: concept-guide
title: Consumer Groups and Rebalance Protocols
description: How Kafka consumer groups share partitions, the difference between the classic and the new KIP-848 consumer rebalance protocol (group.protocol=consumer), server-side assignors, online/offline migration, limitations, and the broker and group-level configs that control groups.
tags: [consumer, consumer-groups, rebalance, kip-848, group-coordinator, configuration]
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
  - id: openwiki-source-8cd08a136ae92fa9f3edc4b7
    resource: repo://docs/operations/consumer-rebalance-protocol.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Consumer Groups and Rebalance Protocols

## Consumer groups in one paragraph

A topic is divided into totally ordered partitions, and **each partition is consumed by exactly one consumer within each subscribing consumer group at any given time**. A consumer group is identified by `group.id`; members that call `subscribe(...)` have partitions assigned to them by the group coordinator on the brokers. Because each partition has a single owner per group, a consumer's position in a partition is just one integer — the offset of the next record — which is periodically committed (see [Consumer](consumer.md)). Adding consumers to a group spreads partitions across more instances; a rebalance redistributes partitions when members join, leave or fail.

## Two group types: Classic and Consumer

Since Apache Kafka 4.0, the **next generation consumer rebalance protocol** ([KIP-848](https://cwiki.apache.org/confluence/x/HhD1D)) is Generally Available. It improves scalability of consumer groups, simplifies consumers and reduces rebalance time thanks to a fully incremental design that no longer relies on a global synchronization barrier.

Consumer groups are therefore of two types, depending on which protocol their members use:

| | `classic` group protocol | `consumer` group protocol (KIP-848) |
| --- | --- | --- |
| Client setting | `group.protocol=classic` (default) | `group.protocol=consumer` |
| Partition assignment | Client-side assignors (`partition.assignment.strategy`) | Server-side assignors (`group.consumer.assignors`, optionally `group.remote.assignor`) |
| Heartbeat / session timeout | Client configs `heartbeat.interval.ms` (default `3000`), `session.timeout.ms` (default `45000`) | Broker configs `group.consumer.heartbeat.interval.ms` (default `5000`), `group.consumer.session.timeout.ms` (default `45000`) |
| Rebalances | Eager or cooperative, with a group-wide sync barrier | Fully incremental per member |

### Enabling the new protocol

**Server:** the new protocol is enabled automatically on the server since Kafka 4.0. Enabling/disabling it is controlled by the `group.version` feature flag (managed with `kafka-features.sh`).

**Consumer:** the protocol is *not* the client default. Set:

```properties
group.id=my-group
group.protocol=consumer
# optional: choose a server-side assignor by name
group.remote.assignor=uniform
```

When enabled, the consumer also uses an improved threading model and exposes additional metrics (see [client metrics](../monitoring/client-metrics.md)).

With `group.protocol=consumer`, these are **no longer usable**:

- `heartbeat.interval.ms`
- `session.timeout.ms`
- `partition.assignment.strategy`
- `enforceRebalance(String)` and `enforceRebalance()`

New subscription methods `subscribe(SubscriptionPattern)` and `subscribe(SubscriptionPattern, ConsumerRebalanceListener)` subscribe to a regular expression with the new protocol; the regex uses the **RE2J** format and is evaluated **on the server side**.

### Server-side assignors

The broker config `group.consumer.assignors` (default `uniform,range`) lists the available assignors. The first entry (`uniform`) is the default unless the consumer selects another via `group.remote.assignor`. Custom strategies can be plugged in by implementing `ConsumerGroupPartitionAssignor` and listing the fully qualified class name in `group.consumer.assignors`.

Mapping when migrating from client-side assignors:

| Client-side assignor | Server-side assignor |
| --- | --- |
| `RangeAssignor` | `range` |
| `CooperativeStickyAssignor` | `uniform` |
| `StickyAssignor` | `uniform` |
| `RoundRobinAssignor` | `uniform` |

For classic groups, `partition.assignment.strategy` defaults to `org.apache.kafka.clients.consumer.RangeAssignor,org.apache.kafka.clients.consumer.CooperativeStickyAssignor`.

## Upgrade and downgrade

**Offline:** an *empty* group is converted automatically between `Classic` and `Consumer`. Stop all consumers, then restart them with `group.protocol=consumer`. Downside: the group is down meanwhile.

**Online:** roll out consumers with `group.protocol=consumer`. When the first new-protocol consumer joins, the group is converted from `Classic` to `Consumer`, and the classic protocol is interoperated with the new one. This works only when the classic group uses an assignor that does **not embed custom metadata**. Downgrade is the reverse: the group converts back to `Classic` when the last new-protocol consumer leaves.

Whether non-empty groups may be converted is controlled by the broker config `group.consumer.migration.policy` (default `bidirectional`; values `DISABLED`, `DOWNGRADE`, `UPGRADE`, `BIDIRECTIONAL`).

## Evolution timeline (KIP-1274)

- **Kafka 3.7:** Early Access
- **Kafka 4.0:** GA (production-ready)
- **Kafka 5.0:** `KafkaConsumer` defaults to the `Consumer` protocol while still supporting `Classic`
- **Kafka 6.0:** `KafkaConsumer` only supports `Consumer`; the broker still supports `Classic` for backward compatibility

## Limitations

- Client-side assignors are not supported with the new protocol (feedback: KAFKA-18327).
- Rack-aware assignment strategies are not fully supported yet (KAFKA-19387).

## Static membership

With dynamic membership, member ids are ephemeral, so restarts (deploys, config changes) can reshuffle many partitions — painful for large-state apps. Setting `group.instance.id` (`ConsumerConfig#GROUP_INSTANCE_ID_CONFIG`) to a unique value per instance makes the consumer a **static member**: membership stays unchanged across restarts within the session timeout, so no rebalance is triggered. For Kafka Streams, set one unique id per `KafkaStreams` instance regardless of thread count. Duplicate ids are fenced with `org.apache.kafka.common.errors.FencedInstanceIdException`. Details: KIP-345 and [Consumer](consumer.md#static-membership).

## Configuration reference

### Consumer (client) configs

| Config | Default | Notes |
| --- | --- | --- |
| `group.id` | `null` | Required for `subscribe(...)` or Kafka-based offset management. |
| `group.protocol` | `classic` | `classic` or `consumer`. |
| `group.remote.assignor` | `null` | Server-side assignor name; only with `group.protocol=consumer`. |
| `group.instance.id` | `null` | Enables static membership. |
| `heartbeat.interval.ms` | `3000` (3 seconds) | Classic only. |
| `session.timeout.ms` | `45000` (45 seconds) | Classic only. |
| `max.poll.interval.ms` | `300000` (5 minutes) | Max delay between `poll()` calls before the member is considered failed. |
| `partition.assignment.strategy` | `RangeAssignor`, `CooperativeStickyAssignor` | Classic only. |

### Broker configs (group coordinator)

| Config | Default | Notes |
| --- | --- | --- |
| `group.consumer.assignors` | `uniform,range` | First is the default. Read-only. |
| `group.consumer.heartbeat.interval.ms` | `5000` | Bounded by `group.consumer.min/max.heartbeat.interval.ms` (`5000` / `15000`). |
| `group.consumer.session.timeout.ms` | `45000` | Bounded by `group.consumer.min/max.session.timeout.ms` (`45000` / `60000`). |
| `group.consumer.assignment.interval.ms` | `1000` | Interval between assignment updates (cluster-wide dynamic). |
| `group.consumer.max.size` | `2147483647` | Max members in a `consumer`-protocol group. |
| `group.consumer.migration.policy` | `bidirectional` | See above. |
| `group.coordinator.rebalance.protocols` | `classic,consumer,streams` | **Deprecated**, removed in 5.0 (all protocols will always be enabled). |
| `group.coordinator.threads` | `4` | Request processing threads. |
| `group.initial.rebalance.delay.ms` | `3000` | Wait for more members before the first rebalance of a new group. |
| `group.min.session.timeout.ms` / `group.max.session.timeout.ms` | `6000` / `1800000` | Allowed session timeouts for classic members. |
| `group.max.size` | `2147483647` | Max members in a classic group. |

### Group-level configs (dynamic per group)

Per-group overrides can be set with `kafka-configs.sh --entity-type groups` (see [Topic and group configuration](../configuration/topic-and-group-configuration.md)):

| Config | Default |
| --- | --- |
| `consumer.heartbeat.interval.ms` | `5000` (5 seconds) |
| `consumer.session.timeout.ms` | `45000` (45 seconds) |
| `consumer.assignment.interval.ms` | `1000` (1 second) |

The same file also defines `share.*` and `streams.*` group configs, covered in [Share groups](share-groups.md) and [Streams rebalancing](../streams/running-and-rebalancing.md).

## Related pages

- [Consumer](consumer.md)
- [Managing consumer and share groups with CLI tools](../operations/managing-groups.md)
- [Running, scaling and the Streams rebalance protocol](../streams/running-and-rebalancing.md)
