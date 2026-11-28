---
type: api-guide
title: Naming Topologies and Topology Description Plugins
description: Why and how to name Kafka Streams DSL operators, state stores and repartition topics (Named, Consumed.as, Produced.as, Grouped, Joined, StreamJoined, Materialized) so topology descriptions are readable and upgrades don't break state, the ensure.explicit.internal.resource.naming guard, and the 4.4 streams-group topology description plugin (KIP-1331) — push/describe cycle, broker and client configs, implementing StreamsGroupTopologyDescriptionPlugin, reading descriptions via Admin or CLI, statuses, deletion, metrics and troubleshooting.
tags: [streams, topology, naming, upgrades, kip-1331, streams-groups, operations]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-5767bc019eaebec5bd027f8e
    resource: repo://docs/streams/developer-guide/dsl-topology-naming.md
  - id: openwiki-source-65441b210b7270ea8aed2740
    resource: repo://docs/streams/developer-guide/topology-description-plugin.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Naming Topologies and Topology Description Plugins

## Why name DSL operators

In the Processor API you name every processor and store yourself. In the DSL, one operator may compile into several processors, state stores (with changelog topics) and repartition topics — all with **generated names**. That has two costs:

1. **Readability** of `Topology#describe()`.
2. **Upgrade breakage:** generated names include a global sequence number, so adding or removing an operator **upstream** of a stateful operator renames its store, changelog and repartition topics.

### Readability

```java
KStream<String,String> stream = builder.stream("input");
stream.filter((k,v) -> !v.equals("invalid_txn"))
      .mapValues((v) -> v.substring(0,5))
      .to("output");
```

```text
Topologies:
   Sub-topology: 0
    Source: KSTREAM-SOURCE-0000000000 (topics: [input])
      --> KSTREAM-FILTER-0000000001
    Processor: KSTREAM-FILTER-0000000001 (stores: [])
      --> KSTREAM-MAPVALUES-0000000002
      <-- KSTREAM-SOURCE-0000000000
    Processor: KSTREAM-MAPVALUES-0000000002 (stores: [])
      --> KSTREAM-SINK-0000000003
      <-- KSTREAM-FILTER-0000000001
    Sink: KSTREAM-SINK-0000000003 (topic: output)
      <-- KSTREAM-MAPVALUES-0000000002
```

With names (overloads accepting `Named`, `Consumed.as`, `Produced.as`):

```java
KStream<String,String> stream =
    builder.stream("input", Consumed.as("Customer_transactions_input_topic"));
stream.filter((k,v) -> !v.equals("invalid_txn"), Named.as("filter_out_invalid_txns"))
      .mapValues((v) -> v.substring(0,5), Named.as("Map_values_to_first_6_characters"))
      .to("output", Produced.as("Mapped_transactions_output_topic"));
```

```text
    Source: Customer_transactions_input_topic (topics: [input])
      --> filter_out_invalid_txns
    Processor: filter_out_invalid_txns (stores: [])
      --> Map_values_to_first_6_characters
    ...
    Sink: Mapped_transactions_output_topic (topic: output)
```

### Upgrade safety

Generated names follow `KSTREAM|KTABLE-<OPERATOR>-<zero-padded number>`, the number being the operator's position in the topology.

```java
stream.groupByKey().count().toStream().to("output");
// Processor: KSTREAM-AGGREGATE-0000000002 (stores: [KSTREAM-AGGREGATE-STATE-STORE-0000000001])
```

Adding a `filter` before `count` shifts the numbers:

```java
stream.filter((k,v)-> v != null && v.length() >= 6)
      .groupByKey().count().toStream().to("output");
// Processor: KSTREAM-AGGREGATE-0000000003 (stores: [KSTREAM-AGGREGATE-STATE-STORE-0000000002])
```

