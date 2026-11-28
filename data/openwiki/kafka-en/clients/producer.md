---
type: api-guide
title: Producer
description: Using KafkaProducer — direct-to-leader load balancing and key-based partitioning, asynchronous batched sends (batch.size, linger.ms), acks and durability, retries and delivery.timeout.ms, idempotence, compression, example code and the key producer configs with their exact defaults.
tags: [producer, clients, partitioning, batching, compression, acks, configuration, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-76246c5ca9c192faf88cb2f6
    resource: repo://docs/design/design.md
  - id: openwiki-source-42c50a2642f2eaaa407a11fe
    resource: repo://docs/generated/producer_config.html
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Producer

The Producer API (`org.apache.kafka.clients.producer.KafkaProducer`, artifact `org.apache.kafka:kafka-clients`) publishes records to topics. Transactions and exactly-once are covered in [Idempotence and transactions](../concepts/idempotence-and-transactions.md).

## How the producer works

### Direct to the partition leader

The producer sends data **directly to the broker that leads the target partition**, with no routing tier. Any Kafka node can answer a metadata request saying which brokers are alive and where the partition leaders are, so the producer can route requests itself.

### Choosing a partition

The client controls the partition. With a **key**, the default logic hashes the key to a partition — e.g. using a user id as key sends all of that user's data to one partition, letting consumers make locality assumptions. Default partitioning (`partitioner.class` unset):

- If a partition is set on the record, it is used.
- If no partition is specified but a key is present, choose a partition based on a hash of the key (unless `partitioner.ignore.keys=true`).
- If neither is present, use a **sticky partition** that changes after at least `batch.size` bytes have been produced to it.
- If `client.rack` is set and `partitioner.rack.aware=true`, the sticky partition is chosen among partitions whose leader is in the same rack (falling back to all partitions).
- `partitioner.adaptive.partitioning.enable` (default `true`) sends more to partitions on faster brokers; `partitioner.availability.timeout.ms` (default `0`, disabled) treats a partition as unavailable when its broker cannot process produce requests for that long.

Alternatives: `org.apache.kafka.clients.producer.RoundRobinPartitioner` (sends consecutive records to different partitions regardless of key; known uneven distribution on new batches, KAFKA-9965), or a custom implementation of `org.apache.kafka.clients.producer.Partitioner`.

### Asynchronous, batched sends

To batch, the producer accumulates records in memory and sends larger batches per request. Batching is bounded by size (`batch.size`, default `16384` bytes) and by time (`linger.ms`, default `5` ms) — a small latency cost for much better throughput.

- Once `batch.size` worth of records accumulates for a partition, it is sent immediately; otherwise the producer *lingers* up to `linger.ms` for more records (analogous to Nagle's algorithm).
- **Version note:** the `linger.ms` default changed from `0` to `5` in Apache Kafka 4.0, because larger batches typically give similar or lower latency.
- Records wait in a buffer of `buffer.memory` (default `33554432` bytes). If records are produced faster than they can be delivered, `send()` blocks up to `max.block.ms` (default `60000`) and then fails. Even with `linger.ms=0`, `send()` can block when the buffer is full or metadata is unavailable.

### End-to-end batch compression

Compression works on **whole batches**, giving much better ratios than per-message compression. The broker decompresses a batch to validate it (e.g. the record count matches the header), but writes it to disk **compressed**, and it is sent to consumers still compressed; consumers decompress. Supported codecs: GZIP, Snappy, LZ4 and ZStandard, selected by `compression.type` (`none` default, `gzip`, `snappy`, `lz4`, `zstd`) with optional `compression.gzip.level` (default `-1`), `compression.lz4.level` (default `9`), `compression.zstd.level` (default `3`).

### Durability: `acks`

| `acks` | Behavior |
| --- | --- |
| `0` | Don't wait for any acknowledgment; the record is considered sent once in the socket buffer. No guarantee of receipt; `retries` has no effect; returned offsets are always `-1`. |
| `1` | Leader writes to its local log and responds without waiting for followers; data is lost if the leader fails before followers replicate. |
| `all` (= `-1`, **default**) | Leader waits for the full set of in-sync replicas; the record survives as long as one in-sync replica stays alive. Strongest guarantee. |

Combine `acks=all` with the topic/broker setting `min.insync.replicas` for durability (see [Replication](../concepts/replication.md)).

### Retries, timeouts and idempotence

- `retries` (default `2147483647`) resends on transient errors; total time is bounded by `delivery.timeout.ms` (default `120000`, 2 minutes), which should be ≥ `request.timeout.ms` + `linger.ms`.
- `enable.idempotence` (default `true`) guarantees exactly one copy of each message per partition despite retries. It requires `max.in.flight.requests.per.connection` ≤ 5 (default `5`; ordering preserved), `retries` > 0 and `acks=all`. If conflicting configs are set and idempotence was not explicitly enabled, idempotence is silently disabled; if it was explicitly enabled, a `ConfigException` is thrown.
- With idempotence off and `max.in.flight.requests.per.connection` > 1, retries can reorder messages.

## Example code

From `examples/src/main/java/kafka/examples/Producer.java`:

```java
Properties props = new Properties();
// bootstrap server config is required for producer to connect to brokers
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
props.put(ProducerConfig.CLIENT_ID_CONFIG, "client-" + UUID.randomUUID());
// key and value are just byte arrays, so we need to set appropriate serializers
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, IntegerSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
// enable duplicates protection at the partition level
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, enableIdempotency);
// the producer instance is thread safe
try (KafkaProducer<Integer, String> producer = new KafkaProducer<>(props)) {
    // async: callback is invoked when the record is acknowledged
    producer.send(new ProducerRecord<>(topic, key, value), (metadata, exception) -> {
        if (exception != null && !(exception instanceof RetriableException)) {
            // we can't recover from these exceptions
        }
    });
    // sync: block for the ack
    RecordMetadata metadata = producer.send(new ProducerRecord<>(topic, key, value)).get();
}
```

- `send()` returns a `Future<RecordMetadata>`; calling `.get()` makes it synchronous.
- In the callback, on error the `RecordMetadata` holds `-1` for all fields except the topic partition.
- Unrecoverable send errors in the example: `AuthorizationException`, `UnsupportedVersionException`, `ProducerFencedException`, `FencedInstanceIdException`, `OutOfOrderSequenceException`, `SerializationException`.

See [Java client examples](examples.md) to run it.

### Console producer

```bash
$ bin/kafka-console-producer.sh --topic quickstart-events --bootstrap-server localhost:9092
>This is my first event
>This is my second event
```

## Sample configuration file

`config/producer.properties`:

```properties
bootstrap.servers=localhost:9092
client.id=test-producer
transaction.timeout.ms=60000
key.serializer=org.apache.kafka.common.serialization.StringSerializer
value.serializer=org.apache.kafka.common.serialization.StringSerializer
acks=all
retries=2147483647
retry.backoff.ms=100
retry.backoff.max.ms=1000
enable.idempotence=true
max.in.flight.requests.per.connection=5
request.timeout.ms=30000
max.block.ms=60000
delivery.timeout.ms=120000
compression.type=none
linger.ms=5
batch.size=16384
buffer.memory=33554432
max.request.size=1048576
```

## Key producer configs and defaults

| Config | Default | Notes |
| --- | --- | --- |
| `bootstrap.servers` | (none) | Initial brokers. |
| `key.serializer` / `value.serializer` | (none, required) | Implement `org.apache.kafka.common.serialization.Serializer`. |
| `acks` | `all` | `all`/`-1`, `0`, `1`. |
| `enable.idempotence` | `true` | |
| `retries` | `2147483647` | |
| `delivery.timeout.ms` | `120000` (2 minutes) | Upper bound on report of success/failure after `send()`. |
| `request.timeout.ms` | `30000` (30 seconds) | Should be larger than broker `replica.lag.time.max.ms`. |
| `retry.backoff.ms` / `retry.backoff.max.ms` | `100` / `1000` | Exponential backoff. |
| `max.in.flight.requests.per.connection` | `5` | |
| `batch.size` | `16384` | Bytes per partition batch. |
| `linger.ms` | `5` | Was `0` before 4.0. |
| `buffer.memory` | `33554432` | |
| `max.block.ms` | `60000` (1 minute) | Bounds blocking in `send()`, `partitionsFor()`, `initTransactions()`, `sendOffsetsToTransaction()`, `commitTransaction()`, `abortTransaction()`. |
| `max.request.size` | `1048576` | Also caps uncompressed batch size; the broker has its own limit. |
| `compression.type` | `none` | `gzip`, `snappy`, `lz4`, `zstd`. |
| `partitioner.class` | `null` | Default partitioner logic above. |
| `partitioner.ignore.keys` | `false` | |
| `interceptor.classes` | `""` | `org.apache.kafka.clients.producer.ProducerInterceptor` implementations. |
| `transactional.id` | `null` | Enables transactions. |
| `transaction.timeout.ms` | `60000` (1 minute) | Must not exceed broker `transaction.max.timeout.ms`. |
| `transaction.two.phase.commit.enable` | `false` | Client participates in two-phase commit; its transactions never expire. |
| `connections.max.idle.ms` | `540000` (9 minutes) | |
| `metadata.max.idle.ms` | `300000` (5 minutes) | Forget metadata for idle topics. |
| `enable.metrics.push` | `true` | |

Full lists (security, metrics, DNS) are in [Client configuration](../configuration/client-configuration.md).

## Related pages

- [Topics, partitions and offsets](../concepts/topics-partitions-offsets.md)
- [Message delivery semantics](../concepts/delivery-semantics.md)
- [Idempotence and transactions](../concepts/idempotence-and-transactions.md)
- [Producer metrics](../monitoring/client-metrics.md)
