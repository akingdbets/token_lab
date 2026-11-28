---
type: api-guide
title: "Streams DSL: Sources, Stateless and Stateful Transformations"
description: The Kafka Streams DSL — KStream, KTable and GlobalKTable semantics, reading sources with StreamsBuilder (stream, table, globalTable), every stateless operation (split/branch, filter, map, flatMap, groupBy, merge, peek, selectKey, toTable, repartition…), stateful aggregations (aggregate, count, reduce, cogroup) and their null/tombstone behavior, process/processValues and the 4.0 removal of transform*, suppress for emit-rate control, versioned (timestamp-based) tables, and writing results back with to().
tags: [streams, dsl, kstream, ktable, aggregation, transformations, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-6d2700367726e79c73735010
    resource: repo://docs/streams/developer-guide/dsl-api.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Streams DSL: Sources, Stateless and Stateful Transformations

The DSL is the high-level Kafka Streams API. Compared with the [Processor API](processor-api.md), only the DSL offers built-in **stream and table abstractions** (`KStream`, `KTable`, `GlobalKTable`) and a declarative, functional style for stateless transformations (`map`, `filter`), stateful ones (`count`, `reduce`, joins, windowing). Building a topology means: (1) read input streams from topics, (2) compose transformations, (3) write results to topics or expose them via [interactive queries](state-stores-and-interactive-queries.md). Joins and windows are on [a separate page](dsl-joins-and-windowing.md).

## Core abstractions

### KStream — record stream

Each record is a self-contained fact, interpreted as an **INSERT** into an append-only ledger (transactions, page views, log lines). For `("alice", 1) --> ("alice", 3)`, summing per user gives **4**.

### KTable — changelog stream

Each record is an **UPDATE (upsert)** of the previous value for its key; a `null` value is a **DELETE (tombstone)**. For the same records, summing gives **3**.

- Log compaction is **safe for a KTable's topic** but **wrong for a KStream's** (it would drop `("alice", 1)` and change the result).
- KTables support key lookups via joins and interactive queries.
- Each app instance's KTable holds only the partitions assigned to it.

### GlobalKTable

Also a changelog, but **every instance holds all partitions** of the topic (for 5 partitions and 5 instances: KTable = 1 partition each, GlobalKTable = all 5).

- **Pros:** convenient/efficient joins — star joins, foreign-key lookups by value fields, efficient chained joins, **no co-partitioning needed**; broadcast data to all instances.
- **Cons:** more local storage and more network/broker load (whole topic tracked). No notion of time.

## Creating source streams

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.KStream;

StreamsBuilder builder = new StreamsBuilder();

KStream<String, Long> wordCounts = builder.stream(
    "word-counts-input-topic", /* input topic */
    Consumed.with(
      Serdes.String(), /* key serde */
      Serdes.Long()   /* value serde */
    ));

KTable<String, Long> table = builder.table(
    "word-counts-input-topic",
    Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("word-counts-store"));

GlobalKTable<String, Long> globalWordCounts = builder.globalTable(
    "word-counts-input-topic",
    Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as(
      "word-counts-global-store" /* table/store name */)
      .withKeySerde(Serdes.String()) /* key serde */
      .withValueSerde(Serdes.Long()) /* value serde */
    );
```

| Method | Result | Notes |
| --- | --- | --- |
| `builder.stream(topic(s) or Pattern)` | `KStream` | Partitioned record stream. With a regex, all matching topics form one input group (not parallelized per topic). |
| `builder.table(topic)` | `KTable` | Name the backing store (via `Materialized.as`) to make it queryable; otherwise an internal, non-queryable name is used. Variants set e.g. `auto.offset.reset`. |
| `builder.globalTable(topic)` | `GlobalKTable` | Reads all partitions; name the store to query it. |

If you don't pass Serdes, the defaults (`default.key.serde`, `default.value.serde`) apply — you **must** pass them explicitly when types differ ([Serdes](serdes-and-datatypes.md)).

## Stateless transformations

Don't need a state store. `KStream` operations return `KStream`s (or several, with `split`); `KTable` operations return `KTable`s, which can optionally be **materialized** (queryable) by passing a store name. `toStream()` converts a table to a stream.

| Operation | Types | Notes |
| --- | --- | --- |
| `split()` / `branch()` / `defaultBranch()` | KStream → BranchedKStream | First matching predicate wins; unmatched records go to the default branch or are dropped. |
| broadcast | KStream → KStream(s) | Apply several operations to the same stream. |
| `filter` / `filterNot` | KStream→KStream, KTable→KTable | On tables, filtered-out records become tombstones downstream. |
| `flatMap` | KStream → KStream | 0..n records with new keys — **marks for repartitioning**; prefer `flatMapValues`. |
| `flatMapValues` | KStream → KStream | Keeps keys; no repartitioning. |
| `foreach` | KStream → void, KTable → void | **Terminal**; side effects aren't covered by processing guarantees. |
| `groupByKey` | KStream → KGroupedStream | Repartitions **only if** the stream was marked for repartitioning; preferred over `groupBy`. |
| `groupBy` | KStream → KGroupedStream, KTable → KGroupedTable | New key (and for tables, new value); shorthand for `selectKey(...).groupByKey()`; **always repartitions**. |
| `cogroup` | KGroupedStream → CogroupedKStream | Aggregate several grouped streams into one result. |
| `map` | KStream → KStream | New key and value — marks for repartitioning; prefer `mapValues`. |
| `mapValues` | KStream→KStream, KTable→KTable | Value only; no repartitioning. |
| `merge` | KStream → KStream | Union; no ordering guarantee across inputs (per-input order kept). |
| `peek` | KStream → KStream | Side-effect action, passes records unchanged. |
| `print` | KStream → void | Terminal; `System.out` or `Printed.toFile(...)`. |
| `selectKey` | KStream → KStream | New key — marks for repartitioning. |
| `toStream` | KTable → KStream | |
| `toTable` | KStream → KTable | |
| `repartition` | KStream → KStream | Always repartitions through a managed internal topic; set partition count with `Repartitioned.numberOfPartitions(n)`; useful before `process()` after key changes. |

Examples:

```java
// branch
Map<String, KStream<String, Long>> branches =
    stream.split(Named.as("Branch-"))
        .branch((key, value) -> key.startsWith("A"),  /* first predicate  */
             Branched.as("A"))
        .branch((key, value) -> key.startsWith("B"),  /* second predicate */
             Branched.as("B"))
        .defaultBranch(Branched.as("C"));             /* default branch */

KStream<String, Long> onlyPositives = stream.filter((key, value) -> value > 0);
KStream<String, Long> alsoPositives = stream.filterNot((key, value) -> value <= 0);

KStream<byte[], String> words = sentences.flatMapValues(value -> Arrays.asList(value.split("\\s+")));
KStream<byte[], String> uppercased = stream.mapValues(value -> value.toUpperCase());
KStream<String, String> rekeyed = stream.selectKey((key, value) -> value.split(" ")[0]);
KStream<byte[], String> merged = stream1.merge(stream2);

stream.foreach((key, value) -> System.out.println(key + " => " + value));
stream.print(Printed.toFile("streams.out").withLabel("streams"));

KGroupedStream<byte[], String> groupedStream = stream.groupByKey(
    Grouped.with(Serdes.ByteArray(), Serdes.String()));

KStream<byte[], String> repartitioned = stream.repartition(Repartitioned.numberOfPartitions(10));
KTable<byte[], String> table2 = stream.toTable();
```

`groupBy`/`groupByKey` variants take `Grouped.with(...)` Serdes — required when the grouped key/value types differ from the defaults. Grouping is a prerequisite for aggregations; **windowing** further sub-groups same-key records.

## Stateful transformations

Need a state store (fault-tolerant, fully restored before processing resumes after failures). Store types used regardless of what `Materialized` specifies:

- Non-windowed aggregations and KTables: `TimestampedKeyValueStore` or `VersionedKeyValueStore` (if `Materialized` is versioned).
- Time-windowed aggregations and KStream-KStream joins: `TimestampedWindowStore`.
- Session-windowed aggregations: `SessionStore` (no timestamped variant yet).

**Headers-aware stores (KIP-1285):** `dsl.store.format=HEADERS` makes supported operators keep record headers in stores. It only changes the store format: aggregations, KTable-KTable joins, materialized `KTable.mapValues`, `KStream.toTable()` and `StreamsBuilder.table()` write **empty headers**; KStream-KStream join window stores keep source headers but results don't get merged headers; left/outer stream-stream join buffers drop headers.

WordCount:

```java
KStream<String, String> textLines = ...;
KStream<String, Long> wordCounts = textLines
    // Split each text line, by whitespace, into words.
    .flatMapValues(value -> Arrays.asList(value.toLowerCase().split("\\W+")))
    // Group the stream by word to ensure the key of the record is the word.
    .groupBy((key, word) -> word)
    // Count the occurrences of each word (record key): KGroupedStream -> KTable.
    .count()
    // Convert the KTable<String, Long> into a KStream<String, Long>.
    .toStream();
```

### Aggregating

After `groupByKey`/`groupBy` (→ `KGroupedStream` or `KGroupedTable`), aggregate **per key**, windowed or not.

| Operation | Types | Required functions |
| --- | --- | --- |
| `aggregate` | KGroupedStream→KTable, KGroupedTable→KTable, CogroupedKStream→KTable | Stream: initializer + adder. Table: initializer + adder + **subtractor**. Cogrouped: initializer only (aggregators given in `cogroup`). Result type may differ from input. |
| `aggregate` (windowed) | TimeWindowedKStream / SessionWindowedKStream → KTable<Windowed<K>,…> | initializer + adder (+ session **merger** for session windows). |
| `count` | KGroupedStream/KGroupedTable → KTable<K, Long> | |
| `reduce` | KGroupedStream/KGroupedTable → KTable | Combines with the last reduced value; result type can't change. Tables need adder + subtractor. |

```java
KTable<byte[], Long> aggregatedStream = groupedStream.aggregate(
    () -> 0L, /* initializer */
    (aggKey, newValue, aggValue) -> aggValue + newValue.length(), /* adder */
    Materialized.<byte[], Long, KeyValueStore<Bytes, byte[]>>as("aggregated-stream-store") /* state store name */
        .withValueSerde(Serdes.Long()));

KTable<byte[], Long> aggregatedTable = groupedTable.aggregate(
    () -> 0L, /* initializer */
    (aggKey, newValue, aggValue) -> aggValue + newValue.length(), /* adder */
    (aggKey, oldValue, aggValue) -> aggValue - oldValue.length(), /* subtractor */
    Materialized.<byte[], Long, KeyValueStore<Bytes, byte[]>>as("aggregated-table-store")
        .withValueSerde(Serdes.Long()));

KTable<String, Long> counts = groupedStream.count();
KTable<String, Long> sums = groupedStream.reduce((aggValue, newValue) -> aggValue + newValue);
```

Behavior details:

- **Grouped streams:** records with `null` keys are ignored; the initializer is called the first time a key is seen (before the adder); the adder runs for every non-`null` value. `count` also ignores `null` values.
- **Grouped tables:** `null` keys ignored. First non-null value (INSERT) → adder only. Later values (UPDATE) → **subtractor with the old value, then adder with the new** (subtractor always first). Tombstone (DELETE) → subtractor only; if it returns `null` the key is removed from the result, and the initializer may run again later for that key. `count` treats `null` values as tombstones.
- Results are `KTable`s, so late or updated inputs emit **new versions** of the aggregate, which overwrite the previous value downstream. How often updates are emitted depends on the record cache and `commit.interval.ms` ([memory management](state-stores-and-interactive-queries.md#memory-management)).

### Custom processing: process and processValues

Mix in Processor API logic:

- `KStream#process(ProcessorSupplier, String... storeNames)` — a `Processor` that may change keys (marks for repartitioning).
- `KStream#processValues(FixedKeyProcessorSupplier, String... storeNames)` — a `FixedKeyProcessor` that can't change keys.

```java
logStream.process(LogSeverityProcessor::new);
messageStream.processValues(SlangReplacementProcessor::new).to(OUTPUT_MESSAGES_TOPIC);
purchaseStream.process(CumulativeDiscountProcessor::new, CUSTOMER_SPENDING_STORE);
```

**Kafka 4.0 removed** `KStream#transform`, `#flatTransform`, `#transformValues`, `#flatTransformValues` and the old `KStream#process` — migrate to `process`/`processValues` (using `ProcessorContext`, `Record`/`FixedKeyRecord` and `context().forward()`).

**Caution (KAFKA-19668):** rewriting `transformValues()`/`flatTransformValues()` to `processValues()` with the **merge repartition topics** optimization may be unsafe on 4.0.0/4.1.0; use 4.0.1/4.1.1+ and enable the fix (off by default for compatibility). New apps using that optimization should enable it too:

```java
final Properties properties = new Properties();
properties.put(StreamsConfig.APPLICATION_ID_CONFIG, ...);
properties.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, ...);
properties.put(TopologyConfig.InternalConfig.ENABLE_PROCESS_PROCESSVALUE_FIX, true);

final StreamsBuilder builder = new StreamsBuilder(new TopologyConfig(new StreamsConfig(properties)));
```

Compare `Topology.describe()` output before and after migrating, and test upgrades outside production.

## Controlling KTable emit rate: suppress

To rate-limit downstream effects (e.g. calls to an external system) independent of caching, use `KTable#suppress` (KIP-328):

```java
KGroupedTable<String, String> groupedTable = ...;
groupedTable
    .count()
    .suppress(untilTimeLimit(ofMinutes(5), maxBytes(1_000_000L).emitEarlyWhenFull()))
    .toStream()
    .foreach((key, count) -> updateCountsDatabase(key, count));
```

Each key is emitted at most once per 5 minutes; the latest state per key is buffered in memory (here capped at 1 MB; record-count limits are also possible). When full, `emitEarlyWhenFull()` emits oldest records early; alternatively shut down to strictly enforce the limit. For windowed final results see `Suppressed.untilWindowCloses` in [Joins and windowing](dsl-joins-and-windowing.md#window-final-results).

## Timestamp-based semantics with versioned tables

Tables default to **offset-based** semantics: the record with the largest offset per key is "latest", even if out of order. Since **Streams 3.5**, materializing a table with a **versioned state store** gives **timestamp-based** semantics:

- Stream-table joins use the latest table record with timestamp ≤ the stream record's timestamp.
- Table aggregations (`aggregate`, `count`, `reduce`) and table-table joins (primary-key and foreign-key) use latest-by-timestamp; out-of-order updates don't trigger new results. Joining versioned with unversioned tables combines latest-by-timestamp with latest-by-offset.
- Table `filter` no longer suppresses consecutive tombstones.
- `suppress` is **not allowed** on versioned tables.

<!-- openwiki: broken internal link [processor-api.md#versioned-key-value-state-stores] heading anchor "versioned-key-value-state-stores" does not exist in "processor-api.md". Fix the href or restore the target, then delete this comment. -->
Downstream tables stay versioned until explicitly materialized unversioned, a stateful transformation (aggregation/join) occurs, or the table is converted to a stream and back. **Don't** materialize aggregation or table-table join results with versioned stores. Creating versioned stores: [Processor API](processor-api.md#versioned-key-value-state-stores).

## Writing results back to Kafka

```java
stream.to("my-stream-output-topic");
stream.to("my-stream-output-topic", Produced.with(Serdes.String(), Serdes.Long()));
```

- `to` is terminal. Pass Serdes via `Produced` when types differ from defaults; `Produced` can also set a `StreamPartitioner`. A `TopicNameExtractor` variant chooses the topic per record.
- **Repartitioning happens** if the output topic's partition count differs, the stream was marked for repartitioning, a custom `StreamPartitioner` is used, or the output key is `null`.
- Writing to external systems from a processor is possible but **not recommended** — use [Kafka Connect](../connect/overview-and-running.md); otherwise you own the delivery semantics.

Tables can be written by converting first: `table.toStream().to("topic")`.

## Related pages

- [Joins, windowing and suppression](dsl-joins-and-windowing.md)
- [Processor API](processor-api.md)
- [Serdes and data types](serdes-and-datatypes.md)
- [Naming operators and internal topics](topology-naming-and-description.md)
- [Testing](testing.md)
