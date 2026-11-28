---
type: "Reference"
title: "State Stores, Interactive Queries and Memory Management"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-c5deb020b2f89d5dccbe87a1
    resource: repo://docs/streams/developer-guide/interactive-queries.md
  - id: openwiki-source-4782913d21c18656da8decb1
    resource: repo://docs/streams/developer-guide/memory-mgmt.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---


# State Stores, Interactive Queries and Memory Management

State stores are created by DSL stateful operators or explicitly in the [Processor API](processor-api.md#state-stores). This page covers reading them from outside the topology (**Interactive Queries**, IQ) and controlling the memory they and their caches use.

## Interactive Queries overview

An application's state is split across instances and many local stores (**one store per stream partition**). IQ has a local and a remote part:

| Capability | App instance | Entire application |
| --- | --- | --- |
| Query local stores | ✅ | ✅ |
| Make an instance discoverable | ✅ | ✅ |
| Discover running instances and their stores | ✅ | ✅ |
| Communicate over the network (RPC) | ✅ | ❌ — **you must add an RPC layer** |

Queries are **read-only** — you can't mutate stores out of band. **Versioned state stores don't support IQ** yet.

## Querying local stores

Use `KafkaStreams#store(StoreQueryParameters.fromNameAndType(name, type))`. The store name comes from `Materialized.as(...)` (DSL) or the `StoreBuilder` (Processor API); the type from `QueryableStoreTypes`:

| `QueryableStoreTypes` | Returns |
| --- | --- |
| `keyValueStore()` | `ReadOnlyKeyValueStore<K, V>` (values only) |
| `timestampedKeyValueStore()` | `ReadOnlyKeyValueStore<K, ValueAndTimestamp<V>>` |
| `timestampedKeyValueStoreWithHeaders()` | header-aware key-value store |
| `windowStore()` / `timestampedWindowStore()` | `ReadOnlyWindowStore<K, V>` / with timestamps |
| `timestampedWindowStoreWithHeaders()` | header-aware window store |
| `sessionStore()` / `sessionStoreWithHeaders()` | `ReadOnlySessionStore` |

You can also implement a custom `QueryableStoreType`. The API transparently queries all local partitions of a store.

### Key-value stores

```java
// topology: all-time word counts in store "CountsKeyValueStore"
KGroupedStream<String, String> groupedByWord = textLines
  .flatMapValues(value -> Arrays.asList(value.toLowerCase().split("\\W+")))
  .groupBy((key, word) -> word, Grouped.with(stringSerde, stringSerde));
groupedByWord.count(Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("CountsKeyValueStore"));

KafkaStreams streams = new KafkaStreams(builder.build(), props);
streams.start();

// query
ReadOnlyKeyValueStore<String, Long> keyValueStore =
    streams.store(StoreQueryParameters.fromNameAndType(
        "CountsKeyValueStore", QueryableStoreTypes.keyValueStore()));

System.out.println("count for hello:" + keyValueStore.get("hello"));

try (KeyValueIterator<String, Long> range = keyValueStore.range("all", "streams")) {
  while (range.hasNext()) {
    KeyValue<String, Long> next = range.next();
    System.out.println("count for " + next.key + ": " + next.value);
  }
}

try (KeyValueIterator<String, Long> all = keyValueStore.all()) { /* ... */ }
```

Stateless `KTable` results can be made queryable by materializing them:

```java
KTable<String, Integer> oddCounts = numberLines.filter((region, count) -> (count % 2 != 0),
  Materialized.<String, Integer, KeyValueStore<Bytes, byte[]>>as("queryableStoreName"));
```

### Window stores

A key can appear in many windows (one result per window):

```java
groupedByWord.windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofSeconds(60)))
  .count(Materialized.<String, Long, WindowStore<Bytes, byte[]>>as("CountsWindowStore"));

ReadOnlyWindowStore<String, Long> windowStore =
    streams.store(StoreQueryParameters.fromNameAndType(
        "CountsWindowStore", QueryableStoreTypes.windowStore()));

Instant timeFrom = Instant.ofEpochMilli(0); // beginning of time = oldest available
Instant timeTo = Instant.now();             // now (in processing-time)
try (WindowStoreIterator<Long> iterator = windowStore.fetch("world", timeFrom, timeTo)) {
  while (iterator.hasNext()) {
    KeyValue<Long, Long> next = iterator.next();   // (window start timestamp, count)
    long windowTimestamp = next.key;
    System.out.println("Count of 'world' @ time " + windowTimestamp + " is " + next.value);
  }
}
```

### IQv2 (query API)

IQv2 builds a `Query`, wraps it in a `StateQueryRequest`, and runs `KafkaStreams#query(...)`, returning per-partition `QueryResult`s. **KIP-1356** adds `@Evolving` header-aware query types returning `ReadOnlyRecord` (value, timestamp, headers), e.g. `TimestampedKeyWithHeadersQuery` (parallel to `TimestampedKeyQuery`) and `TimestampedRangeWithHeadersQuery` (parallel to `TimestampedRangeQuery`):

```java
TimestampedKeyWithHeadersQuery<String, Long> query =
    TimestampedKeyWithHeadersQuery.withKey("hello");

StateQueryRequest<ReadOnlyRecord<String, Long>> request =
    StateQueryRequest.inStore("counts-store").withQuery(query);

StateQueryResult<ReadOnlyRecord<String, Long>> result = streams.query(request);
QueryResult<ReadOnlyRecord<String, Long>> partitionResult = result.getOnlyPartitionResult();
if (partitionResult != null && partitionResult.isSuccess()) {
  ReadOnlyRecord<String, Long> record = partitionResult.getResult();
  if (record != null) {
    System.out.println("value:   " + record.value());
    System.out.println("headers: " + record.headers());
  }
}
```

- `.skipCache()` (e.g. `TimestampedKeyWithHeadersQuery.<String, Long>withKey("hello").skipCache()`) bypasses the record cache.
- Range queries return a `ReadOnlyRecordIterator` (close it) and may span several partitions — iterate `getPartitionResults()`.
- Header-aware stores require the matching `*WithHeaders` store types ([headers in stores](processor-api.md#headers-in-state-stores)).

## Querying the entire application (remote state)

To expose the full state (e.g. serving each game player's latest status to a mobile app):

1. **Add an RPC layer** (REST, Thrift, custom) embedded in the app.
2. **Expose its endpoint** via `application.server` — a unique `host:port` per instance:

```java
Properties props = new Properties();
String rpcEndpoint = "host1:4460";
props.put(StreamsConfig.APPLICATION_SERVER_CONFIG, rpcEndpoint);

KStream<String, String> textLines = builder.stream("word-count-input", Consumed.with(stringSerde, stringSerde));
textLines
  .flatMapValues(value -> Arrays.asList(value.toLowerCase().split("\\W+")))
  .groupBy((key, word) -> word, Grouped.with(stringSerde, stringSerde))
  .count(Materialized.as("word-count"));   // discoverable, queryable store

KafkaStreams streams = new KafkaStreams(builder.build(), props);
streams.start();

MyRPCService rpcService = ...;   // your service, on the same host:port
rpcService.listenAt(rpcEndpoint);
```

3. **Discover instances** with `StreamsMetadata`, then query locally or forward to the right instance:

| Method | Returns |
| --- | --- |
| `KafkaStreams#allMetadata()` | All instances of this app. |
| `KafkaStreams#allMetadataForStore(String storeName)` | Instances hosting that store. |
| `KafkaStreams#metadataForKey(String storeName, K key, Serializer<K> keySerializer)` | The instance holding `key` (default partitioning). |
| `KafkaStreams#metadataForKey(String storeName, K key, StreamPartitioner<K, ?> partitioner)` | Same with a custom partitioner. |

If `application.server` isn't set on an instance, these methods find **no metadata** for it.

```java
// Approach 1: ask the instance that owns 'alice'
StreamsMetadata metadata = streams.metadataForKey("word-count", "alice", Serdes.String().serializer());
Long result = http.getLong("http://" + metadata.host() + ":" + metadata.port() + "/word-count/alice");

// Approach 2: brute force over all hosts of the store
Optional<Long> result2 = streams.allMetadataForStore("word-count")
    .stream()
    .map(m -> http.getLong("http://" + m.host() + ":" + m.port() + "/word-count/alice"))
    .filter(s -> s != null)
    .findFirst();
```

The RPC endpoints can carry other inter-instance traffic too. See the KafkaMusicExample demo for an end-to-end implementation. IQ also works with the [streams rebalance protocol](running-and-rebalancing.md#streams-rebalance-protocol-kip-1071).

## Memory management

### Record caches in the DSL

A per-instance record cache sits in front of **source KTables** (`StreamsBuilder#table()`, `#globalTable()`) and **aggregation KTables**, caching and compacting output records before they are written to state stores **and** before they are forwarded downstream.

Example: summing values for key `A` with inputs `<A,1>, <D,5>, <A,20>, <A,300>` — without caching you get `<A,(1,null)>, <A,(21,1)>, <A,(321,21)>`; with caching likely a single `<A,(321,null)>`.

```java
Properties props = new Properties();
// Enable record cache of size 10 MB.
props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 10 * 1024 * 1024L);   // statestore.cache.max.bytes in newer releases
// Set commit interval to 1 second.
props.put(StreamsConfig.COMMIT_INTERVAL_MS_CONFIG, 1000);

// Disable record cache
props.put(StreamsConfig.CACHE_MAX_BYTES_BUFFERING_CONFIG, 0);
```

- The size is global per instance: with `T` threads and `C` bytes, each thread gets `C/T` for its own cache (no sharing across threads).
- LRU eviction; a newer record for the same key **overwrites** ("compacts") the dirty entry — similar to log compaction.
- Data is flushed to the store and forwarded downstream at the **earliest** of `commit.interval.ms` or cache pressure. Both settings are global (not per node). Small caches → output driven by cache pressure; large caches → by commit interval. In the docs' illustration, caching cut 15 output records to 8.

### Record caches in the Processor API

The cache only compacts writes **to state stores**; forwarded records are **not** cached, so downstream processors see everything. Toggle per store:

```java
StoreBuilder<KeyValueStore<String, Long>> countStoreBuilder =
  Stores.keyValueStoreBuilder(
    Stores.persistentKeyValueStore("Counts"),
    Serdes.String(),
    Serdes.Long())
  .withCachingEnabled();     // or .withCachingDisabled()
```

Versioned stores don't support caching. Avoid frequent manual `flush()` calls (costly with RocksDB).

### RocksDB

Each RocksDB instance allocates **off-heap** memory for the block cache, index/filter blocks and memtables (write buffers). Key options: `block_cache_size`, `write_buffer_size`, `max_write_buffer_number` — set them with a `RocksDBConfigSetter` (`rocksdb.config.setter`).

**Changelog offset durability (since 4.3, KIP-1035):** each persistent store's changelog offset is stored **inside RocksDB** instead of a per-task `.checkpoint` file. With the WAL disabled (the changelog is the durable log), data and offset hit disk only when a memtable **flushes** to an SST file. For **low-traffic stores**, the persisted offset can lag far behind; after an unclean exit (SIGKILL, OOM-kill, incomplete `close()`), more changelog must be replayed. Mitigate by shrinking the write buffer for those stores and, above all, by **clean shutdown** (shutdown hook calling `KafkaStreams#close`):

```java
public static class CustomRocksDBConfig implements RocksDBConfigSetter {
    @Override
    public void setConfig(final String storeName, final Options options, final Map<String, Object> configs) {
        // smaller write buffer => more frequent flushes => fresher on-disk changelog offset
        options.setWriteBufferSize(4 * 1024 * 1024L);
    }
    @Override
    public void close(final String storeName, final Options options) {}
}
```

Flushing is **volume-based, not time-based**.

**Restore performance:** bulk restoration through a small buffer creates many L0 SST files and compaction work, possibly stalling on `level0_slowdown_writes_trigger` / `level0_stop_writes_trigger` or `max_write_buffer_number`. For slow-to-restore large stores, raise `write_buffer_size` above the **16 MB default** (32–64 MB is a reasonable start, e.g. `options.setWriteBufferSize(64 * 1024 * 1024L)`) and consider a higher `level0_file_num_compaction_trigger` — costs off-heap memory. (Opposite advice to the low-traffic case, for a different problem.)

**Allocator:** the default allocator can inflate memory use; use **jemalloc**:

```bash
# example: install jemalloc (on Debian)
$ apt install -y libjemalloc-dev
# set LD_PRELOAD before you start your Kafka Streams application
$ export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so"
```

**Bounding total off-heap memory (since 2.3):** cache index and filter blocks in the block cache, limit memtables with a shared `WriteBufferManager` counted against that cache, and share **one** `Cache` across all store instances:

```java
public static class BoundedMemoryRocksDBConfig implements RocksDBConfigSetter {
    private static org.rocksdb.Cache cache = new org.rocksdb.LRUCache(TOTAL_OFF_HEAP_MEMORY, -1, false, INDEX_FILTER_BLOCK_RATIO);
    private static org.rocksdb.WriteBufferManager writeBufferManager = new org.rocksdb.WriteBufferManager(TOTAL_MEMTABLE_MEMORY, cache);

    @Override
    public void setConfig(final String storeName, final Options options, final Map<String, Object> configs) {
        BlockBasedTableConfig tableConfig = (BlockBasedTableConfig) options.tableFormatConfig();
        // These three options in combination will limit the memory used by RocksDB to the size passed to the block cache (TOTAL_OFF_HEAP_MEMORY)
        tableConfig.setBlockCache(cache);
        tableConfig.setCacheIndexAndFilterBlocks(true);
        options.setWriteBufferManager(writeBufferManager);
        // recommended when bounding total memory
        tableConfig.setCacheIndexAndFilterBlocksWithHighPriority(true);
        tableConfig.setPinTopLevelIndexAndFilter(true);
        tableConfig.setBlockSize(BLOCK_SIZE);
        options.setMaxWriteBufferNumber(N_MEMTABLES);
        options.setWriteBufferSize(MEMTABLE_SIZE);
        options.setTableFormatConfig(tableConfig);
    }

    @Override
    public void close(final String storeName, final Options options) {
        // Cache and WriteBufferManager should not be closed here, as the same objects are shared by every store instance.
    }
}
```

`INDEX_FILTER_BLOCK_RATIO` reserves high-priority cache space for index/filter blocks (requires `setCacheIndexAndFilterBlocksWithHighPriority(true)`); the `LRUCache` boolean controls strict capacity enforcement; a larger `BLOCK_SIZE` shrinks index blocks but may cache colder data. Best settings are workload-dependent — benchmark; consider partitioned index filters. Monitor with [RocksDB metrics](../monitoring/client-metrics.md#rocksdb).

### Other memory consumers

- Producer buffering: `buffer.memory`.
- Consumer buffering: not strictly bounded; influenced by `fetch.max.bytes` and `fetch.max.wait.ms`.
- TCP buffers: `send.buffer.bytes` / `receive.buffer.bytes` (not counted above).
- Deserialized records buffered after `poll()`: indirectly bounded by `buffered.records.per.partition` (default 1000).
- **Always close store iterators** (`KeyValueIterator`, `WindowStoreIterator`) — or use try-with-resources — otherwise memory grows until OOM.

## Related pages

- [Processor API and state store types](processor-api.md)
- [Configuration](configuration.md)
- [Concepts: state and fault tolerance](core-concepts-and-architecture.md)
- [Streams metrics](../monitoring/client-metrics.md#kafka-streams-metrics)
