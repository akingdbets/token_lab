---
type: getting-started
title: Running Kafka with Docker
description: How to run Apache Kafka from the official Docker images — the JVM-based apache/kafka image (since 3.7.0) and the experimental GraalVM native apache/kafka-native image (since 3.8.0) — with pull and run commands, when to use each, and how they fit the quickstart.
tags: [docker, getting-started, containers, graalvm]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-d4df7ecf4a0733d9a281c377
    resource: repo://docs/getting-started/docker.md
  - id: openwiki-source-879c710378f4939b0b8f9110
    resource: repo://docs/getting-started/quickstart.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Running Kafka with Docker

Kafka publishes two official images on Docker Hub. Both start a single-node KRaft Kafka with default configs, listening on port **9092**, so they can replace the "download and format" steps of the [local quickstart](local-quickstart.md).

| Image | Available since | Intended use |
| --- | --- | --- |
| `apache/kafka` — JVM based | 3.7.0 | General use. |
| `apache/kafka-native` — GraalVM native | 3.8.0 | **Experimental**: local development and testing only, **not recommended for production**. |

## JVM-based image

```bash
# a specific version
$ docker pull apache/kafka:4.3.0

# or the latest version
$ docker pull apache/kafka:latest

# start with default configs on port 9092
$ docker run -p 9092:9092 apache/kafka:4.3.0
```

## GraalVM native image

The native image starts faster and uses less memory, which makes it attractive for tests and laptops, but it is experimental.

```bash
$ docker pull apache/kafka-native:4.3.0
$ docker pull apache/kafka-native:latest
$ docker run -p 9092:9092 apache/kafka-native:4.3.0
```

## Using the container

Once the container is running, clients on the host connect to `localhost:9092` exactly as in the quickstart. With a Kafka distribution unpacked locally you can use its tools against the container:

```bash
$ bin/kafka-topics.sh --create --topic quickstart-events --bootstrap-server localhost:9092
$ bin/kafka-console-producer.sh --topic quickstart-events --bootstrap-server localhost:9092
$ bin/kafka-console-consumer.sh --topic quickstart-events --from-beginning --bootstrap-server localhost:9092
```

Remember that the default container config is a single node: internal topics such as `__consumer_offsets` and `__transaction_state` need replication factor 1, as in `config/server.properties` (see [Broker configuration](../configuration/broker-configuration.md)).

## Configuration and advanced usage

Detailed instructions for configuring the images — overriding broker properties, mounting config files, multi-node and SSL setups — are in the Docker usage guide in the Kafka repository: `docker/examples/README.md` (https://github.com/apache/kafka/blob/trunk/docker/examples/README.md).

For production clusters, apply the same guidance as for any deployment: [KRaft cluster setup](../operations/kraft-cluster-setup.md), [hardware and OS](../operations/hardware-os-and-deployment.md) and [security](../security/listeners-and-security-overview.md).

## Related pages

- [Quickstart: run Kafka locally](local-quickstart.md)
- [Compatibility and Java versions](compatibility.md)
