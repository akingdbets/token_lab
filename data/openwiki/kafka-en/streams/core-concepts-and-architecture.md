---
type: "Reference"
title: "Kafka Streams Concepts and Architecture"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-475ef0e100a7f3e63f2a1fd7
    resource: repo://docs/streams/architecture.md
  - id: openwiki-source-7e7e806463c4e6621c46e449
    resource: repo://docs/streams/core-concepts.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---


# Kafka Streams Concepts and Architecture

Kafka Streams is a **client library** for processing data stored in Kafka. Highlights:

- Simple, lightweight library embeddable in any Java app; works with your existing packaging and deployment tools.
- **No external dependencies** besides Kafka, using Kafka's partitioning to scale while keeping strong ordering.
- **Fault-tolerant local state** for fast stateful ops (windowed joins, aggregations).
- **Exactly-once** processing even with client or broker failures.
- **One-record-at-a-time** processing with millisecond latency and **event-time windowing** with out-of-order data.
- A high-level **Streams DSL** and a low-level **Processor API**.
- Low barrier to entry: prototype on one machine; scale by running more instances — Streams balances load automatically.

## Processor topology

- A **stream** is an unbounded, continuously updating data set — an ordered, replayable, fault-tolerant sequence of immutable **key-value records**.
- A **stream processing application** defines its logic as one or more **processor topologies**: graphs of **stream processors** (nodes) connected by streams (edges).
- A **stream processor** receives one record at a time from upstream, applies an operation, and may emit records downstream.
- **Source processors** have no upstream processors and read from Kafka topics; **sink processors** have no downstream processors and write to a Kafka topic. Normal processors may also call external systems.
- Define topologies with the [DSL](dsl-api.md) (`map`, `filter`, `join`, aggregations, …) or the [Processor API](processor-api.md) (custom processors, direct state store access).
- A topology is a logical abstraction; at runtime it's instantiated and replicated per **task** for parallelism.

## Time

