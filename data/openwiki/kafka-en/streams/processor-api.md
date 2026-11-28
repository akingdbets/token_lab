---
type: api-guide
title: Streams Processor API
description: The low-level Kafka Streams Processor API — implementing Processor<KIn,VIn,KOut,VOut> with init/process/close and Record, scheduling punctuations on stream time or wall-clock time, building state stores with the Stores factory (persistent RocksDB, in-memory, timestamped, versioned, headers-aware, read-only, custom), changelog-based fault tolerance and tuning, ProcessorContext, and wiring sources, processors, stores and sinks with Topology.
tags: [streams, processor-api, state-stores, punctuation, topology, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-29f0fa11c924a148287f47a6
    resource: repo://docs/streams/developer-guide/processor-api.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Streams Processor API

The Processor API lets you define custom stream processors that handle **one record at a time** and connect them with **state stores**, for stateless or stateful logic the DSL doesn't offer (e.g. access to record metadata, custom scheduling). You can also combine it with the DSL via `KStream#process` / `processValues` ([DSL](dsl-api.md#custom-processing-process-and-processvalues)). Testing: [`test-utils`](testing.md).

## Defining a processor

Implement `org.apache.kafka.streams.processor.api.Processor<KIn, VIn, KOut, VOut>`:

- `init(ProcessorContext<KOut, VOut>)` — called during task construction; do initialization, fetch stores, schedule punctuations. The context gives access to record metadata (topic, partition, offset) and lets you forward records.
- `process(Record<KIn, VIn>)` — called for each received record.
- `close()` — release resources (**don't close state stores**; Streams manages them).

Type parameters: `KIn`/`VIn` are the input key/value types; `KOut`/`VOut` are what `context.forward()` accepts (use `Void` if you never forward non-null keys/values). Records are `Record<K, V>` with key, value, timestamp and headers; derive outputs with builders like `inputRecord.withValue(newValue)`. For key-preserving logic use `FixedKeyProcessor` / `FixedKeyRecord`; `ContextualProcessor` and `ContextualFixedKeyProcessor` manage the context for you.

### Punctuation

Schedule periodic callbacks in `init()` with `ProcessorContext#schedule(Duration, PunctuationType, Punctuator)`:

| `PunctuationType` | Triggered by | Example: 60 records with timestamps 1…60 s, schedule every 10 s |
| --- | --- | --- |
| `STREAM_TIME` | Record timestamps (event time by default) | `punctuate()` runs **6 times**, regardless of how long processing takes. |
| `WALL_CLOCK_TIME` | System time | Processed in 20 s → **2** calls; processed in 5 s → **0** calls. |

**Stream time only advances when records are processed.** With no input (or while waiting due to `max.task.idle.ms`), `STREAM_TIME` punctuations don't fire — even if you use `WallclockTimestampExtractor`. Multiple punctuators can be scheduled.

### Example: word count processor

```java
public class WordCountProcessor implements Processor<String, String, String, String> {
    private KeyValueStore<String, Integer> kvStore;

    @Override
    public void init(final ProcessorContext<String, String> context) {
        context.schedule(Duration.ofSeconds(1), PunctuationType.STREAM_TIME, timestamp -> {
            try (final KeyValueIterator<String, Integer> iter = kvStore.all()) {
                while (iter.hasNext()) {
                    final KeyValue<String, Integer> entry = iter.next();
                    context.forward(new Record<>(entry.key, entry.value.toString(), timestamp));
                }
            }
        });
        kvStore = context.getStateStore("Counts");
    }

    @Override
    public void process(final Record<String, String> record) {
        final String[] words = record.value().toLowerCase(Locale.getDefault()).split("\\W+");

        for (final String word : words) {
            final Integer oldValue = kvStore.get(word);

            if (oldValue == null) {
                kvStore.put(word, 1);
            } else {
                kvStore.put(word, oldValue + 1);
            }
        }
    }

    @Override
    public void close() {
        // close any resources managed by this processor
        // Note: Do not close any StateStores as these are managed by the library
    }
}
```

## State stores

Stateful processors need one or more state stores — to remember recent records, keep rolling aggregates, deduplicate, etc. Stores can also be [interactively queried](state-stores-and-interactive-queries.md). Built-in stores are **fault-tolerant by default**.

You don't instantiate stores directly; you define a **`StoreBuilder`** (usually via the `Stores` factory) that Streams uses to create store instances where needed.

### Built-in store types

| Store | Engine | Notes |
| --- | --- | --- |
| Persistent `KeyValueStore<K, V>` | RocksDB | **Recommended for most uses.** Data on local disk; can exceed heap but must fit on disk; tunable via `rocksdb.config.setter`. Variants: `persistentKeyValueStore` (plain), `persistentTimestampedKeyValueStore`, `persistentVersionedKeyValueStore`, `persistentWindowStore` / `persistentTimestampedWindowStore`, `persistentSessionStore`. |
| In-memory `KeyValueStore<K, V>` | — | Must fit in heap; good when local disk is unavailable or wiped between restarts. Variants: key-value, window, session (`inMemoryKeyValueStore`, …). **No in-memory versioned store.** |

```java
// persistent
StoreBuilder<KeyValueStore<String, Long>> countStoreSupplier =
  Stores.keyValueStoreBuilder(
    Stores.persistentKeyValueStore("persistent-counts"),
    Serdes.String(),
    Serdes.Long());
KeyValueStore<String, Long> countStore = countStoreSupplier.build();

// in-memory
StoreBuilder<KeyValueStore<String, Long>> inMemoryStoreSupplier =
  Stores.keyValueStoreBuilder(
    Stores.inMemoryKeyValueStore("inmemory-counts"),
    Serdes.String(),
    Serdes.Long());
```

**Always close iterators** (`KeyValueIterator`) — e.g. with try-with-resources — or you risk OOM errors.

### Fault tolerance (changelogs)

Stores are continuously backed up to a **compacted changelog topic**, enabling recovery and task migration without data loss. Window store changelogs use **compaction and deletion**, because their composite keys (key + window timestamp) would otherwise grow without bound.

```java
// disable changelogging: no fault tolerance, no standby replicas
StoreBuilder<KeyValueStore<String, Long>> noLog = Stores.keyValueStoreBuilder(
  Stores.persistentKeyValueStore("Counts"),
  Serdes.String(),
  Serdes.Long())
  .withLoggingDisabled();

// enable with custom changelog topic configs (unrecognized configs are ignored)
Map<String, String> changelogConfig = new HashMap<>();
changelogConfig.put(TopicConfig.MIN_IN_SYNC_REPLICAS_CONFIG, "1");
StoreBuilder<KeyValueStore<String, Long>> withLog = Stores.keyValueStoreBuilder(
  Stores.persistentKeyValueStore("Counts"),
  Serdes.String(),
  Serdes.Long())
  .withLoggingEnabled(changelogConfig);
```

### Timestamped stores

KTables always store timestamps. Timestamped stores improve semantics (out-of-order handling in source KTables, detecting out-of-order joins/aggregations, latest-update timestamps in interactive queries) and can be queried with or without timestamps. Upgrading needs a single rolling bounce; DSL store data upgrades lazily; custom `XxxBytesStoreSupplier`s can opt in by implementing `TimestampedBytesStore` (Streams then uses a proxy that adds/strips timestamps).

### Headers in state stores

To keep record headers in state (e.g. so a Processor API aggregation/join can propagate them), use **persistent, RocksDB-only** `…WithHeaders` suppliers with matching builders:

- `persistentTimestampedKeyValueStoreWithHeaders` + `timestampedKeyValueStoreWithHeadersBuilder`
- `persistentTimestampedWindowStoreWithHeaders` + `timestampedWindowStoreWithHeadersBuilder`
- `persistentSessionStoreWithHeaders` + `sessionStoreWithHeadersBuilder`

Key-value/window reads return `ValueTimestampHeaders`; session stores hold `AggregationWithHeaders`. There are no `WithHeaders` variants for plain key-value or plain window stores. (DSL: `dsl.store.format=HEADERS`.)

### Versioned key-value stores

Since **Streams 3.5**, versioned stores keep **multiple versions per key**, supporting "latest as of timestamp T" lookups; they underpin [timestamp-based table semantics](dsl-api.md#timestamp-based-semantics-with-versioned-tables).

```java
StoreBuilder<VersionedKeyValueStore<String, Long>> versioned =
  Stores.versionedKeyValueStoreBuilder(
    Stores.persistentVersionedKeyValueStore("versioned-counts", Duration.ofDays(1)), // history retention
    Serdes.String(),
    Serdes.Long());
```

- **History retention** is fixed per store: lookups are accurate for timestamps within retention of the current stream time.
- It doubles as the **grace period**: writes older than stream time minus grace are rejected. Stream time is tracked **per partition**, not per key — set it high enough.
- Higher memory footprint and slower than non-versioned stores — tune RocksDB memory and benchmark.
- **No caching or interactive queries** yet; window stores and global tables can't be versioned.
- Opt-in only. To migrate a persistent (plain or timestamped) key-value store: stop all instances and clear local state for those stores; switch the code; set the changelog topic's `min.compaction.lag.ms` ≥ history retention (retention + 1 day recommended); restart and let stores rebuild.

### Read-only stores

A read-only store materializes an input topic and reuses it as its changelog (configure that topic with log compaction). Only its "state update processor" may write; other processors may only read. Watch co-partitioning when using it for lookups.

### Custom stores

Implement `org.apache.kafka.streams.processor.StateStore` (or `KeyValueStore`, `VersionedKeyValueStore`, …), restoration via `StateRestoreCallback` or `BatchingStateRestoreCallback`, and a `StoreBuilder`.

## ProcessorContext

Besides `forward()`, `schedule()` and `commit()`, the context exposes application metadata — `applicationId()`, `taskId()`, `stateDir()` — and record metadata (`topic`, `partition`, `offset`) via `recordMetadata()`.

## Building a topology

```java
Topology builder = new Topology();
// add the source processor node that takes Kafka topic "source-topic" as input
builder.addSource("Source", "source-topic")
    // add the WordCountProcessor node which takes the source processor as its upstream processor
    .addProcessor("Process", () -> new WordCountProcessor(), "Source")
    // add the count store associated with the WordCountProcessor processor
    .addStateStore(countStoreBuilder, "Process")
    // add the sink processor node that takes Kafka topic "sink-topic" as output
    // and the WordCountProcessor node as its upstream processor
    .addSink("Sink", "sink-topic", "Process");
```

Alternatively the `ProcessorSupplier` can **own** its stores by implementing `ConnectedStoreProvider#stores()`:

```java
builder.addSource("Source", "source-topic")
    .addProcessor("Process", new ProcessorSupplier<String, String, String, String>() {
        public Processor<String, String, String, String> get() {
            return new WordCountProcessor();
        }
        public Set<StoreBuilder<?>> stores() {
            final StoreBuilder<KeyValueStore<String, Long>> countsStoreBuilder =
                Stores.keyValueStoreBuilder(
                    Stores.persistentKeyValueStore("Counts"),
                    Serdes.String(),
                    Serdes.Long());
            return Collections.singleton(countsStoreBuilder);
        }
    }, "Source")
    .addSink("Sink", "sink-topic", "Process");
```

Processors sharing a store may each provide it this way if they use the **same `StoreBuilder` instance**. Records forwarded by the source trigger `process()`; `forward()` calls (e.g. from the punctuator) send records to the sink. `addSink` has variants choosing the topic per record.

**`ProcessorSupplier#get()` must return a new `Processor` instance every time** — returning a singleton violates the supplier pattern and causes runtime exceptions.

Then [run the application](running-and-rebalancing.md): `new KafkaStreams(builder, props).start()`.

## Related pages

- [Streams DSL](dsl-api.md)
- [State stores, interactive queries and memory](state-stores-and-interactive-queries.md)
- [Testing with TopologyTestDriver](testing.md)
- [Concepts and architecture](core-concepts-and-architecture.md)
