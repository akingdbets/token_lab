---
type: tutorial
title: "Kafka Streams: Introduction and Quickstart"
description: What Kafka Streams is and why to use it, the Hello Kafka Streams WordCountApplication in Java, and the step-by-step WordCountDemo quickstart — creating input and compacted output topics, running the demo with kafka-run-class.sh (optionally with group.protocol=streams), producing lines and reading the continuously updated counts — explained through the KTable/changelog duality.
tags: [streams, quickstart, tutorial, wordcount, getting-started]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-a78445f12c0928bfc8ffbb36
    resource: repo://docs/streams/introduction.md
  - id: openwiki-source-c801af17c40baebe8874a583
    resource: repo://docs/streams/quickstart.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Kafka Streams: Introduction and Quickstart

## What it is

Kafka Streams is a **client library** for building applications and microservices whose input and output data live in Kafka. It combines writing and deploying ordinary **Java and Scala** applications with Kafka's server-side cluster technology.

Why use it:

- Elastic, highly scalable, fault-tolerant.
- Deploy to containers, VMs, bare metal or cloud.
- Suitable for small, medium and large use cases.
- Fully integrated with Kafka security.
- Standard Java/Scala applications; develop on Mac, Linux or Windows.
- **Exactly-once** processing semantics.
- **No separate processing cluster** required.

Dependency: `org.apache.kafka:kafka-streams` ([APIs overview](../clients/apis-overview.md)). Concepts: [Concepts and architecture](core-concepts-and-architecture.md).

## Hello Kafka Streams

A WordCount that is elastic, scalable, fault-tolerant, stateful and production-ready:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.KTable;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.state.KeyValueStore;

import java.util.Arrays;
import java.util.Properties;

public class WordCountApplication {

    public static void main(final String[] args) throws Exception {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "wordcount-application");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka-broker1:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass());

        StreamsBuilder builder = new StreamsBuilder();
        KStream<String, String> textLines = builder.stream("TextLinesTopic");
        KTable<String, Long> wordCounts = textLines
            .flatMapValues(textLine -> Arrays.asList(textLine.toLowerCase().split("\\W+")))
            .groupBy((key, word) -> word)
            .count(Materialized.<String, Long, KeyValueStore<Bytes, byte[]>>as("counts-store"));
        wordCounts.toStream().to("WordsWithCountsTopic", Produced.with(Serdes.String(), Serdes.Long()));

        KafkaStreams streams = new KafkaStreams(builder.build(), props);
        streams.start();
    }
}
```

What happens: lines are split into words (`flatMapValues`), re-keyed by word (`groupBy`, which repartitions), counted into a queryable store `counts-store` (`count`), and the running counts are written to `WordsWithCountsTopic` with `String`/`Long` Serdes. A Scala version exists using `org.apache.kafka.streams.scala` (deprecated library; see [Serdes and Scala migration](serdes-and-datatypes.md)).

## Quickstart: run the WordCountDemo

The demo (`org.apache.kafka.streams.examples.wordcount.WordCountDemo`, shipped with Kafka) does:

```java
final Serde<String> stringSerde = Serdes.String();
final Serde<Long> longSerde = Serdes.Long();

KStream<String, String> textLines = builder.stream(
      "streams-plaintext-input",
      Consumed.with(stringSerde, stringSerde)
    );

KTable<String, Long> wordCounts = textLines
    // Split each text line, by whitespace, into words.
    .flatMapValues(value -> Arrays.asList(value.toLowerCase().split("\\W+")))
    // Group the text words as message keys
    .groupBy((key, value) -> value)
    // Count the occurrences of each word (message key).
    .count();

// Store the running counts as a changelog stream to the output topic.
wordCounts.toStream().to("streams-wordcount-output", Produced.with(Serdes.String(), Serdes.Long()));
```

Unlike batch WordCounts over bounded data, it runs **forever on unbounded input**, continuously emitting updated counts.

### Step 1–2: get and start Kafka

```bash
$ tar -xzf kafka_2.13-4.3.0.tgz
$ cd kafka_2.13-4.3.0

$ KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
$ bin/kafka-storage.sh format --standalone -t $KAFKA_CLUSTER_ID -c config/server.properties
$ bin/kafka-server-start.sh config/server.properties
```

(Details: [Run Kafka locally](../getting-started/local-quickstart.md).)

### Step 3: create topics

```bash
$ bin/kafka-topics.sh --create \
    --bootstrap-server localhost:9092 \
    --replication-factor 1 \
    --partitions 1 \
    --topic streams-plaintext-input

$ bin/kafka-topics.sh --create \
    --bootstrap-server localhost:9092 \
    --replication-factor 1 \
    --partitions 1 \
    --topic streams-wordcount-output \
    --config cleanup.policy=compact

$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --exclude-internal
```

The output topic is **compacted** because it is a changelog stream (latest count per word is what matters).

### Step 4: start the application

```bash
$ bin/kafka-run-class.sh org.apache.kafka.streams.examples.wordcount.WordCountDemo
```

It produces no STDOUT output beyond logs; results go to `streams-wordcount-output`. Optionally try the **KIP-1071 streams rebalance protocol**, which moves task assignment to the broker, shortening rebalances and eliminating stop-the-world rebalances:

```bash
$ echo "group.protocol=streams" > streams.properties
$ bin/kafka-run-class.sh org.apache.kafka.streams.examples.wordcount.WordCountDemo streams.properties
```

### Step 5: process some data

Producer terminal:

```bash
$ bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic streams-plaintext-input
>all streams lead to kafka
>hello kafka streams
>join kafka summit
```

Consumer terminal (keys are `String`, values `Long`):

```bash
$ bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
    --topic streams-wordcount-output \
    --from-beginning \
    --formatter-property print.key=true \
    --formatter-property print.value=true \
    --formatter-property key.deserializer=org.apache.kafka.common.serialization.StringDeserializer \
    --formatter-property value.deserializer=org.apache.kafka.common.serialization.LongDeserializer

all	    1
streams	1
lead	1
to	    1
kafka	1
hello	1
kafka	2
streams	2
join	1
kafka	3
summit	1
```

### Why the output looks like this

The output is a **continuous stream of updates**: each line is the latest count for one word, and later records for the same key supersede earlier ones. Internally, the `KTable<String, Long>` from `count()` evolves as lines arrive (new words insert entries; "kafka" and "streams" get updated by the second line), and each table change is sent downstream as a change record. This is the **table–changelog duality**: publishing every table change gives a stream; consuming that stream from the beginning reconstructs the table. (Record caching may batch some intermediate updates — see [memory management](state-stores-and-interactive-queries.md#memory-management).)

### Step 6: teardown

Stop the console consumer, producer, WordCount app and broker, in that order, with `Ctrl-C`.

## Next steps

- [Write your own application (tutorial)](writing-an-application.md)
- [Streams DSL](dsl-api.md)
- [Configuration](configuration.md)
- [Testing](testing.md)
