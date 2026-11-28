---
type: index
title: Kafka Wiki Quickstart
description: Entry point to this Apache Kafka user wiki (built from the Kafka 4.x documentation, configs and examples) — what it covers, how it is organized, and a task-routing map telling developers and operators which page to read for common goals such as running Kafka, producing/consuming, exactly-once, KRaft operations, security, monitoring, Connect and Streams.
tags: [index, quickstart, navigation, kafka]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-f35361e71a8e17b4f31c5501
    resource: repo://docs/_index.md
  - id: openwiki-source-65441b210b7270ea8aed2740
    resource: repo://docs/streams/developer-guide/topology-description-plugin.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Kafka Wiki Quickstart

This wiki explains **Apache Kafka for users** — developers writing clients, Connect and Streams applications, and operators running clusters — from beginners to advanced. It is derived from the Kafka documentation in this repository (`docs/`, the generated config tables in `docs/generated/`), the sample configs in `config/` and the Java examples in `examples/`. Pages favor usage over internals and keep exact config names, defaults and version notes.

**Version note:** the source docs are for the Kafka **4.x** line (the docs index is titled "AK 4.3.X", snippets use `4.3.0`/`4.3.1` artifacts and tarballs, and some sections describe **4.4** features such as the streams-group topology description plugin). Kafka 4.x runs **only in KRaft mode** (no ZooKeeper) and requires Java 17+ for brokers.

## Start here

1. [Introduction to Kafka](getting-started/introduction.md) — event streaming, core concepts, APIs, use cases.
2. [Quickstart: run Kafka locally](getting-started/local-quickstart.md) — or [with Docker](getting-started/docker.md).
3. [Topics, partitions, offsets and records](concepts/topics-partitions-offsets.md).
4. Pick your path below.

## Task routing map

### I want to…

| Goal | Read |
| --- | --- |
| Run a single-node Kafka on my laptop | [Local quickstart](getting-started/local-quickstart.md), [Docker](getting-started/docker.md) |
| Check Java / client compatibility before upgrading | [Compatibility and Java versions](getting-started/compatibility.md) |
| Write a producer | [Producer](clients/producer.md), [client configs](configuration/client-configuration.md) |
| Write a consumer / understand offsets and commits | [Consumer](clients/consumer.md) |
| Scale consumers, understand rebalancing, use KIP-848 (`group.protocol=consumer`) | [Consumer groups and rebalance protocols](clients/consumer-groups-and-rebalance.md) |
| Use queue-like consumption with acknowledgements and DLQs | [Share groups](clients/share-groups.md) |
| Manage topics/configs/ACLs from code | [Admin API](clients/admin-api.md) |
| See runnable Java examples | [Java client examples](clients/examples.md) |
| Pick Maven artifacts / check for internal API usage | [Kafka APIs overview](clients/apis-overview.md) |
| Avoid data loss or duplicates | [Delivery semantics](concepts/delivery-semantics.md), [Replication](concepts/replication.md) |
| Get exactly-once with producer + consumer | [Idempotence and transactions](concepts/idempotence-and-transactions.md) |
| Understand retention, segments and disk usage | [Storage and retention](concepts/storage-and-retention.md) |
| Keep only the latest value per key | [Log compaction](concepts/log-compaction.md) |
| Offload old data to S3/HDFS | [Tiered storage](operations/tiered-storage.md) |

### Operating a cluster

| Goal | Read |
| --- | --- |
| Set up KRaft controllers and brokers, format storage, add/remove controllers | [KRaft cluster setup](operations/kraft-cluster-setup.md) |
| Move from ZooKeeper mode / know what changed | [ZooKeeper to KRaft migration](operations/zookeeper-to-kraft-migration.md) |
| Configure brokers or change configs without restart | [Broker configuration](configuration/broker-configuration.md) |
| Set per-topic or per-group configs | [Topic and group configuration](configuration/topic-and-group-configuration.md) |
| Keep secrets out of config files | [Config providers and system properties](configuration/config-providers-and-system-properties.md) |
| Create/alter topics, reassign partitions, decommission brokers, throttle | [Basic operations](operations/topic-and-cluster-administration.md) |
| Check lag, reset offsets, manage consumer/share groups | [Managing groups](operations/managing-groups.md) |
| Limit noisy tenants, set quotas | [Quotas and multi-tenancy](operations/quotas-and-multi-tenancy.md) |
| Replicate between clusters / DR | [Geo-replication with MirrorMaker 2](operations/geo-replication-mirrormaker.md) |
| Size hardware, tune OS/filesystem/JVM | [Hardware, OS and deployment](operations/hardware-os-and-deployment.md) |
| Monitor brokers, controllers, coordinators | [Broker and KRaft metrics](monitoring/broker-and-kraft-metrics.md) |
| Monitor clients, Connect and Streams apps | [Client metrics](monitoring/client-metrics.md) |