The store and changelog names changed, so you **can't do a rolling redeploy**; the old state is orphaned and you'd need the [reset tool](running-and-rebalancing.md#resetting-an-application) to recompute it. Naming the store avoids this:

```java
stream.filter((k, v) -> v != null && v.length() >= 6)
      .groupByKey()
      .count(Materialized.as("Purchase_count_store"))
      .toStream()
      .to("output");
// Processor: KSTREAM-AGGREGATE-0000000002 (stores: [Purchase_count_store])
```

### What to name, and with what

| Operation | Naming class |
| --- | --- |
| Aggregation repartition topics | `Grouped` |
| KStream-KStream join repartition topics | `StreamJoined` |
| KStream-KTable join repartition topic | `Joined` |
| KStream-KStream join state stores | `StreamJoined` |
| State stores (aggregations, KTable-KTable joins) | `Materialized` |
| Stateless stream/table operations | `Named` |

```java
stream.groupBy((k, v) -> v.customerId(), Grouped.as("by-customer"))
      .count(Materialized.as("customer-counts"));
left.join(right, joiner, JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5)),
          StreamJoined.as("orders-payments-join"));
```

Recommendations:

1. **Existing unnamed topologies:** adding names is itself a breaking change — stop all instances, change the code, run the reset tool, restart.
2. **New topologies:** at least name the **persistent** parts — state stores (changelogs) and repartition topics.

Enforce it:

```java
Properties props = new Properties();
props.put(StreamsConfig.ENSURE_EXPLICIT_INTERNAL_RESOURCE_NAMING_CONFIG, true);   // ensure.explicit.internal.resource.naming (default false)
```

With this set, the app **refuses to start** if any internal topic, state store or changelog relies on a generated name.

## Topology description plugin (KIP-1331, Kafka 4.4+)

Brokers can record a **human-readable topology description** for each **streams group** — the same information as `Topology#describe()` — in a pluggable broker-side store, so operators can inspect what an application runs without access to its code.

- Applies only to streams groups (`group.protocol=streams`, KIP-1071 — see [streams rebalance protocol](running-and-rebalancing.md#streams-rebalance-protocol-kip-1071)).
- **Disabled by default**: active only when the broker sets `group.streams.topology.description.plugin.class` to a `StreamsGroupTopologyDescriptionPlugin`.
- Clients push automatically when asked — no code changes; turn off per client with `topology.description.push.enabled=false` (default `true`; only controls responses to solicitations).
- Descriptions are versioned by the group's **topology epoch**.

### Push/describe cycle

1. **Solicitation:** if no successful push is recorded for the current topology epoch, the coordinator sets `TopologyDescriptionRequired` in the `StreamsGroupHeartbeat` response.
2. **Push:** the client sends `StreamsGroupTopologyDescriptionUpdate` (group ID, member ID, epoch, subtopologies/sources/processors/sinks/stores/global stores).
3. **Store:** the broker validates membership and calls `setTopology(groupId, topologyEpoch, description)`; on success it stops soliciting. Concurrent identical pushes are possible.
4. **Failures:** `StreamsTopologyDescriptionPermanentFailureException` → epoch marked failed, no re-solicit until the epoch advances; transient (any other exception) → per-group exponential back-off **30 s to 1 h**, then re-solicit. Clients see `STREAMS_TOPOLOGY_DESCRIPTION_UPDATE_FAILED` and don't retry themselves.
5. **Describe:** `StreamsGroupDescribe` v1+ with `IncludeTopologyDescription=true` calls `getTopology(groupId, topologyEpoch)`.
6. **Deletion:** on group deletion/expiry the broker calls `deleteTopology(groupId)`.

### Configuration

- Broker: `group.streams.topology.description.plugin.class` (unset = disabled; describes report `NOT_STORED`). Kafka ships `org.apache.kafka.server.streams.InMemoryTopologyDescriptionPlugin` for testing — **not for production** (lost on restart, not shared across brokers).
- Client: `topology.description.push.enabled` (default `true`).

### Implementing a plugin

From the `group-coordinator-api` module:

```java
public interface StreamsGroupTopologyDescriptionPlugin extends Configurable, AutoCloseable {
    CompletableFuture<Void> setTopology(String groupId, int topologyEpoch, StreamsGroupTopologyDescription description);
    CompletableFuture<Void> deleteTopology(String groupId);
    CompletableFuture<StreamsGroupTopologyDescription> getTopology(String groupId, int topologyEpoch);
}
```

- **Thread-safe** (`setTopology` may be called concurrently) and **idempotent** (same `(groupId, epoch)` data; repeated `deleteTopology`).
- **Complete futures asynchronously; never throw synchronously** — a synchronous throw from `setTopology` counts as a permanent failure.
- **Classify failures** as permanent vs transient (see above).
- `getTopology` returns the description only for the requested epoch, `null` if data is gone (→ `NOT_STORED`); exceptional completion → `ERROR`.
- One instance per broker, configured via `configure(Map)` and closed on shutdown.

### Reading descriptions

```java
try (Admin admin = Admin.create(props)) {
    DescribeStreamsGroupsResult result = admin.describeStreamsGroups(
        List.of("my-streams-app"),
        new DescribeStreamsGroupsOptions().includeTopologyDescription(true));
    StreamsGroupDescription description = result.describedGroups().get("my-streams-app").get();
    StreamsGroupTopologyDescriptionStatus status = description.topologyDescriptionStatus();
    Optional<StreamsGroupTopologyDescription> topology = description.topologyDescription();
}
```

`StreamsGroupTopologyDescription` mirrors `org.apache.kafka.streams.TopologyDescription` without depending on `kafka-streams`. Brokers older than 4.4 → `UnsupportedVersionException`.

```bash
kafka-streams-groups.sh --bootstrap-server localhost:9092 \
  --describe --group my-streams-app --topology
```

| Status | Meaning |
| --- | --- |
| `NOT_REQUESTED` | Caller didn't request it. |
| `NOT_STORED` | Nothing recorded (no plugin, or not pushed yet). |
| `ERROR` | Plugin read failed — check broker logs. |
| `AVAILABLE` | Description included (only in this case). |

### Deletion, removal and downgrade

- If `deleteTopology` fails, `DeleteGroups` returns **`GROUP_DELETION_FAILED`** for the group (reason in `ErrorMessage`, `DeleteGroups` v3+); fix the backend and retry (idempotent).
- Unsetting the plugin or downgrading below 4.4 stops cleanup calls; existing entries stay in the plugin's storage and must be cleaned manually — expected, not corruption.

### Observability and troubleshooting

Metrics under `kafka.server:type=group-coordinator-metrics` (each as `-rate` and `-count`): `streams-group-topology-description-set-success/-error`, `-get-success/-error`, `-delete-success/-error`, `-cleanup-cycle`, `-cleanup-eligible`. Watch the **`-error`** sensors first.

- **`NOT_STORED`:** plugin class set on all coordinator brokers? push not disabled? new epoch not yet pushed (wait a few heartbeats)? permanent failure (no re-solicit until epoch changes)? data lost (stays `NOT_STORED` until the topology epoch advances — restarting without a topology change won't fix it).
- **`ERROR`:** `getTopology` failed — see coordinator broker logs.
- **Push failures:** `STREAMS_TOPOLOGY_DESCRIPTION_UPDATE_FAILED` (broker re-solicits with back-off); `UNKNOWN_MEMBER_ID` if fenced/deleted — self-healing.
- **`UnsupportedVersionException`:** broker < 4.4.

## Related pages

- [Streams DSL](dsl-api.md)
- [Running, scaling and the streams rebalance protocol](running-and-rebalancing.md)
- [Configuration](configuration.md#topology)
- [Group coordinator metrics](../monitoring/broker-and-kraft-metrics.md#group-coordinator-metrics)
