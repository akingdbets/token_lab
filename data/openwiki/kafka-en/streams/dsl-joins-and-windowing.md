---
type: api-guide
title: "Streams DSL: Joins, Windowing and Suppression"
description: Joining and windowing in the Kafka Streams DSL — supported join types per operand pair, co-partitioning requirements and how to fix mismatches, KStream-KStream windowed joins with JoinWindows, KTable-KTable equi and foreign-key joins, KStream-KTable joins with grace periods, KStream-GlobalKTable lookups, null/tombstone handling, hopping/tumbling/sliding/session windows with grace periods and retention, and emitting final window results with suppress.
tags: [streams, dsl, joins, windowing, suppress, grace-period, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-6d2700367726e79c73735010
    resource: repo://docs/streams/developer-guide/dsl-api.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Streams DSL: Joins, Windowing and Suppression

Builds on [DSL basics](dsl-api.md) and [time and windowing concepts](core-concepts-and-architecture.md#time).

## Joins

Joins enrich records with related data — e.g. a transaction stream with up-to-date prices, inventory and customer info made available in Kafka via change data capture (CDC) and read into tables, with local, low-latency lookups.

| Operands | Type | Inner | Left | Outer |
| --- | --- | --- | --- | --- |
| KStream–KStream | Windowed | ✅ | ✅ | ✅ |
| KTable–KTable | Non-windowed | ✅ | ✅ | ✅ |
| KTable–KTable foreign-key | Non-windowed | ✅ | ✅ | ❌ |
| KStream–KTable | Non-windowed | ✅ | ✅ | ❌ |
| KStream–GlobalKTable | Non-windowed | ✅ | ✅ | ❌ |
| KTable–GlobalKTable | — | ❌ | ❌ | ❌ |

Output records are built with your `ValueJoiner`: `KeyValue.pair(leftRecord.key, joiner.apply(leftRecord.value, rightRecord.value))`.

### Co-partitioning

Equi-joins require **co-partitioned** inputs so records with the same key reach the same task — **this is your responsibility**:

- Both input topics must have the **same number of partitions**.
- All writers must use the **same partitioning strategy** (same producer `partitioner.class`, same `StreamPartitioner` in Streams).

Not required for **KStream–GlobalKTable** joins (each instance has all data; a `KeyValueMapper` enables non-key lookups) and **foreign-key** joins (Streams co-partitions internally).

Streams checks partition counts at assignment time and throws `TopologyBuilderException` if they differ; it can't check partitioning strategies.

**Fixing a mismatch:** find the side with fewer partitions ("SMALLER"), repartition it to match "LARGER" with the same partitioner, then join. Prefer repartitioning the smaller topic up (avoids bottlenecks); for stream-table joins repartition the stream (repartitioning a table may create a second state store).

```java
// SMALLER is a KStream
smaller.repartition(Repartitioned.numberOfPartitions(n));
// SMALLER is a KTable
smaller.toStream().repartition(Repartitioned.numberOfPartitions(n)).toTable();
```

Inner/left/outer joins **repartition a stream only if it was marked** for repartitioning (by `map`, `selectKey`, …).

### KStream–KStream (windowed)

Always windowed, otherwise the join buffer would grow forever. A new record on one side joins with **every** matching record in the window on the other side.

```java
import java.time.Duration;
KStream<String, Long> left = ...;
KStream<String, Double> right = ...;

KStream<String, String> joined = left.join(right,
    (leftValue, rightValue) -> "left=" + leftValue + ", right=" + rightValue, /* ValueJoiner */
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5)),
    Joined.with(
      Serdes.String(), /* key */
      Serdes.Long(),   /* left value */
      Serdes.Double()) /* right value */
  );
// leftJoin(...) and outerJoin(...) have the same shape
```

- Predicate: `leftRecord.key == rightRecord.key` **and** timestamps within the `JoinWindows` difference. The result is a `KStream<K, …>`, not windowed keys.
- Inner: records with `null` key or value are ignored.
- Left: unmatched left records produce `joiner.apply(leftValue, null)`; outer: also `joiner.apply(null, rightValue)`. These non-joined results are emitted **after the grace period passes**. The deprecated `JoinWindows.of(...).grace(...)` API emits them **eagerly**, producing spurious results.
- Grace: `JoinWindows.ofTimeDifferenceAndGrace(diff, grace)`.
- With `dsl.store.format=HEADERS`, inner joins use headers-aware window stores; left/outer buffers for unmatched records are not headers-aware (headers lost). Results don't get merged headers.

### KTable–KTable equi-join

Non-windowed and relational-style: both changelogs are materialized; the result is an ever-updating `KTable`.

```java
KTable<String, Long> left = ...;
KTable<String, Double> right = ...;
KTable<String, String> joined = left.join(right,
    (leftValue, rightValue) -> "left=" + leftValue + ", right=" + rightValue /* ValueJoiner */
  );
// leftJoin, outerJoin
```

- `null` keys ignored. `null` values are tombstones: they don't trigger the joiner but forward a **tombstone to the result** if the key exists there.
- With **versioned** tables, out-of-order records (an older timestamp than already processed for that key) are ignored.

### KTable–KTable foreign-key join

Like `SELECT … FROM this JOIN other ON other.key = foreignKeyExtractor(this.value)`; no co-partitioning needed.

```java
// map the left value to the right key
Function<Long, String> foreignKeyExtractor = (v) -> v.toString();
// alternative with access to the left key
BiFunction<String, Long, String> foreignKeyExtractor2 = (k, v) -> v.toString();

KTable<String, String> joined = left.join(right, foreignKeyExtractor,
    (leftValue, rightValue) -> "left=" + leftValue + ", right=" + rightValue /* ValueJoiner */
  );
// leftJoin is supported, outer is not
```

- Many left rows may map to one right key; a right update produces an update **for each** left row with that foreign key.
- Records whose extractor returns `null` are ignored — use a sentinel (`"NULL"`, `-1`) to join on null keys.
- Tombstones and versioned-table behavior as for equi-joins.

### KStream–KTable

Table lookups on each stream record (e.g. enrich activity with the latest profile).

```java
KStream<String, Long> left = ...;
KTable<String, Double> right = ...;
KStream<String, String> joined = left.join(right,
    (leftValue, rightValue) -> "left=" + leftValue + ", right=" + rightValue, /* ValueJoiner */
    Joined.keySerde(Serdes.String()) /* key */
      .withValueSerde(Serdes.Long()) /* left value */
      .withGracePeriod(Duration.ZERO) /* grace period */
  );
// leftJoin is supported
```

- **Only stream records trigger the join**; table records just update the table side.
- Stream records with `null` key or value are ignored; table `null` values are tombstones.
- `Joined#withGracePeriod` buffers stream records to handle out-of-order data against a **versioned** table (timestamp-based lookup of the table version ≤ the stream timestamp).

### KStream–GlobalKTable

Like KStream-KTable, but:

- no co-partitioning;
- efficient **star joins** of a large fact stream against dimension tables;
- **foreign-key lookups** via a `KeyValueMapper` on the stream record;
- good for skewed data/hot partitions and chains of joins.

```java
KStream<String, Long> left = ...;
GlobalKTable<Integer, Double> right = ...;
KStream<String, String> joined = left.join(right,
    (leftKey, leftValue) -> leftKey.length(), /* derive a (potentially) new key by which to lookup against the table */
    (leftValue, rightValue) -> "left=" + leftValue + ", right=" + rightValue /* ValueJoiner */
  );
```

The predicate is `KeyValueMapper#apply(leftRecord.key, leftRecord.value) == rightRecord.key`. The global table is **fully bootstrapped on (re)start** before processing begins.

## Windowing

Windows sub-group records **of the same key** for aggregations and joins; windows are tracked per key. Window state is kept for at least the **retention period — default one day**, changeable via `Materialized#withRetention()`. Records arriving after **window end + grace** are dropped.

| Window | Behavior | Description |
| --- | --- | --- |
| Hopping | Time-based | Fixed size, overlapping |
| Tumbling | Time-based | Fixed size, non-overlapping, gap-less |
| Sliding | Time-based | Fixed size, overlapping, based on differences between record timestamps |
| Session | Session-based | Dynamically sized, non-overlapping, data-driven |

Windowed aggregations return a **windowed KTable** with `Windowed<K>` keys; use `Windowed#window()` and `Windowed#key()`.

### Hopping

Defined by **size** and **advance** ("hop"); records can belong to several windows. Other systems sometimes call these "sliding" — Kafka Streams follows academic terminology where sliding windows differ.

```java
import java.time.Duration;
import org.apache.kafka.streams.kstream.TimeWindows;

// size 5 minutes, advance 1 minute
TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)).advanceBy(Duration.ofMinutes(1));
```

Windows are **aligned to the epoch** with inclusive start and exclusive end: size 5000 ms, hop 3000 ms → `[0;5000), [3000;8000), …`. Time units are milliseconds.

### Tumbling

A hopping window whose advance equals its size; each record is in exactly one window. Epoch-aligned: `[0;5000), [5000;10000), …`.

```java
// size 5 minutes, grace 1 minute
TimeWindows.ofSizeAndGrace(Duration.ofMinutes(5), Duration.ofMinutes(1));
// equivalent
TimeWindows.ofSizeAndGrace(Duration.ofMinutes(5), Duration.ofMinutes(1)).advanceBy(Duration.ofMinutes(5));
```

### Sliding

Used by joins (`JoinWindows`) and windowed aggregations (`SlidingWindows`). Two records are in the same window if their timestamp difference is within the window size; each unique combination of records appears in exactly one window snapshot. **Aligned to record timestamps** (not the epoch), with **both bounds inclusive**.

```java
import org.apache.kafka.streams.kstream.SlidingWindows;
// time difference 10 minutes, grace 30 minutes
SlidingWindows.ofTimeDifferenceAndGrace(Duration.ofMinutes(10), Duration.ofMinutes(30));
```

### Session

Sessions are periods of activity separated by an **inactivity gap**. Events within the gap of an existing session merge into it (possibly merging sessions); others start new sessions. Windows are independent per key and vary in size — ideal for **user behavior analysis**.

```java
import org.apache.kafka.streams.kstream.SessionWindows;
// inactivity gap 5 minutes
SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(5));
```

Session aggregations need an additional **session merger** aggregator:

```java
KTable<Windowed<String>, Long> sessionized = groupedStream
    .windowedBy(SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(5)))
    .aggregate(
        () -> 0L,                                             /* initializer */
        (aggKey, newValue, aggValue) -> aggValue + newValue,  /* adder */
        (aggKey, leftAggValue, rightAggValue) -> leftAggValue + rightAggValue, /* session merger */
        Materialized.<String, Long, SessionStore<Bytes, byte[]>>as("sessionized-aggregated-stream-store")
            .withValueSerde(Serdes.Long()));
```

Example: green records at t=0 and t=6 and a blue record at t=2 form three sessions; a late green record at t=4 merges the two green sessions into `[0,6]`, a late blue at t=5 extends the blue session to `[2,5]`, and a blue at t=11 starts a new session.

## Window final results

Windowed computations emit **continuous updates**. To act only on the **final** result (alerts, sinks that can't handle updates), suppress intermediate results until the window closes:

```java
KGroupedStream<UserId, Event> grouped = ...;
grouped
    .windowedBy(TimeWindows.ofSizeAndGrace(Duration.ofHours(1), Duration.ofMinutes(10)))
    .count()
    .suppress(Suppressed.untilWindowCloses(unbounded()))
    .filter((windowedUserId, count) -> count < 3)
    .toStream()
    .foreach((windowedUserId, count) -> sendAlert(windowedUserId.window(), windowedUserId.key(), count));
```

- `ofSizeAndGrace(1h, 10min)`: the 09:00–10:00 window accepts late records until 10:10, then **closes**.
- `Suppressed.untilWindowCloses(...)` emits nothing until close, then exactly one final value per windowed key (e.g. `U@09:00-10:00` → `10` at 10:10).
- `unbounded()` buffer has no memory cap — cap it in production (`maxBytes`, `maxRecords`).
- Suppression is an ordinary operator: you can branch suppressed and unsuppressed paths. See KIP-328 and `Suppressed`. For non-windowed rate limiting use `untilTimeLimit` ([DSL basics](dsl-api.md#controlling-ktable-emit-rate-suppress)).

## Related pages

- [Streams DSL basics](dsl-api.md)
- [Concepts: time, windowing, out-of-order](core-concepts-and-architecture.md)
- [Versioned stores (Processor API)](processor-api.md)
- [State stores and memory](state-stores-and-interactive-queries.md)