### Securing Kafka

| Goal | Read |
| --- | --- |
| Understand listeners, protocols and the trust model | [Security overview and listeners](security/listeners-and-security-overview.md) |
| Enable TLS encryption / mTLS | [SSL/TLS](security/ssl-encryption-and-authentication.md) |
| Authenticate with Kerberos, PLAIN, SCRAM, OAuth or delegation tokens | [SASL](security/sasl-authentication.md) |
| Authorize with ACLs | [Authorization and ACLs](security/authorization-and-acls.md) |

### Kafka Connect

| Goal | Read |
| --- | --- |
| Run standalone/distributed workers, install plugins | [Connect overview and workers](connect/overview-and-running.md) |
| Transform or filter records in flight | [SMTs and predicates](connect/transformations-and-predicates.md) |
| Manage connectors via REST, handle errors/DLQ, exactly-once, ACLs | [REST API and operations](connect/rest-api-and-operations.md) |
| Write my own connector | [Connector development](connect/connector-development.md) |

### Kafka Streams

| Goal | Read |
| --- | --- |
| Try Streams in five minutes | [Introduction and quickstart](streams/introduction-and-quickstart.md) |
| Build my first app step by step | [Writing an application](streams/writing-an-application.md) |
| Understand time, tables vs streams, tasks and state | [Concepts and architecture](streams/core-concepts-and-architecture.md) |
| Use the DSL (map, filter, groupBy, aggregate) | [DSL](streams/dsl-api.md) |
| Join streams/tables, use windows, emit final results | [Joins and windowing](streams/dsl-joins-and-windowing.md) |
| Write custom processors and stores | [Processor API](streams/processor-api.md) |
| Choose Serdes, migrate off the Scala DSL | [Serdes and data types](streams/serdes-and-datatypes.md) |
| Query state, tune RocksDB and caches | [State stores, IQ and memory](streams/state-stores-and-interactive-queries.md) |
| Configure exactly-once, threads, standbys | [Streams configuration](streams/configuration.md) |
| Run, scale, reset, secure; use `group.protocol=streams` | [Running and rebalancing](streams/running-and-rebalancing.md) |
| Unit-test topologies | [Testing](streams/testing.md) |
| Keep state names stable across upgrades; topology descriptions | [Naming and topology description](streams/topology-naming-and-description.md) |

### Internals and protocol

| Goal | Read |
| --- | --- |
| Implement a client, understand API versioning, SASL handshake, record format | [Wire protocol and internals](reference/protocol-and-internals.md) |

## Wiki layout

| Section | Content |
| --- | --- |
| `getting-started/` | Introduction, local and Docker quickstarts, compatibility |
| `concepts/` | Data model, replication, delivery semantics, transactions, storage, compaction |
| `clients/` | Producer, consumer, groups, share groups, Admin, API overview, examples |
| `configuration/` | Broker, client, topic/group configs, config providers |
| `operations/` | KRaft, migration, basic ops, groups CLI, quotas, tiered storage, MirrorMaker, hardware |
| `monitoring/` | Broker/KRaft and client/Connect/Streams metrics |
| `security/` | Listeners and security model, SSL, SASL, ACLs |
| `connect/` | Running Connect, SMTs, REST/ops, connector development |
| `streams/` | Everything Kafka Streams |
| `reference/` | Protocol and implementation internals |

## Building Kafka from source

The repository README documents the Gradle build: `./gradlew jar` builds the JARs; Kafka is built and tested with **Java 17 and 25**, with `release` 11 for clients and streams and 17 for other modules; **Scala 2.13** is the only supported Scala version. For using Kafka, prefer the release tarball or Docker images described in the quickstarts.

## Related pages

- [Introduction](getting-started/introduction.md)
- [Local quickstart](getting-started/local-quickstart.md)
