---
type: concept-guide
title: Idempotent Producer and Transactions
description: How to get exactly-once processing with the Kafka producer and consumer — idempotence, transactional.id, initTransactions/beginTransaction/sendOffsetsToTransaction/commitTransaction/abortTransaction, read_committed consumers, KIP-1050 exception categories, the KIP-890 transaction protocol (transaction.version=2), and transaction-related configs.
tags: [transactions, exactly-once, idempotence, producer, consumer, kip-890]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-2d99f0eff26c3fa533ddd079
    resource: repo://docs/generated/kafka_config.html
  - id: openwiki-source-42c50a2642f2eaaa407a11fe
    resource: repo://docs/generated/producer_config.html
  - id: openwiki-source-cc3912bd5fe9cac963b7ce88
    resource: repo://docs/operations/transaction-protocol.md
  - id: openwiki-source-e5b09bfdede1aa79e7c81bb9
    resource: repo://examples/src/main/java/kafka/examples/ExactlyOnceMessageProcessor.java
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Idempotent Producer and Transactions

The simplest way to get exactly-once semantics is [Kafka Streams](../streams/configuration.md) (`processing.guarantee=exactly_once_v2`). The same guarantees can be achieved by using `KafkaProducer` and `KafkaConsumer` directly, the way Kafka Streams does. Background: [Message delivery semantics](delivery-semantics.md).

## Idempotent producer

With `enable.idempotence=true` (the default), the broker assigns the producer an ID and deduplicates writes using a per-message sequence number, so retries cannot create duplicates within a partition. Requirements: `acks=all`, `retries` > 0, `max.in.flight.requests.per.connection` ≤ 5 (see [Producer](../clients/producer.md)).

## How Kafka transactions differ

- The consumer and producer are separate, and **only the producer is transactional**.
- The producer can transactionally update the consumer's position (the "committed offset"); that is what produces end-to-end exactly-once.

Three key aspects (matching Kafka Streams):

1. The consumer uses partition assignment so it is the only consumer in its group processing each partition.
2. The producer uses a transaction so that all its output records and the consumer offsets it commits are written atomically.
3. To handle transactions correctly with rebalancing, use **one producer instance per consumer instance**.

## Required configuration

```properties
# consumer
isolation.level=read_committed
enable.auto.commit=false

# producer (only the producer has transactional.id)
transactional.id=<static, unique id for this instance>
```

Setting `transactional.id` configures the producer for transactional delivery and ensures that a restarted application **aborts any in-flight transaction** from the previous instance (zombie fencing). Read-committed is strictly optional but recommended; otherwise the consumer sees records from aborted and still-open transactions.

## The transactional loop

From `examples/src/main/java/kafka/examples/ExactlyOnceMessageProcessor.java` (run with `examples/bin/exactly-once-demo.sh 6 3 10000`):

```java
// called first and once to fence zombies and abort any pending transaction
producer.initTransactions();
consumer.subscribe(Set.of(inputTopic), this);

while (!closed && remainingRecords > 0) {
    try {
        ConsumerRecords<Integer, String> records = consumer.poll(ofMillis(200));
        if (!records.isEmpty()) {
            producer.beginTransaction();
            for (ConsumerRecord<Integer, String> record : records) {
                producer.send(new ProducerRecord<>(outputTopic, record.key(), record.value() + "-ok"));
            }
            // checkpoint the progress by sending offsets to group coordinator broker
            // note that this API is only available for broker >= 2.5
            producer.sendOffsetsToTransaction(getOffsetsToCommit(consumer), consumer.groupMetadata());
            // commit the transaction including offsets
            producer.commitTransaction();
        }
    } catch (AuthorizationException | UnsupportedVersionException | ProducerFencedException
             | FencedInstanceIdException | OutOfOrderSequenceException | SerializationException e) {
        // we can't recover from these exceptions
        shutdown();
    } catch (KafkaException e) {
        producer.abortTransaction();
        // rewind: seek each assigned partition to consumer.committed(...) (or seekToBeginning)
        retries = maybeRetry(retries, consumer);
    }
}
```

Details worth copying:

- `transactional.id` is `"tid-" + threadName` — static and unique per instance, so it identifies the same producer across restarts.
- `transaction.timeout.ms` is set to `10_000`: a relatively short transaction timeout clears pending offsets faster (producer default `60000`).
- The consumer uses `read_committed`, `enable.auto.commit=false` and a `group.instance.id` (`"giid-" + threadName`) to avoid unnecessary rebalances.
- The offsets committed are `consumer.position(tp)` for each assigned partition — the *next* offset to read.
- After an abort, the application must **reset the consumer position explicitly**: aborted transactions don't rewind the consumer automatically. The example retries up to 5 times and then skips the batch by committing the position (a real application might send such records to a dead letter topic).