| Notion | Meaning |
| --- | --- |
| **Event time** | When the event occurred at the source (e.g. when a car's GPS captured a location). |
| **Processing time** | When the Streams app processes the record — ms to days after event time. |
| **Ingestion time** | When the broker appended the record to the topic partition. |

Event- vs ingestion-time is chosen in **Kafka** (broker/topic `message.timestamp.type`: `CreateTime` or `LogAppendTime`), since timestamps are embedded in messages since 0.10.x; the default extractor reads them as-is.

- Streams assigns each record a timestamp via the **`TimestampExtractor`** interface (`default.timestamp.extractor`, default `FailOnInvalidTimestamp`). Custom extractors can read a timestamp field (event time) or return wall-clock time (processing time).
- **Stream time** is data-driven: it only advances when new records arrive, unlike **wall-clock time**.

Output record timestamps:

- Records produced while processing an input (`context.forward()` in `process()`) inherit the **input timestamp**.
- Records produced by periodic `Punctuator#punctuate()` get the task's current internal time (`context.timestamp()`).
- Aggregation results get the **max** timestamp of contributing records (per key, globally or per window).
- Stream-stream and table-table joins: `max(left.ts, right.ts)`; stream-table joins: the stream record's timestamp.
- Stateless ops pass timestamps through; `flatMap` and siblings give all outputs the input's timestamp.
- In the Processor API you can set timestamps explicitly when calling `forward()`.

## Stream–table duality

Real applications need both streams and tables (e.g. enriching a transaction stream with the latest customer info).

- **Stream as table:** a stream is a **changelog** of a table — replaying it reconstructs the table. Aggregating a stream (e.g. pageviews per user) yields a table.
- **Table as stream:** a table is a **snapshot** of the latest value per key; iterating it yields a stream.

The same idea underlies CDC database replication, log compaction, and the replication of Streams state stores. Streams models it explicitly with **`KStream`** (record stream), **`KTable`** (changelog / partitioned table) and **`GlobalKTable`** (fully replicated table) — see [DSL](dsl-api.md).

## Aggregations

An aggregation combines many input records into one output record per key (counts, sums, …). The input may be a `KStream` or `KTable`; the **output is always a `KTable`**, so late (out-of-order) records can update an already emitted result, and the new value overwrites the old one for that key downstream.

## Windowing

Windows group records **with the same key** for aggregations and joins; they're tracked per key. A **grace period** sets how long a window accepts out-of-order records: a record is **dropped** if stream time is beyond the window end plus grace. Out-of-order only applies to event time (with processing time, nothing is out of order by definition). Window types are covered in [Joins and windowing](dsl-joins-and-windowing.md).

## State

Stateful operations (joins, aggregations, windowing) use **state stores** — persistent key-value stores (RocksDB), in-memory hashmaps or other structures — embedded in each task, with fault tolerance and automatic recovery. **Interactive Queries** allow read-only access to named stores from outside the topology ([state stores and IQ](state-stores-and-interactive-queries.md)).

## Processing guarantees

Since 0.11.0.0, Kafka's idempotent, transactional producers let Streams provide **end-to-end exactly-once**: for every record read from source topics, its results are reflected exactly once in output topics **and** state stores — input offset commits, state store updates and output writes are committed atomically.

- **Exactly-once v2** (since 2.6.0, brokers ≥ 2.5.0) is more efficient (fewer client threads and network connections, higher throughput, better scalability); EOS v1 is deprecated since 3.0.0 (KIP-447).
- Enable with `processing.guarantee=exactly_once_v2` (`StreamsConfig.EXACTLY_ONCE_V2`); default is `at_least_once`. See [Configuration](configuration.md#processing-guarantee) for side effects.

## Out-of-order handling

Out-of-order data arises when (1) timestamps within a partition aren't monotonic with offsets (Streams processes in offset order), or (2) a task reading multiple partitions doesn't wait for all of them and later sees older timestamps on another partition (`max.task.idle.ms` controls waiting).

Stateless operations are unaffected; stateful ones trade latency, cost and correctness — via window grace periods for windowed aggregations, and versioned state stores for joins:

| Join | Out-of-order behavior |
| --- | --- |
| Stream-stream (inner, left, outer) | Handled correctly. |
| Stream-table | Not handled without versioned stores (offset order, possibly unpredictable). With versioned stores, stream-side out-of-order data is handled by timestamped lookups; table-side still isn't. |
| Table-table | Not handled without versioned stores, but results are an eventually consistent changelog. With versioned stores, semantics become timestamp-based and out-of-order records are handled. |

## Architecture

Streams builds on the Kafka producer and consumer for parallelism, coordination and fault tolerance.

### Stream partitions and tasks

- Each **stream partition** is a totally ordered sequence of records mapping to a **topic partition**; records map to Kafka messages; **keys** determine partitioning in both.
- Streams creates a **fixed number of tasks** from the input partitions; each task gets a fixed list of input partitions (this mapping never changes), instantiates its own copy of the topology, buffers each partition and processes records one at a time. Tasks are independent and run in parallel.
- **Maximum parallelism = number of tasks ≈ max partitions of the input topics.** With 5 input partitions you can run up to 5 instances; extra instances stay idle as hot spares that take over if a busy one fails.
- Streams is a library, not a resource manager: run instances anywhere. If an instance fails, its tasks restart on others and continue from the same partitions.
- Partition-to-task and task-to-thread assignment (balancing load vs. stickiness of stateful tasks) is done by `StreamsPartitionAssignor` in the classic protocol; **other assignors set by users are ignored**. (The new `streams` group protocol moves assignment to the broker — see [Running and rebalancing](running-and-rebalancing.md).)

### Threading model

- `num.stream.threads` sets threads per instance; each thread runs one or more tasks independently.
- Threads share **no state**, so no inter-thread coordination is needed; more threads or instances simply replicate the topology over different partitions.
- Run as many threads in total (across instances) as there are input partitions for every thread to have work.
- **Since 2.8** you can add/remove stream threads at runtime (`KafkaStreams#addStreamThread()` / `removeStreamThread()`), e.g. to replace dead threads without restarting the client.

### Local state stores

The DSL creates and manages state stores automatically for `join()`, `aggregate()` and windowing; each task may embed several local stores.

### Fault tolerance

- Input data in Kafka is replicated and highly available, so it can be reprocessed after failures; failed tasks are restarted on remaining instances.
- Each state store has a replicated, **compacted changelog topic** (one partition per store instance/task). After a failure, Streams **replays the changelog** to restore the store before processing resumes — transparent to users.
- Restoration time dominates task (re)initialization. Configure **standby replicas** (`num.standby.replicas`) — fully replicated copies — so migrated tasks land where state already exists. **Since 2.6**, a task is only assigned to an instance with a **fully caught-up** copy if one exists (warmups catch up in the background).
- **Rack awareness:** `rack.aware.assignment.tags` places standbys on different "racks" than actives; with `client.rack` and broker `broker.rack`, `rack.aware.assignment.strategy` reduces cross-rack traffic. `rack.aware.assignment.tags` takes precedence for standby distribution if both are set.

## Related pages

- [Introduction and quickstart](introduction-and-quickstart.md)
- [Streams DSL](dsl-api.md), [Joins and windowing](dsl-joins-and-windowing.md), [Processor API](processor-api.md)
- [State stores and interactive queries](state-stores-and-interactive-queries.md)
- [Running, scaling and rebalancing](running-and-rebalancing.md)
