---
type: tutorial
title: "Quickstart: Run Kafka Locally"
description: Step-by-step quickstart for a single-node KRaft Kafka — download and extract, generate a cluster ID and format storage with kafka-storage.sh, start the server, create and describe a topic, produce and consume with the console tools, move data with Connect file connectors, a first Kafka Streams WordCount, and teardown.
tags: [quickstart, tutorial, getting-started, kraft, console-tools, connect, streams]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-879c710378f4939b0b8f9110
    resource: repo://docs/getting-started/quickstart.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Quickstart: Run Kafka Locally

This walks through the official quickstart: one combined broker+controller node on `localhost` using `config/server.properties`. **Java 17+ is required.**

## Step 1: Get Kafka

Download the release (`kafka_2.13-4.3.0.tgz` in the docs) and extract it:

```bash
$ tar -xzf kafka_2.13-4.3.0.tgz
$ cd kafka_2.13-4.3.0
```

## Step 2: Start the Kafka environment

### Option A: downloaded files

```bash
# generate a cluster UUID
$ KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"

# format the log directories (single standalone controller)
$ bin/kafka-storage.sh format --standalone -t $KAFKA_CLUSTER_ID -c config/server.properties

# start the server
$ bin/kafka-server-start.sh config/server.properties
```

`config/server.properties` defines a node with `process.roles=broker,controller`, `node.id=1`, client listener `PLAINTEXT://:9092`, controller listener `CONTROLLER://:9093`, `controller.quorum.bootstrap.servers=localhost:9093` and `log.dirs=/tmp/kraft-combined-logs` (see [Broker configuration](../configuration/broker-configuration.md#sample-properties-files)). `--standalone` formats a single-controller dynamic quorum; multi-controller setups are covered in [KRaft cluster setup](../operations/kraft-cluster-setup.md).

### Option B: Docker

```bash
$ docker pull apache/kafka:4.3.0
$ docker run -p 9092:9092 apache/kafka:4.3.0

# or the experimental GraalVM native image
$ docker pull apache/kafka-native:4.3.0
$ docker run -p 9092:9092 apache/kafka-native:4.3.0
```

See [Running Kafka with Docker](docker.md).

## Step 3: Create a topic

Events are organized in topics. In another terminal:

```bash
$ bin/kafka-topics.sh --create --topic quickstart-events --bootstrap-server localhost:9092

$ bin/kafka-topics.sh --describe --topic quickstart-events --bootstrap-server localhost:9092
Topic: quickstart-events        TopicId: NPmZHyhbR9y00wMglMH2sg PartitionCount: 1       ReplicationFactor: 1	Configs:
Topic: quickstart-events Partition: 0    Leader: 0   Replicas: 0 Isr: 0
```

Every CLI tool prints its options when run without arguments.

## Step 4: Write events

Each line you type becomes one event:

```bash
$ bin/kafka-console-producer.sh --topic quickstart-events --bootstrap-server localhost:9092
>This is my first event
>This is my second event
```

Stop with `Ctrl-C`.

## Step 5: Read events

```bash
$ bin/kafka-console-consumer.sh --topic quickstart-events --from-beginning --bootstrap-server localhost:9092
This is my first event
This is my second event
```

Events are stored durably, so they can be read as many times and by as many consumers as you like — rerun the command in another terminal to see it.

## Step 6: Import/export data with Kafka Connect

Add the file connectors to the worker's plugin path (relative paths are fine for the quickstart; use absolute paths in production):

```bash
$ echo "plugin.path=libs/connect-file-4.3.0.jar" >> config/connect-standalone.properties
$ echo -e "foo\nbar" > test.txt
```

On Windows:

```bash
$ echo foo > test.txt
$ echo bar >> test.txt
```

Start a standalone worker with a file source and a file sink connector:

```bash
$ bin/connect-standalone.sh config/connect-standalone.properties config/connect-file-source.properties config/connect-file-sink.properties
```

The source reads `test.txt` into topic `connect-test`; the sink writes that topic to `test.sink.txt`:

```bash
$ more test.sink.txt
foo
bar

$ bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic connect-test --from-beginning
{"schema":{"type":"string","optional":false},"payload":"foo"}
{"schema":{"type":"string","optional":false},"payload":"bar"}

$ echo "Another line" >> test.txt   # flows through the pipeline
```

The JSON envelope comes from `JsonConverter` with `schemas.enable=true` in `connect-standalone.properties`. More: [Kafka Connect](../connect/overview-and-running.md).

## Step 7: Process events with Kafka Streams

Kafka Streams is a Java/Scala client library for real-time apps whose input and output live in Kafka; it supports exactly-once, stateful operations, windowing, joins and event-time processing. WordCount:

```java
KStream<String, String> textLines = builder.stream("quickstart-events");

KTable<String, Long> wordCounts = textLines
            .flatMapValues(line -> Arrays.asList(line.toLowerCase().split(" ")))
            .groupBy((keyIgnored, word) -> word)
            .count();

wordCounts.toStream().to("output-topic", Produced.with(Serdes.String(), Serdes.Long()));
```

Run the full demo in [Streams introduction and quickstart](../streams/introduction-and-quickstart.md) or build it step by step in [Writing a Streams application](../streams/writing-an-application.md).

## Step 8: Tear down

1. Stop producer and consumer clients with `Ctrl-C`.
2. Stop the Kafka broker with `Ctrl-C`.
3. Optionally delete all local data:

```bash
$ rm -rf /tmp/kafka-logs /tmp/kraft-combined-logs
```

## Troubleshooting tips

- **Formatting is required** before the first start; a node with unformatted `log.dirs` will not start. Reformatting erases data.
- Clients must reach the address in `advertised.listeners` (`localhost:9092` here); change it when connecting from another host or container.
- Single-node internal topics use replication factor 1 (`offsets.topic.replication.factor=1`, `transaction.state.log.replication.factor=1`, …) — keep these defaults at 3 in real clusters.

## Next steps

- [Introduction](introduction.md) and [core concepts](../concepts/topics-partitions-offsets.md)
- [Java client examples](../clients/examples.md)
- [Basic operations](../operations/topic-and-cluster-administration.md)
