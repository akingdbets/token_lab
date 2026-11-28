---
type: concept
title: Message Delivery Semantics
description: At-most-once, at-least-once and exactly-once delivery in Kafka from both the producer and the consumer side — what "committed" means, how idempotence and transactions remove duplicates, how offset-commit ordering determines semantics, and which configs select each guarantee.
tags: [delivery-semantics, exactly-once, at-least-once, producer, consumer, transactions]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Message Delivery Semantics

Kafka can provide three guarantees between producer and consumer:

- **At most once** — messages may be lost but are never redelivered.
- **At least once** — messages are never lost but may be redelivered.
- **Exactly once** — each message is processed once and only once.

The problem splits in two: the durability guarantee when **publishing** and the guarantee when **consuming**. **By default Kafka guarantees at-least-once.**

## Producer side

### What "committed" means

A message is **committed** when all replicas in the partition's in-sync replica set (ISR) have applied it to their log. Once committed, it is not lost as long as one broker replicating that partition stays alive (see [Replication](replication.md)).

If a producer hits a network error while publishing, it cannot know whether the error happened before or after the commit — like inserting into a database table with an auto-generated key.

### From at-least-once to exactly-once on write

- Before 0.11.0.0, a producer that missed the ack could only resend, giving **at-least-once** (possible duplicates).
- Since 0.11.0.0, the **idempotent producer** guarantees resends don't create duplicates: the broker assigns each producer an ID and deduplicates using a sequence number sent with every message. Idempotence is on by default (`enable.idempotence=true`).
- Also since 0.11.0.0, **transactions** let the producer write atomically to multiple partitions: all messages are written or none.

### Trading durability for latency

Producers choose the durability level with `acks`: waiting for the commit (`acks=all`) can take on the order of 10 ms; alternatively send fully asynchronously (`acks=0`) or wait only for the leader (`acks=1`). See [Producer](../clients/producer.md).

## Consumer side

All replicas have the same log with the same offsets, and the consumer controls its position. What matters is the order of **processing** versus **saving the position** (committing the offset):

| Order | Crash between the two steps | Semantics |
| --- | --- | --- |
| Read → save position → process | Messages before the saved position were not processed | **At most once** |
| Read → process → save position | First messages are re-processed by the new owner | **At least once** |

At-least-once is often fine because messages carry a primary key, so re-applying an update is idempotent.

### Exactly once when the output is Kafka

When reading from one topic and writing to another (as Kafka Streams does), the consumer's position is itself a message in an internal topic, so the **offset can be written in the same transaction as the output records**:

- If the transaction aborts, the stored position reverts (though the consumer must refetch the committed offset; it does not rewind automatically) and the output is invisible to consumers depending on their isolation level.
- `isolation.level=read_uncommitted` (default) shows all messages, including those of aborted transactions; `read_committed` returns only committed transactional messages (plus non-transactional ones).

### Exactly once when the output is an external system

Coordinating the consumer position with external output classically needs two-phase commit. Kafka's simpler, more general approach is to **store the offset in the same place as the output** — e.g. a Kafka Connect connector writing data to HDFS together with the offsets it read, so both or neither are updated. Exactly-once to other systems generally requires their cooperation; Kafka provides the primitives (see [Kafka Connect exactly-once](../connect/rest-api-and-operations.md)).

## Choosing a guarantee

| Goal | How |
| --- | --- |
| **At least once** (default) | Default producer (`acks=all`, retries, idempotence) and commit offsets *after* processing (auto commit or `commitSync()` after processing). |
| **At most once** | Disable producer retries and commit offsets in the consumer *before* processing a batch. |
| **Exactly once, Kafka → Kafka** | Use [Kafka Streams](../streams/configuration.md) with `processing.guarantee=exactly_once_v2`, or the transactional producer + `read_committed` consumer pattern in [Idempotence and transactions](idempotence-and-transactions.md). |
| **Exactly once, Kafka → external** | Store offsets atomically with output in the target system, or use connectors with exactly-once support. |

Minimal consume–transform–produce exactly-once settings:

```properties
# consumer
isolation.level=read_committed
enable.auto.commit=false

# producer
transactional.id=my-app-instance-1
# enable.idempotence=true is implied by transactions
```

## Related pages

- [Idempotence and transactions](idempotence-and-transactions.md)
- [Replication, ISR and leader election](replication.md)
- [Producer](../clients/producer.md) and [Consumer](../clients/consumer.md)
