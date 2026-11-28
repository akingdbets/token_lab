---
type: concept
title: Replication, ISR and Leader Election
description: How Kafka replicates partitions with a leader and followers, what keeps a replica in the in-sync replica set (ISR), how acks and min.insync.replicas determine durability, unclean leader election, Eligible Leader Replicas (KIP-966), and the configs that control replication.
tags: [replication, isr, leader-election, durability, elr, min-insync-replicas]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
  - id: openwiki-source-90e8bcb038c68685bcaea34e
    resource: repo://docs/operations/eligible-leader-replicas.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Replication, ISR and Leader Election

Kafka replicates each topic partition's log across a configurable number of servers (the **replication factor**, set per topic), so that partitions fail over automatically when a server dies. Replication is the default model: an unreplicated topic is simply a replicated topic with replication factor 1.

## Leaders and followers

- The unit of replication is the **topic partition**. Normally each partition has one **leader** and zero or more **followers**; leader + followers = replication factor.
- **All writes go to the leader**. Reads can go to the leader or to followers (follower fetching uses `replica.selector.class`, which by default returns the leader, plus the client's `client.rack`).
- Follower logs are identical to the leader's — same offsets, same order — apart from a few not-yet-replicated messages at the leader's tail.
- Followers **pull** from the leader like a consumer, which naturally batches replication.
- With many more partitions than brokers, leaders are spread evenly across brokers.

## What "in sync" means

A special node, the **controller**, manages broker registration. A broker is "alive" when both:

1. It maintains an active session with the controller — in KRaft, by sending periodic heartbeats (`broker.heartbeat.interval.ms`, default `2000`). If no heartbeat arrives within `broker.session.timeout.ms` (default `9000`), the node is considered offline.
2. As a follower, it replicates the leader's writes and doesn't fall "too far" behind.

Replicas meeting both conditions are **in sync**; the leader tracks this set, the **ISR**. A follower that dies is removed when the controller notices its lost session; a follower that has a session but lags is removed by the leader when it cannot catch up to the leader's log end within `replica.lag.time.max.ms` (default `30000`).

Kafka handles a **fail/recover** failure model, not Byzantine failures. Crashed replicas don't need intact data: before rejoining the ISR, a replica must fully re-sync, even if it lost unflushed data — so Kafka doesn't need `fsync` on every write.

## Commit, acks and min.insync.replicas

- Only **committed** messages are given to consumers. A message is committed when **all** current ISR members have it.
- Producers choose whether to wait for commit with `acks` (`0`, `1`, `all`/`-1`; see [Producer](../clients/producer.md)).
- Regardless of `acks`, messages are not visible to consumers until (1) replicated to all in-sync replicas and (2) the ISR size is at least `min.insync.replicas`.
- With `acks=all` and an ISR smaller than `min.insync.replicas`, the producer gets `NotEnoughReplicas` or `NotEnoughReplicasAfterAppend`.

**Guarantee:** a committed message is not lost as long as at least one in-sync replica stays alive. Kafka stays available through node failures after a short fail-over, but may not stay available during network partitions.

### `acks=all` is relative to the current ISR

`acks=all` means all *current* in-sync replicas, not all assigned replicas. With two replicas where one has failed, `acks=all` writes still succeed — but would be lost if the last replica also fails. To prefer durability over availability:

1. **Disable unclean leader election** (default) — the partition stays unavailable until the latest leader returns, rather than risking loss.
2. **Set a minimum ISR size** with `min.insync.replicas` — writes with `acks=all` are rejected when the ISR is below the minimum.

The typical durable setup: **replication factor 3, `min.insync.replicas=2`, producers with `acks=all`**:

```bash
bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic payments \
  --partitions 6 --replication-factor 3 --config min.insync.replicas=2
```

## Why ISR instead of majority quorum

Majority-vote replication (Zab, Raft, Viewstamped Replication) needs 2f+1 replicas to tolerate f failures. Kafka instead maintains the ISR dynamically: only ISR members are eligible as leader, a write commits only when all ISR members have it, and the ISR is persisted in cluster metadata whenever it changes. With **f+1 replicas Kafka tolerates f failures** without losing committed messages — e.g. surviving one failure needs two replicas and one acknowledgement (versus three replicas for a majority quorum). The trade-off — latency depends on the slowest ISR member — is softened by letting clients choose whether to block on commit, and is offset by lower disk and throughput costs. The closest academic design is Microsoft's PacificA.

## Unclean leader election

If *all* replicas of a partition die, there are two options:

1. Wait for an ISR replica to return (consistent, but unavailable meanwhile — permanently if its data is lost).
2. Elect the first replica that comes back even if it isn't in the ISR (available, but it may lack committed messages, which are then lost).

Since 0.11.0.0 Kafka defaults to option 1. `unclean.leader.election.enable` (default `false`, topic or cluster-wide) switches to option 2 for use cases that favor uptime. In KRaft mode, when enabled dynamically, the periodic unclean election thread runs every 5 minutes by default; use `kafka-leader-election.sh` with the unclean option to trigger it immediately:

```bash
bin/kafka-leader-election.sh --bootstrap-server localhost:9092 --election-type unclean --topic my-topic --partition 0
```

## Eligible Leader Replicas (KIP-966)

Since Kafka 4.0, **Eligible Leader Replicas** (KIP-966 Part 1) improve replication; **ELR is enabled by default on new clusters starting 4.1** (not by default in 4.0). Because the strict min-ISR rule means the high watermark cannot advance while the ISR is smaller than `min.insync.replicas`, some replicas outside the ISR are still safe to become leader. The KRaft controller stores them in the `PartitionRecord` field `Eligible Leader Replicas`. Leader election order:

1. If the ISR is not empty, pick one of its members.
2. Else, if the ELR is not empty, pick one that is not fenced.
3. Else, pick the last known leader if it is unfenced (similar to pre-4.0 behavior when all replicas are offline).

Enable / disable:

```bash
bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --feature eligible.leader.replicas.version=1
bin/kafka-features.sh --bootstrap-server localhost:9092 downgrade --feature eligible.leader.replicas.version=0
```

Downgrade is safe. ELR can be inspected through the `DescribeTopicPartitions` API (the Admin client returns it when describing topics).

When ELR is enabled, `min.insync.replicas` semantics change:

- A cluster-level `min.insync.replicas` is added if absent (same value as the active controller's static config) and cannot be removed.
- Updating the cluster-level value — even to the same value — clears all ELR state.
- Broker-level `min.insync.replicas` values are removed and can no longer be altered; set it at the cluster level instead.
- Updating `min.insync.replicas` for a topic clears that topic's ELR state.

## Replica management and leader balancing

Partitions are balanced across brokers round-robin, and leadership is balanced so each broker leads a proportional share. When a broker fails, the controller elects new leaders from the remaining ISR members for all affected partitions in a batch, making failover fast even with many partitions. If the controller fails, another is elected. `auto.leader.rebalance.enable` (default `true`) periodically (`leader.imbalance.check.interval.seconds`, default `300`) moves leadership back to preferred replicas — see [Basic operations](../operations/topic-and-cluster-administration.md).

## Configuration reference

| Config | Scope | Default |
| --- | --- | --- |
| `default.replication.factor` | broker | `1` |
| `min.insync.replicas` | broker (cluster-wide) / topic | `1` |
| `unclean.leader.election.enable` | broker (cluster-wide) / topic | `false` |
| `replica.lag.time.max.ms` | broker | `30000` (30 seconds) |
| `num.replica.fetchers` | broker (cluster-wide) | `1` |
| `broker.session.timeout.ms` | broker | `9000` |
| `broker.heartbeat.interval.ms` | broker | `2000` |
| `broker.rack` | broker | `null` (rack-aware replica placement) |
| `replica.selector.class` | broker | `null` (leader) |
| `auto.leader.rebalance.enable` | broker | `true` |
| `offsets.topic.replication.factor` | broker | `3` |

## Related pages

- [Message delivery semantics](delivery-semantics.md)
- [Basic operations: reassignment, rack awareness, replication factor](../operations/topic-and-cluster-administration.md)
- [KRaft cluster setup](../operations/kraft-cluster-setup.md)
