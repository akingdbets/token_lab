---
type: tutorial
title: Writing a Kafka Streams Application
description: How to build a Kafka Streams application from scratch — Maven artifacts and the streams-quickstart archetype, the KafkaStreams lifecycle (construct with Topology and Properties, start, uncaught exception handling, close with a shutdown hook), and the step-by-step Pipe, LineSplit and WordCount tutorial programs with their Topology#describe() output, including the repartition topic and counts-store state store.
tags: [streams, tutorial, maven, kafkastreams, wordcount, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-43ebb124020db2122dc2eda6
    resource: repo://docs/streams/developer-guide/write-streams-app.md
  - id: openwiki-source-73e4c9f37b127018ca9c06f8
    resource: repo://docs/streams/tutorial.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Writing a Kafka Streams Application

Any Java or Scala program using the Streams library is a Streams application. Its logic is a **processor topology** defined with the [DSL](dsl-api.md) (recommended starting point: `map`, `filter`, `join`, aggregations) or the [Processor API](processor-api.md) (custom processors and direct store access, more code).

## Dependencies

| Group ID | Artifact ID | Version | Description |
| --- | --- | --- | --- |
| `org.apache.kafka` | `kafka-streams` | `4.3.0` | **Required** base library. |
| `org.apache.kafka` | `kafka-clients` | `4.3.0` | **Required** client library incl. built-in Serdes. |
| `org.apache.kafka` | `kafka-streams-scala` | `4.3.0` | Optional Scala DSL (suffix `_2.12`/`_2.13` when not using SBT) — **deprecated since 4.3, removed in 5.0** ([migration](serdes-and-datatypes.md#scala-migrating-off-kafka-streams-scala)). |

```xml
<dependency>
    <groupId>org.apache.kafka</groupId>
    <artifactId>kafka-streams</artifactId>
    <version>4.3.0</version>
</dependency>
<dependency>
    <groupId>org.apache.kafka</groupId>
    <artifactId>kafka-clients</artifactId>
    <version>4.3.0</version>
</dependency>
```

Add `kafka-streams-test-utils` (test scope) for [testing](testing.md).

## The KafkaStreams lifecycle

```java
StreamsBuilder builder = ...;          // DSL
Topology topology = builder.build();
// or: Topology topology = ...;        // Processor API

Properties props = ...;                // cluster, default Serdes, security, ...
KafkaStreams streams = new KafkaStreams(topology, props);
```

1. **Construct** — `new KafkaStreams(topology, props)` initializes internals but doesn't process yet.
2. **Start** — `streams.start()` launches the stream threads. If other instances of the same `application.id` run elsewhere, tasks are transparently rebalanced to include this one.
3. **Handle errors** — set an uncaught exception handler **before** `start()`. The current API is `StreamsUncaughtExceptionHandler` returning `REPLACE_THREAD`, `SHUTDOWN_CLIENT` or `SHUTDOWN_APPLICATION` ([details](running-and-rebalancing.md#listeners-and-callbacks)); the older `Thread.UncaughtExceptionHandler` form is shown in some docs:

```java
streams.setUncaughtExceptionHandler(exception ->
    StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.SHUTDOWN_CLIENT);
```

4. **Stop** — `streams.close()` (optionally with a timeout). Add a shutdown hook so SIGTERM closes cleanly; afterwards, this instance's tasks migrate to the remaining instances:

```java
// Add shutdown hook to stop the Kafka Streams threads.
// You can optionally provide a timeout to `close`.
Runtime.getRuntime().addShutdownHook(new Thread(streams::close));
```

A clean close also persists state store offsets, reducing restore work after restarts ([RocksDB offset durability](state-stores-and-interactive-queries.md#rocksdb)).

## Tutorial

Assumes a broker on `localhost:9092` (see the [Streams quickstart](introduction-and-quickstart.md)).

### Project setup

```bash
$ mvn archetype:generate \
    -DarchetypeGroupId=org.apache.kafka \
    -DarchetypeArtifactId=streams-quickstart-java \
    -DarchetypeVersion=4.3.0 \
    -DgroupId=streams.examples \
    -DartifactId=streams-quickstart \
    -Dversion=0.1 \
    -Dpackage=myapps
```

```text
streams-quickstart
|-- pom.xml
|-- src
    |-- main
        |-- java
        |   |-- myapps
        |       |-- LineSplit.java
        |       |-- Pipe.java
        |       |-- WordCount.java
        |-- resources
            |-- log4j.properties
```

The generated `pom.xml` already has the Streams dependency and **targets Java 11**. Delete the examples to write them yourself: `cd streams-quickstart && rm src/main/java/myapps/*.java`.

### 1. Pipe — copy a topic

```java
package myapps;

public class Pipe {

    public static void main(String[] args) throws Exception {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "streams-pipe");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass());

        final StreamsBuilder builder = new StreamsBuilder();

        builder.stream("streams-plaintext-input").to("streams-pipe-output");

        final Topology topology = builder.build();
        System.out.println(topology.describe());

        final KafkaStreams streams = new KafkaStreams(topology, props);
        final CountDownLatch latch = new CountDownLatch(1);

        // attach shutdown handler to catch control-c
        Runtime.getRuntime().addShutdownHook(new Thread("streams-shutdown-hook") {
            @Override
            public void run() {
                streams.close();
                latch.countDown();
            }
        });

        try {
            streams.start();
            latch.await();
        } catch (Throwable e) {
            System.exit(1);
        }
        System.exit(0);
    }
}
```

```bash
$ mvn clean package
$ mvn exec:java -Dexec.mainClass=myapps.Pipe
Sub-topologies:
  Sub-topology: 0
    Source: KSTREAM-SOURCE-0000000000(topics: streams-plaintext-input) --> KSTREAM-SINK-0000000001
    Sink: KSTREAM-SINK-0000000001(topic: streams-pipe-output) <-- KSTREAM-SOURCE-0000000000
Global Stores:
  none
```

Key points: `application.id` and `bootstrap.servers` are required; default Serdes here are `String`; `topology.describe()` can be printed at any point to "try and taste" the topology; the app runs until `close()`.

### 2. LineSplit — stateless transformation

Copy `Pipe.java` to `LineSplit.java`, change the class and `application.id` to `streams-linesplit`, then split each line into words:

```java
KStream<String, String> source = builder.stream("streams-plaintext-input");
source.flatMapValues(value -> Arrays.asList(value.split("\\W+")))
      .to("streams-linesplit-output");
```

(The pre-lambda form uses `new ValueMapper<String, Iterable<String>>() { ... }`.)

```text
Sub-topologies:
  Sub-topology: 0
    Source: KSTREAM-SOURCE-0000000000(topics: streams-plaintext-input) --> KSTREAM-FLATMAPVALUES-0000000001
    Processor: KSTREAM-FLATMAPVALUES-0000000001(stores: []) --> KSTREAM-SINK-0000000002 <-- KSTREAM-SOURCE-0000000000
    Sink: KSTREAM-SINK-0000000002(topic: streams-linesplit-output) <-- KSTREAM-FLATMAPVALUES-0000000001
  Global Stores:
    none
```

A `FLATMAPVALUES` processor now sits between source and sink, emitting one record per word.

### 3. WordCount — stateful aggregation

`application.id` `streams-wordcount`:

```java
KStream<String, String> source = builder.stream("streams-plaintext-input");
source.flatMapValues(value -> Arrays.asList(value.toLowerCase(Locale.getDefault()).split("\\W+")))
      .groupBy((key, value) -> value)
      .count(Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("counts-store"))
      .toStream()
      .to("streams-wordcount-output", Produced.with(Serdes.String(), Serdes.Long()));
```

- `groupBy` re-keys by word; `count` keeps a running count in the state store **`counts-store`** (always `KeyValueStore<Bytes, byte[]>` at the innermost layer), queryable via [interactive queries](state-stores-and-interactive-queries.md).
- The result is a changelog stream, so create `streams-wordcount-output` with **log compaction**; values are now `Long`, so pass `Produced.with(Serdes.String(), Serdes.Long())` and read with `LongDeserializer`.

```text
Sub-topologies:
  Sub-topology: 0
    Source: KSTREAM-SOURCE-0000000000(topics: streams-plaintext-input) --> KSTREAM-FLATMAPVALUES-0000000001
    Processor: KSTREAM-FLATMAPVALUES-0000000001(stores: []) --> KSTREAM-KEY-SELECT-0000000002 <-- KSTREAM-SOURCE-0000000000
    Processor: KSTREAM-KEY-SELECT-0000000002(stores: []) --> KSTREAM-FILTER-0000000005 <-- KSTREAM-FLATMAPVALUES-0000000001
    Processor: KSTREAM-FILTER-0000000005(stores: []) --> KSTREAM-SINK-0000000004 <-- KSTREAM-KEY-SELECT-0000000002
    Sink: KSTREAM-SINK-0000000004(topic: counts-store-repartition) <-- KSTREAM-FILTER-0000000005
  Sub-topology: 1
    Source: KSTREAM-SOURCE-0000000006(topics: counts-store-repartition) --> KSTREAM-AGGREGATE-0000000003
    Processor: KSTREAM-AGGREGATE-0000000003(stores: [counts-store]) --> KTABLE-TOSTREAM-0000000007 <-- KSTREAM-SOURCE-0000000006
    Processor: KTABLE-TOSTREAM-0000000007(stores: []) --> KSTREAM-SINK-0000000008 <-- KSTREAM-AGGREGATE-0000000003
    Sink: KSTREAM-SINK-0000000008(topic: streams-wordcount-output) <-- KTABLE-TOSTREAM-0000000007
Global Stores:
  none
```

The topology now has **two sub-topologies** connected by the internal **repartition topic** `counts-store-repartition` (created by `groupBy` because the key changed; a filter drops null keys before it). The second sub-topology's `AGGREGATE` processor reads the current count from `counts-store`, increments it, writes it back and forwards the update; `KTABLE-TOSTREAM` turns table updates into a stream for the sink. Because `counts-store` is explicitly named, its store/changelog names stay stable when you change upstream operators ([naming](topology-naming-and-description.md)).

Run it with `mvn exec:java -Dexec.mainClass=myapps.WordCount` and feed it as in the [quickstart](introduction-and-quickstart.md#step-5-process-some-data).

## Next steps

- [Configuration](configuration.md) — resiliency and exactly-once settings
- [Running, scaling and resetting](running-and-rebalancing.md)
- [Testing with TopologyTestDriver](testing.md)
- [Streams DSL reference](dsl-api.md)
