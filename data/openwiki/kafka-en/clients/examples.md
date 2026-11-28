---
type: example-guide
title: Java Client Examples
description: Walkthrough of the Kafka examples module — KafkaConsumerProducerDemo, KafkaExactlyOnceDemo and TransactionalClientDemo, the Producer/Consumer/ExactlyOnceMessageProcessor helper threads, Utils, and the bin scripts used to run them against a local broker.
tags: [examples, producer, consumer, transactions, exactly-once, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-46b2e24fd032d64c8eaf5a6e
    resource: repo://examples/bin/exactly-once-demo.sh
  - id: openwiki-source-5fbd613dd2f41d2c5b07bc62
    resource: repo://examples/bin/java-producer-consumer-demo.sh
  - id: openwiki-source-c8b39dcd2a245cd9301a976a
    resource: repo://examples/README.md
  - id: openwiki-source-9fb1e2ea16053a43229c80e6
    resource: repo://examples/src/main/java/kafka/examples/KafkaConsumerProducerDemo.java
  - id: openwiki-source-e8e3bdc41210e2c5b6600687
    resource: repo://examples/src/main/java/kafka/examples/KafkaExactlyOnceDemo.java
  - id: openwiki-source-4b56b6aa5862e2824b4aa912
    resource: repo://examples/src/main/java/kafka/examples/Producer.java
  - id: openwiki-source-d06e252e28a380d9760ed087
    resource: repo://examples/src/main/java/kafka/examples/TransactionalClientDemo.java
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Java Client Examples

The `examples` module (package `kafka.examples`) contains small, runnable Java programs that show idiomatic use of the producer, consumer, Admin and transactional APIs. They all connect to `KafkaProperties.BOOTSTRAP_SERVERS = "localhost:9092"`.

## Running the examples

1. Start a local single-broker Kafka cluster with a PLAINTEXT listener on port 9092 (see [Quickstart](../getting-started/local-quickstart.md)).
2. Run one of the demo scripts from the Kafka directory:

```bash
# asynchronously send 10k records to my-topic and consume them
examples/bin/java-producer-consumer-demo.sh 10000

# synchronously send 10k records
examples/bin/java-producer-consumer-demo.sh 10000 sync

# create input-topic and output-topic with 6 partitions each,
# start 3 transactional instances and process 10k records
examples/bin/exactly-once-demo.sh 6 3 10000
```

Both scripts set `KAFKA_HEAP_OPTS="-Xmx512M"` if it is not already set and then `exec bin/kafka-run-class.sh kafka.examples.<MainClass> "$@"`. From an IDE, pass the same values as program arguments.

## The classes

| Class | Role |
| --- | --- |
| `KafkaConsumerProducerDemo` | Main for the producer/consumer demo. |
| `KafkaExactlyOnceDemo` | Main for the multi-instance exactly-once (EOS) demo. |
| `TransactionalClientDemo` | Standalone consume–transform–produce word-count app with KIP-1050 transactional error handling. |
| `Producer` | Thread that sends `numRecords` records (`Integer` key, `"test<key>"` value) in async or sync mode, optionally idempotent/transactional. |
| `Consumer` | Thread that subscribes with a group and `ConsumerRebalanceListener`, optionally `read_committed`. See [Consumer](consumer.md). |
| `ExactlyOnceMessageProcessor` | Transactional read–process–write loop used by the EOS demo. See [Idempotence and transactions](../concepts/idempotence-and-transactions.md). |
| `Utils` | `printHelp`, `printOut`, `printErr`, `maybePrintRecord` (prints ~10 sample records), and `recreateTopics` (Admin API delete + create). |
| `KafkaProperties` | Holds the bootstrap servers constant. |

## KafkaConsumerProducerDemo

Arguments: `records` (required) and optional `sync`. Async is used unless the second argument is `sync`.

Stages:

1. `Utils.recreateTopics(BOOTSTRAP_SERVERS, -1, "my-topic")` deletes and recreates `my-topic` (−1 partitions → broker default).
2. Starts a `Producer` thread writing `numRecords` records to `my-topic`.
3. Starts a `Consumer` thread in group `my-group` reading them back.
4. Waits on a `CountDownLatch(2)` for up to 5 minutes, then shuts the threads down.

### Async vs. sync sending (`Producer`)

```java
// async: send with a callback; returns immediately
producer.send(new ProducerRecord<>(topic, key, value), new ProducerCallback(key, value));

// sync: block on the future for the broker ack
RecordMetadata metadata = producer.send(new ProducerRecord<>(topic, key, value)).get();
```

Notes from the source:

- The producer instance **is thread-safe** (the consumer is not).
- Even with a small `batch.size` and `linger.ms=0`, `send()` can still block when `buffer.memory` is full or metadata is unavailable.
- In the callback, a non-null exception that is not a `RetriableException` is treated as fatal. In sync mode, `AuthorizationException`, `UnsupportedVersionException`, `ProducerFencedException`, `FencedInstanceIdException`, `OutOfOrderSequenceException` and `SerializationException` are unrecoverable.
- When an error occurs, the callback's `RecordMetadata` has `-1` for every field except the topic partition.

## KafkaExactlyOnceDemo

Arguments (all required): `partitions`, `instances`, `records` — e.g. `6 3 10000`. Requires brokers ≥ 2.5.0, otherwise `UnsupportedVersionException`.

Stages:

1. Recreate `input-topic` and `output-topic` with the given partition count.
2. A synchronous, idempotent `Producer` pre-populates `input-topic` (waits up to 2 minutes).
3. `instances` × `ExactlyOnceMessageProcessor` threads (`processor-0`, `processor-1`, …) each run a transactional read–process–write loop, draining their partitions by comparing the log end offset with the committed offset; each record is processed exactly once with per-partition ordering.
4. A `read_committed` `Consumer` in group `check-group` verifies that all records arrived in `output-topic`.

## TransactionalClientDemo

A word-count style consume–transform–produce loop that follows [KIP-1050](https://cwiki.apache.org/confluence/display/KAFKA/KIP-1050) error-handling guidance. Consumer: group `my-group-id`, `enable.auto.commit=false`, `isolation.level=read_committed`, subscribed to `input`. Producer: `enable.idempotence=true`, `transactional.id=prod-1`, writing to `output`.

```java
producer.initTransactions();
while (isRunning) {
    try {
        try {
            ConsumerRecords<String, String> records = consumer.poll(ofSeconds(60));
            // ... build wordCountMap ...
            producer.beginTransaction();
            wordCountMap.forEach((key, value) ->
                producer.send(new ProducerRecord<>(OUTPUT_TOPIC, key, value.toString())));

            Map<TopicPartition, OffsetAndMetadata> offsetsToCommit = new HashMap<>();
            for (TopicPartition partition : records.partitions()) {
                List<ConsumerRecord<String, String>> partitionedRecords = records.records(partition);
                long offset = partitionedRecords.get(partitionedRecords.size() - 1).offset();
                offsetsToCommit.put(partition, new OffsetAndMetadata(offset + 1));
            }
            producer.sendOffsetsToTransaction(offsetsToCommit, consumer.groupMetadata());
            producer.commitTransaction();
        } catch (TransactionAbortableException e) {
            producer.abortTransaction();
            resetToLastCommittedPositions(consumer);   // seek to committed() or seekToBeginning
        }
    } catch (InvalidConfigurationException e) {
        closeAll(); throw e;                          // fatal
    } catch (ApplicationRecoverableException e) {
        closeAll(); initializeApplication();          // restart clients
    } catch (KafkaException e) {
        closeAll(); initializeApplication();          // treat as application-recoverable
    }
}
```

Error classes:

| Exception | Handling |
| --- | --- |
| `TransactionAbortableException` | Abort the transaction and rewind the consumer to its last committed positions. |
| `ApplicationRecoverableException` and other `KafkaException`s | Close and re-create consumer and producer. |
| `InvalidConfigurationException` | Fatal: close and rethrow. |

The committed offset is the **next** offset to read (`last offset + 1`), and offsets are committed through the producer with `sendOffsetsToTransaction(..., consumer.groupMetadata())` so that consumption and production commit atomically.

## Related pages

- [Producer](producer.md)
- [Consumer](consumer.md)
- [Admin API](admin-api.md) (topic recreation in `Utils`)
- [Idempotence and transactions](../concepts/idempotence-and-transactions.md)