### Abort handling and markers

Records written by a transactional producer are part of the transaction; on commit or abort, **transaction marker** (control) records are written, which is how a read-committed consumer filters out aborted records. Control records are never returned to applications.

Two simple recovery policies:

- **Recreate** producer and consumer: the group rebalances and the new consumer fetches the last committed offset, effectively rewinding.
- **Seek**: fetch committed offsets with `KafkaConsumer.committed` and rewind with `KafkaConsumer.seek` (as the examples do).

## Exception categories (KIP-1050)

Transactional producer error handling is standardized:

| Category | Who handles it | What to do |
| --- | --- | --- |
| `RetriableException` | Client, internally | Nothing — retried automatically. |
| `RefreshRetriableException` | Client, internally | Nothing — retried after a metadata refresh. |
| `AbortableException` (e.g. `TransactionAbortableException`) | Application | Abort the transaction and reset the consumer position. |
| `ApplicationRecoverableException` | Application | Own recovery strategy, which must include **restarting the producer**. |
| `InvalidConfigurationException` | Application | Producer need not restart, but the application may choose to. |
| `KafkaException` (other) | Application | Handle as appropriate. |

`examples/src/main/java/kafka/examples/TransactionalClientDemo.java` is the template for these rules; see [Java client examples](../clients/examples.md#transactionalclientdemo).

## Transaction protocol v2 (KIP-890)

Starting in Kafka 4.0, **Transactions Server Side Defense** (KIP-890) strengthens the protocol: with 4.0+ producer clients, the producer epoch is bumped on **every transaction**, ensuring each transaction contains only its intended messages and duplicates are not written into the next transaction.

- Enabled automatically on the server since 4.0, controlled by the **`transaction.version`** feature flag — set it with the storage tool when creating a cluster, or dynamically with the features tool:

```bash
bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --feature transaction.version=2
```

- Producers don't need a restart: they upgrade the next time they (re)connect, and never mid-transaction — only at the start of the next transaction after learning about the upgrade. Downgrades are safe and work the same way.
- **Performance:** only one add-partitions call happens server side (instead of client add + server verify). Because `endTransaction` is asynchronous, a client can start adding partitions for the next transaction before markers are written; the server now retries on `CONCURRENT_TRANSACTIONS` itself before returning the error. Produce latency may look higher, but end-to-end transaction latency does not increase — the time moves from client-side backoff into produce latency. The server-side backoff is tuned with `add.partitions.to.txn.retry.backoff.ms` (default `20`) and `add.partitions.to.txn.retry.backoff.max.ms` (default `100`).

## Configuration reference

### Producer

| Config | Default | Notes |
| --- | --- | --- |
| `enable.idempotence` | `true` | |
| `transactional.id` | `null` | Non-empty string enables transactions. |
| `transaction.timeout.ms` | `60000` (1 minute) | Coordinator aborts transactions open longer than this; must be ≤ broker `transaction.max.timeout.ms`. |
| `transaction.two.phase.commit.enable` | `false` | Participate in 2PC with an external coordinator; such transactions never expire. |

### Consumer

| Config | Default |
| --- | --- |
| `isolation.level` | `read_uncommitted` (use `read_committed`) |
| `enable.auto.commit` | `true` (set `false`) |

### Broker

| Config | Default | Notes |
| --- | --- | --- |
| `transaction.max.timeout.ms` | `900000` (15 minutes) | Larger client timeouts are rejected in `InitProducerIdRequest`. |
| `transactional.id.expiration.ms` | `604800000` (7 days) | Idle transactional ids expire (never while a transaction is ongoing). |
| `producer.id.expiration.ms` | `86400000` (1 day) | Partition leaders expire idle producer IDs. |
| `transaction.state.log.replication.factor` | `3` | `__transaction_state` topic creation fails until the cluster is this big. |
| `transaction.state.log.min.isr` | `2` | |
| `transaction.state.log.num.partitions` | `50` | Don't change after deployment. |
| `transaction.partition.verification.enable` | `true` | Verify the partition was added to the transaction before writing. |
| `transaction.two.phase.commit.enable` | `false` | Allow 2PC transactions. |
| `transaction.abort.timed.out.transaction.cleanup.interval.ms` | `10000` | |

## Related pages

- [Message delivery semantics](delivery-semantics.md)
- [Java client examples](../clients/examples.md)
- [Producer](../clients/producer.md), [Consumer](../clients/consumer.md)
