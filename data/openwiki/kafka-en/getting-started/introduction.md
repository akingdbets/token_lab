---
type: overview
title: Introduction to Apache Kafka
description: What event streaming is, Kafka's three core capabilities (publish/subscribe, store, process), how servers (brokers, Connect) and clients fit together, the main concepts (events, producers, consumers, topics, partitions, replication), the Kafka APIs, typical use cases and the wider ecosystem.
tags: [introduction, overview, event-streaming, concepts, use-cases]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-10fb47514fcebac6f3a0c535
    resource: repo://docs/getting-started/ecosystem.md
  - id: openwiki-source-382bc16e26147a97f6cd7008
    resource: repo://docs/getting-started/introduction.md
  - id: openwiki-source-4784af0ff4cbc3399d673560
    resource: repo://docs/getting-started/uses.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Introduction to Apache Kafka

## Event streaming

Event streaming is the practice of **capturing data in real time** from event sources (databases, sensors, mobile devices, cloud services, applications) as streams of events; **storing** those streams durably for later retrieval; **processing and reacting** to them in real time and retrospectively; and **routing** them to other technologies as needed. It keeps data flowing so the right information is at the right place at the right time.

Examples: real-time payments and financial transactions; tracking fleets and shipments; IoT sensor analytics in factories and wind parks; reacting to customer interactions and orders; patient monitoring in hospitals; connecting data across company divisions; and serving as the foundation for data platforms, event-driven architectures and microservices.

## Kafka is an event streaming platform

Kafka combines three capabilities in one battle-tested system:

1. **Publish** (write) and **subscribe to** (read) streams of events, including continuous import/export from other systems.
2. **Store** streams of events durably and reliably for as long as you want.
3. **Process** streams of events as they occur or retrospectively.

It is distributed, highly scalable, elastic, fault-tolerant and secure, and runs on bare metal, VMs or containers, on-premises or in the cloud — self-managed or as a managed service.

## How it works in a nutshell

Kafka is a distributed system of **servers** and **clients** communicating over a high-performance TCP [protocol](../reference/protocol-and-internals.md).

- **Servers** run as a cluster that can span datacenters or cloud regions. Some form the storage layer — the **brokers**. In KRaft mode, **controllers** manage cluster metadata ([KRaft setup](../operations/kraft-cluster-setup.md)). Others run **Kafka Connect** to import/export data with external systems such as relational databases or other Kafka clusters. If a server fails, others take over without data loss.
- **Clients** let you build distributed applications and microservices that read, write and process event streams in parallel, at scale and fault-tolerantly. Kafka ships Java/Scala clients including the **Kafka Streams** library; the community provides clients for Go, Python, C/C++, REST and more.

## Main concepts

| Concept | Summary |
| --- | --- |
| **Event** (record, message) | "Something happened": key, value, timestamp, optional headers. E.g. key `"Alice"`, value `"Made a payment of $200 to Bob"`. |
| **Producer** | Client that publishes events. |
| **Consumer** | Client that subscribes to and processes events. Producers and consumers are fully decoupled — producers never wait for consumers. |
| **Topic** | Durable, multi-producer, multi-subscriber stream of events (like a folder of files), e.g. `payments`. Events are kept per a retention setting, not deleted after consumption. |
| **Partition** | A topic is split into partitions on different brokers. Same-key events go to the same partition; each partition is read in write order. |
| **Replication** | Each partition is copied to several brokers (commonly replication factor 3), even across regions. |

Details: [Topics, partitions and offsets](../concepts/topics-partitions-offsets.md), [Replication](../concepts/replication.md), [Delivery semantics](../concepts/delivery-semantics.md).

## Kafka APIs

Besides command-line tools for administration, Kafka has these core APIs for Java and Scala:

- **Admin API** — manage and inspect topics, brokers and other objects ([Admin API](../clients/admin-api.md)).
- **Producer API** — publish streams of events to topics ([Producer](../clients/producer.md)).
- **Consumer API** — subscribe to topics and process their events ([Consumer](../clients/consumer.md)); plus the **Share Consumer API** for queue-like share groups ([Share groups](../clients/share-groups.md)).
- **Kafka Streams API** — stream processing apps with transformations, stateful aggregations and joins, windowing and event-time processing ([Kafka Streams](../streams/introduction-and-quickstart.md)).
- **Kafka Connect API** — reusable import/export connectors; usually you use one of the hundreds of existing connectors ([Kafka Connect](../connect/overview-and-running.md)).

See [Kafka APIs overview](../clients/apis-overview.md) for Maven coordinates.

## Common use cases

| Use case | Why Kafka fits |
| --- | --- |
| **Messaging** | Replacement for traditional brokers (comparable to ActiveMQ or RabbitMQ) with better throughput, built-in partitioning, replication and fault tolerance; often low throughput but needing low latency and strong durability. |
| **Website activity tracking** | Kafka's original use case: page views, searches and other actions published to one topic per activity type, consumed for real-time processing, monitoring and offline loading. Very high volume. |
| **Metrics** | Aggregating operational statistics from distributed applications into centralized feeds. |
| **Log aggregation** | Replaces collecting log files into a central place; treats logs as streams of messages with lower latency, multiple sources and distributed consumption; stronger durability than Scribe or Flume via replication. |
| **Stream processing** | Multi-stage pipelines that consume, aggregate, enrich or transform topics into new topics (e.g. crawling articles → normalizing → recommending), often with Kafka Streams. |
| **Event sourcing** | State changes logged as a time-ordered sequence of records; Kafka stores very large logs. |
| **Commit log** | External commit log for distributed systems: replicating data between nodes and re-syncing failed nodes, aided by [log compaction](../concepts/log-compaction.md) (similar to Apache BookKeeper). |

## Ecosystem

Many tools integrate with Kafka outside the main distribution — stream processing systems, Hadoop integration, monitoring and deployment tools — listed on the Kafka ecosystem wiki page (https://cwiki.apache.org/confluence/x/Ri3VAQ).

## Where to go next

- Hands-on: [Quickstart](local-quickstart.md) or [Docker](docker.md).
- Concepts: [Topics, partitions and offsets](../concepts/topics-partitions-offsets.md).
- Full map of this wiki: [Wiki quickstart](../quickstart.md).
