---
type: reference
title: Wire Protocol and Implementation Internals
description: The internals users and client implementers need — Kafka's binary request/response protocol over TCP, ordering and pipelining per connection, bootstrapping via metadata requests and leader routing, partitioning strategies, batching, bidirectional compatibility through API versioning and ApiVersionsRequest, tagged fields and flexible versions, the SASL handshake sequence, message framing, error codes and API keys, the broker's NIO network layer, the record/control-record formats and group member ID recommendations.
tags: [protocol, internals, api-versions, network, record-format, client-implementation]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-a354b88ce97205a60e728b7d
    resource: repo://docs/design/protocol.md
  - id: openwiki-source-ce6664c421a6343b18916cf8
    resource: repo://docs/implementation/message-format.md
  - id: openwiki-source-c235830ea48ba17e39de0b29
    resource: repo://docs/implementation/network-layer.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Wire Protocol and Implementation Internals

This page summarizes the parts of Kafka's protocol and implementation that matter to users debugging clients and to authors of non-Java clients. Exact per-API schemas, error codes and API keys are generated (`protocol_messages.html`, `protocol_errors.html`, `protocol_api_keys.html`, `protocol_types.html`).

## Network basics

- **Binary protocol over TCP.** Every API is a **request/response pair**; all messages are **size-delimited**.
- No handshake on connect/disconnect. Keep **persistent connections** to amortize TCP setup.
- Clients connect to **multiple brokers** (data is partitioned) but generally need **one connection per broker** — no pooling.
- **Ordering:** on a single connection, the broker processes requests in send order and returns responses in the same order; it allows **one in-flight request per connection** to guarantee this. Clients can still **pipeline** with non-blocking I/O — further requests wait in the socket buffer.
- Requests above the broker's maximum size (`socket.request.max.bytes`, default 100 MiB) cause the **socket to be disconnected**.

Framing:

```text
RequestOrResponse => Size (RequestMessage | ResponseMessage)
  Size => int32

Message => RequestOrResponseHeader Body
```

Read the 4-byte size N, then parse the next N bytes. Header versions depend on the API version.

## Bootstrapping and routing

Topics have P partitions (`0 … P-1`), each replicated N times. **Clients decide the partition** for each record; brokers impose no partitioning semantics, so clients sharing a scheme must hash keys identically.

Produce and fetch requests **must go to the partition leader** — otherwise the broker returns `NotLeaderForPartition`. Any broker answers a **metadata request** describing topics, partitions, leaders and broker addresses. Client algorithm:

1. Cycle through the bootstrap URLs (configure **two or three**, or a load balancer) until one connects; fetch metadata.
2. Send produce/fetch requests to the right leaders.
3. On a socket error or a "not leader / not hosted here" error, refresh metadata and retry.

Clients don't need to poll for changes — cache metadata until an error says it's stale (Java clients additionally refresh every `metadata.max.age.ms`).

## Partitioning strategies

Partitioning serves two purposes: **load balancing** across brokers, and **semantic partitioning** — routing by key (e.g. user id) so one consumer sees all of a key's data with local state and order. Simple load balancing can round-robin, or (with many more producers than brokers) have each producer pick one random partition to reduce TCP connections. See the Java [Producer](../clients/producer.md#choosing-a-partition) defaults.

## Batching

Send and fetch APIs always operate on **sequences of messages**, and a single produce or fetch request can span **many topics and partitions**. Batching is a major performance win; clients can implement an asynchronous mode that groups individually sent records.

## Compatibility and API versioning

Kafka has a **bidirectional** compatibility policy: new clients work with old brokers and old clients with new brokers, so either side can be upgraded without downtime.

- Every request starts with an **API key** and **API version** (two 16-bit numbers) identifying its schema.
- Clients support a range of versions and should use the **highest version supported by both** sides. Brokers reject unsupported versions and always respond in the format of the request's version (exception: `ApiVersions` itself).
- New features roll out on brokers first; newer clients adopt them gradually.
- **Tagged fields** (KIP-482) can be added without bumping the version; they cost nothing when unset but are ignored by recipients that don't know them.
- **Flexible versions** use compact encodings (`COMPACT_ARRAY`, `COMPACT_STRING`, … with unsigned varint lengths) and end each request/response component with a tagged-fields section.

### Discovering supported versions (KIP-35, since 0.10.0.0)

1. After connecting (after the TLS handshake if SSL is used), the client sends `ApiVersionsRequest`.
2. The broker returns all supported API keys and versions **regardless of authentication state** (e.g. before SASL authentication). If that is considered an information leak, use SSL client authentication, which happens before `ApiVersionsRequest` is possible. Brokers older than 0.10.0.0 ignore the request or close the connection.
3. If the client's `ApiVersionsRequest` version is too new and the broker is ≥ 2.4.0, the broker answers with a **v0** response carrying `UNSUPPORTED_VERSION` and its supported `ApiVersionsRequest` versions; the client retries with the highest common version (KIP-511).
4. Use the latest version supported by both. Deprecated versions are marked in the protocol docs.
5. Version information is **valid only for that connection** — re-query after reconnecting, since the broker may have been upgraded or downgraded.

