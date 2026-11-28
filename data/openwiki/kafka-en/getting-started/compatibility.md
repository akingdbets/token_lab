---
type: reference
title: Compatibility and Java Versions
description: Which Java versions each Kafka module supports, which older KRaft clusters can be upgraded to 4.x (static vs dynamic voters), how old clients, Streams and Connect interoperate with Kafka 4.0 brokers (KIP-896), and the recommended JVM version and GC settings for running Kafka.
tags: [compatibility, java, jvm, upgrade, clients, kraft]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-d252b2d07f854a00c1b71332
    resource: repo://docs/getting-started/compatibility.md
  - id: openwiki-source-cef1cda090344b736073fcc6
    resource: repo://docs/operations/java-version.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Compatibility and Java Versions

Kafka 4.0 introduced significant compatibility changes. This page collects the documented compatibility matrices plus JVM recommendations. See also [ZooKeeper to KRaft differences](../operations/zookeeper-to-kraft-migration.md) and the [README](../quickstart.md) build notes.

## JDK compatibility by module (Kafka 4.0.0 matrix)

| Module | Java 11 | Java 17 | Java 23 |
| --- | --- | --- | --- |
| Clients | ✅ | ✅ | ✅ |
| Streams | ✅ | ✅ | ✅ |
| Connect | ❌ | ✅ | ✅ |
| Server (brokers/controllers) | ❌ | ✅ | ✅ |

**Java 8 was removed in Kafka 4.0 and is no longer supported.**

Current guidance (operations docs): **Java 17, 21 and 25 are fully supported**; **Java 11** is supported only for a subset of modules (clients, streams and related). Versions newer than the latest LTS are best-effort; the project typically tests only the most recent non-LTS release. The build itself targets `release 11` for clients and streams and `release 17` for everything else, and is tested with Java 17 and 25. Scala 2.13 is the only supported Scala version.

## Server (KRaft) upgrade compatibility

Which existing KRaft cluster versions can be upgraded to a 4.0 server:

| KRaft cluster version | 4.0 server, dynamic voter | 4.0 server, static voter |
| --- | --- | --- |
| before 3.2.x | ❌ | ❌ |
| 3.3.x – 3.8.x | ❌ | ✅ |
| 3.9.x | ✅ | ✅ |
| 4.0.x | ✅ | ✅ |

<!-- openwiki: broken internal link [../operations/kraft-cluster-setup.md#static-versus-dynamic-kraft-quorums] heading anchor "static-versus-dynamic-kraft-quorums" does not exist in "../operations/kraft-cluster-setup.md". Fix the href or restore the target, then delete this comment. -->
**You can't upgrade a server from a static voter set to a dynamic voter set** (KAFKA-16538). Static vs dynamic quorums are explained in [KRaft cluster setup](../operations/kraft-cluster-setup.md#static-versus-dynamic-kraft-quorums).

## Client/broker forward compatibility with Kafka 4.0

| Client version | Module | Compatibility with 4.0 brokers | Notes |
| --- | --- | --- | --- |
| 0.x, 1.x, 2.0 | Client, Streams, Connect | ❌ Not compatible | Pre-0.10.x protocols are fully removed in 4.0 (KIP-896). |
| 2.1 – 2.8 | Client | ⚠️ Partially compatible | See the 4.0 upgrade notes for Consumer, Producer and Admin Client. |
| 2.1 – 2.8 | Streams, Connect | ⚠️ Limited compatibility | See the 4.0 upgrade notes for Streams and Connect. |
| 3.x | Client, Streams, Connect | ✅ Fully compatible | — |

Since Kafka 4.0 the `--zookeeper` option has been removed from admin commands; use `--bootstrap-server` (or `--bootstrap-controller` for controllers).

Protocol-level versioning (how clients and brokers negotiate API versions with `ApiVersionsRequest`) is described in [Wire protocol and internals](../reference/protocol-and-internals.md).

## Running Kafka on the JVM

Recommendations:

- Run the **most recent LTS** Java release (Java 25 at the time of writing) for performance, efficiency and support.
- Use the **latest patch version** — older ones typically have disclosed security vulnerabilities.

Typical arguments for OpenJDK-based JVMs (including Oracle JDK):

```bash
-Xmx6g -Xms6g -XX:MetaspaceSize=96m -XX:+UseG1GC
-XX:MaxGCPauseMillis=20 -XX:InitiatingHeapOccupancyPercent=35 -XX:G1HeapRegionSize=16M
-XX:MinMetaspaceFreeRatio=50 -XX:MaxMetaspaceFreeRatio=80 -XX:+ExplicitGCInvokesConcurrent
```

The `bin/*.sh` launchers read the heap size from the `KAFKA_HEAP_OPTS` environment variable (the example scripts default it to `-Xmx512M` when unset):

```bash
export KAFKA_HEAP_OPTS="-Xmx6g -Xms6g"
bin/kafka-server-start.sh config/server.properties
```

Reference point: one of LinkedIn's busiest clusters at peak, using these arguments — 60 brokers, 50k partitions (replication factor 2), 800k messages/sec in, 300 MB/s inbound and 1 GB/s+ outbound — saw a **90th-percentile GC pause of about 21 ms with fewer than one young GC per second**.

Kafka keeps most data in the OS page cache rather than the heap, so a moderate heap (6 GB here) leaves memory for caching (see [Storage](../concepts/storage-and-retention.md) and [Hardware and OS](../operations/hardware-os-and-deployment.md)).

## Related pages

- [ZooKeeper to KRaft migration and differences](../operations/zookeeper-to-kraft-migration.md)
- [KRaft cluster setup](../operations/kraft-cluster-setup.md)
- [Hardware, OS and deployment](../operations/hardware-os-and-deployment.md)