Version-level compatibility between releases (e.g. pre-0.10 protocols removed in 4.0, KIP-896) is summarized in [Compatibility](../getting-started/compatibility.md).

## SASL authentication sequence

1. (Optional) `ApiVersionsRequest`.
2. `SaslHandshakeRequest` with the mechanism. If it isn't enabled, the broker returns the supported mechanisms and **closes the connection**.
3. SASL exchange: with `SaslHandshakeRequest` v0, raw SASL tokens are sent as opaque packets without Kafka headers; with v1, tokens are wrapped in `SaslAuthenticate` requests/responses. The final broker message's error code indicates success.
4. On success, subsequent packets are normal Kafka requests; on failure the connection is closed.

For 0.9.0.x interoperability, if the first packet isn't a valid Kafka request it is treated as a SASL/GSSAPI token, skipping steps 1–2. Configuration: [SASL authentication](../security/sasl-authentication.md).

## Error codes and API keys

Brokers report problems with **numeric error codes** that clients map to exceptions (e.g. `NOT_LEADER_OR_FOLLOWER`, `UNSUPPORTED_VERSION`, `COORDINATOR_LOAD_IN_PROGRESS`), and each request type has a stable numeric **ApiKey** (Produce, Fetch, Metadata, OffsetCommit, ApiVersions, SaslHandshake, ConsumerGroupHeartbeat, …). See the generated tables for the full lists.

## Why a custom TCP protocol?

- HTTP would forgo advanced TCP features — multiplexing requests and polling many connections at once — and HTTP libraries were found lacking in many languages.
- Supporting multiple protocols makes adding and testing features much harder.
- Existing messaging protocols (XMPP, STOMP, AMQP) would dictate much of the implementation.
- Protocol Buffers/Thrift were not used: Kafka has few messages, language support was spotty, the mapping between log format and wire format must be controlled carefully, and explicit API versioning gives finer compatibility control.

## Broker network layer

A straightforward NIO server: **one acceptor thread** and **N processor threads**, each handling a fixed set of connections (`num.network.threads`; requests are then executed by `num.io.threads` request handler threads). Zero-copy `sendfile` is used by giving the `TransferableRecords` interface a `writeTo` method, letting file-backed records use `transferTo` instead of buffered writes (not with TLS — see [Storage](../concepts/storage-and-retention.md#efficiency-batching-and-zero-copy)). The protocol is deliberately simple so clients can be written in other languages.

## Messages and record batches

A message (record) consists of a variable-length header plus **opaque key and value byte arrays** — Kafka deliberately doesn't mandate a serialization format; applications choose one (see Serdes in [Kafka Streams](../streams/serdes-and-datatypes.md)). The `RecordBatch` interface is an iterator over messages with bulk read/write methods for NIO channels.

Records are always written in **record batches** (current magic value 2). Key facts (full layout in [Storage and retention](../concepts/storage-and-retention.md#record-batch-format-essentials)):

- Batch header: `baseOffset`, `batchLength`, `partitionLeaderEpoch`, `magic`, `crc`, `attributes`, `lastOffsetDelta`, `baseTimestamp`, `maxTimestamp`, `producerId`, `producerEpoch`, `baseSequence`, `recordsCount`, `records`.
- CRC-32C covers attributes→end; `partitionLeaderEpoch` is excluded so brokers can set it without recomputing.
- On compaction, first/last offsets and sequence numbers are preserved (so idempotent producer state survives and duplicates are still detected); empty batches may remain; `baseTimestamp` may change, and is set to the delete horizon for tombstones/aborted markers.
- **Control batches** contain a single **control record** never returned to applications. Key schema `version: int16, type: int16`. Types: **0 = ABORT**, **1 = COMMIT** (transaction markers); 2–6 are used internally by KRaft. Consumers use them to filter aborted transactional data.
- Pre-0.11 "message sets" (old format) are documented in older releases.

## Consumer offset tracking

Consumers commit offsets to their group's **coordinator** broker (found with `FindCoordinatorRequest`), which appends them to the compacted `__consumer_offsets` topic, acknowledges after all replicas have them, caches them in memory, and may answer fetches with `CoordinatorLoadInProgressException` while loading. Details: [Consumer](../clients/consumer.md#offsets-and-the-group-coordinator).

## Recommendation for third-party clients: member IDs

Clients participating in group protocols (e.g. `ConsumerGroupHeartbeat`) generate a **member ID**. The protocol doesn't enforce a format, but it is strongly recommended to:

1. use a **base64-encoded UUID**,
2. encoded with **URL-safe base64** (no `+` or `/`),
3. with **no hyphens** — a continuous alphanumeric string.

Non-conforming IDs are not rejected.

## Related pages

- [Compatibility](../getting-started/compatibility.md)
- [Storage, log segments and retention](../concepts/storage-and-retention.md)
- [Kafka APIs overview](../clients/apis-overview.md)
