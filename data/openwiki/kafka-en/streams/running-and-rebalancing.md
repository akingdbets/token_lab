---
type: operations-guide
title: Running, Scaling and Resetting Streams Apps
description: Operating Kafka Streams applications — starting instances, state/exception/restore/standby listeners, elastic scaling and state restoration with standbys and warmups, sizing instance counts, crash states, user vs internal topics and internal topic defaults, the application reset tool, security and required ACLs, and the KIP-1071 streams rebalance protocol (group.protocol=streams) with its broker/group configs, limitations, migration and the kafka-streams-groups.sh CLI.
tags: [streams, operations, scaling, rebalance, kip-1071, reset-tool, security, kafka-streams-groups]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-fddc8cc226c10b4886209feb
    resource: repo://docs/streams/developer-guide/app-reset-tool.md
  - id: openwiki-source-effa223e4e5cd7f508e10c78
    resource: repo://docs/streams/developer-guide/kafka-streams-group-sh.md
  - id: openwiki-source-2cf512d3d58894a60100487c
    resource: repo://docs/streams/developer-guide/manage-topics.md
  - id: openwiki-source-6534b9110ee20667cf929f02
    resource: repo://docs/streams/developer-guide/running-app.md
  - id: openwiki-source-eb65cb08387dd705102fec6d
    resource: repo://docs/streams/developer-guide/security.md
  - id: openwiki-source-8e13573fed29070c5b35d6db
    resource: repo://docs/streams/developer-guide/streams-rebalance-protocol.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Running, Scaling and Resetting Streams Apps

## Starting an application

A Streams app is an ordinary Java program — package it (e.g. a fat JAR) and run it:

```bash
# Start the application in class `com.example.MyStreamsApp`
# from the fat JAR named `path-to-app-fatjar.jar`.
$ java -cp path-to-app-fatjar.jar com.example.MyStreamsApp
```

Each process is an **instance**; run as many in parallel as you like. On start, the topology is initialized as stream tasks and their state stores are constructed (and restored if needed).

### Listeners and callbacks

All must be set **before `start()`** (afterwards → `IllegalStateException`); the last setter call wins.

**State listener** — states `CREATED`, `REBALANCING`, `RUNNING`, `PENDING_SHUTDOWN`, `NOT_RUNNING`, `PENDING_ERROR`, `ERROR`:

```java
KafkaStreams streams = new KafkaStreams(topology, props);
streams.setStateListener((newState, oldState) -> {
    if (newState == KafkaStreams.State.RUNNING) {
        // application is now ready to process records
    } else if (newState == KafkaStreams.State.ERROR) {
        // application has encountered a fatal error
    }
});
streams.start();
```

**Uncaught exception handler** — return a `StreamThreadExceptionResponse`:

- `REPLACE_THREAD` — replace the failed thread.
- `SHUTDOWN_CLIENT` — shut down this client.
- `SHUTDOWN_APPLICATION` — best-effort request (via the rebalance protocol) that **all** instances shut down.

```java
streams.setUncaughtExceptionHandler(exception -> {
    if (exception instanceof RetriableException) {
        return StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.REPLACE_THREAD;
    }
    return StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.SHUTDOWN_CLIENT;
});
```

The handler runs on the failing thread and is shared by all threads — it **must be thread-safe** (`Thread.currentThread()` identifies the thread).

**State restore listener** (`setGlobalStateRestoreListener`) — `onRestoreStart`, `onBatchRestored`, `onRestoreEnd`, `onRestoreSuspended` (task migrated). Thread-safe; doesn't cover standbys.

**Standby update listener** (`setStandbyUpdateListener`) — `onUpdateStart`, `onBatchLoaded` (batch end offset, size, current changelog end), `onUpdateSuspended` with `SuspendReason.MIGRATED` or `PROMOTED` (then `onRestoreStart` follows).

Shut down cleanly with `streams.close()` (e.g. in a JVM shutdown hook) — see [Writing an application](writing-an-application.md).

## Elastic scaling

Streams uses Kafka group management, so capacity can be added or removed at runtime without downtime or data loss.

- **Add capacity:** start more instances; they join the group and take over some tasks (with their state). Each instance is its own JVM with its own resources.
- **Remove capacity:** stop instances; they leave the group and others take over their tasks.

### State restoration on migration

A migrated task's state is **fully restored before processing resumes**, usually by replaying its changelog:

- No local store → replay from the earliest offset.
- Existing local store → replay from the last checkpointed offset (faster).

`num.standby.replicas` keeps replicated local copies to minimize restoration. **Since 2.6**, warmup replicas restore in the background, and a stateful active task is only assigned to an instance whose state lag is within `acceptable.recovery.lag` — so most migrations don't block processing. If no instance is caught up, an active must restore before processing; enable standbys for high availability.

### How many instances?

Parallelism is bounded by **input partitions**: 10 partitions → up to 10 useful instances (more are idle spares). Spread **data** and **processing cost** evenly across partitions to avoid hot spots.

### Crashes

Configure the [resiliency settings](configuration.md#recommended-for-resiliency), exception handlers (deserialization, production, processing) and DLQs for poison pills. On fatal failure an instance goes `PENDING_ERROR` (closing resources) then `ERROR`; **`PENDING_ERROR` is not recoverable** — only a restart returns it to `RUNNING`, so alert on both states.

## Topics

### User topics

Input topics (from `StreamsBuilder#stream()`, `#table()`, `Topology#addSource()`) and output topics (`KStream#to()`, `KTable.to()`, `Topology#addSink()`). **Create and manage them yourself** beforehand (e.g. `kafka-topics.sh`); don't rely on broker auto-creation (it may be disabled and applies default settings such as replication factor).

### Internal topics

Created and used only by the app (changelogs, repartition topics). Naming convention `<application.id>-<operatorName>-<suffix>` (not guaranteed to stay). Defaults:

- All: `message.timestamp.type=CreateTime`.
- Repartition: `cleanup.policy=delete`, retention `-1` (infinite; consumed data is purged by Streams every `repartition.purge.interval.ms`).
- Key-value changelogs: `compact`.
- Windowed changelogs: `delete,compact`, retention = window store retention + 24 hours.
- Versioned store changelogs: `compact`, `min.compaction.lag.ms` = history retention + 24 hours.

Override with `topic.`-prefixed configs ([configuration](configuration.md#configuring-the-embedded-clients)) or per store `withLoggingEnabled(...)`. Name internal topics explicitly for stable upgrades ([naming](topology-naming-and-description.md)).

## Resetting an application

Reprocess from scratch (development, testing, bug fixes). **All instances must be stopped** (check the `application.id` group with `bin/kafka-consumer-groups.sh`); double-check parameters — mistakes can damage state or other apps. Always try `--dry-run` first.

- **Streams rebalance protocol** groups (4.2+): use `kafka-streams-groups.sh --reset-offsets` (below).
- **Classic** groups: `bin/kafka-streams-application-reset.sh`.

What the classic tool does: **input topics** → reset offsets (default to the beginning); **internal topics** → deleted (and their offsets). It does **not** reset output topics (adjust downstream consumers yourself) or local state.

```bash
$ bin/kafka-streams-application-reset.sh --bootstrap-server localhost:9092 \
    --application-id my-streams-app \
    --input-topics my-input-topic \
    --to-earliest --dry-run
```

| Option | Meaning |
| --- | --- |
| `--application-id` (required) | The `application.id`. |
| `--bootstrap-server` | Default `localhost:9092`. |
| `--input-topics` | Input topics to reset (to earliest by default). Omit to restart from empty state without reprocessing. |
| `--internal-topics` | Subset of internal topics to delete (see the dry run for the default list). |
| `--to-earliest`, `--to-latest`, `--to-offset`, `--to-datetime 'YYYY-MM-DDThh:mm:ss.sss'`, `--by-duration 'PnDTnHnMnS'`, `--shift-by n`, `--from-file` | One reset scenario (default `to-earliest`). |
| `--command-config` | Admin/consumer properties (`--config-file` is deprecated). |
| `--dry-run` | Preview only. |
| `--force` | Remove leftover group members (long session timeouts). |

Then reset **local state** on every machine before restarting: call `KafkaStreams#cleanUp()` (may leave the directory with `kafka-streams-process-metadata`/`.lock`), or delete `<state.dir>/<application.id>` (default under `${java.io.tmpdir}/kafka-streams/`).

## Security

Streams supports all client-side security: configure the usual `security.protocol`, `ssl.*`, `sasl.*` settings in the Streams properties (they apply to its embedded clients):

```properties
# Essential security settings to enable client authentication and SSL encryption
bootstrap.servers=kafka.example.com:9093
security.protocol=SSL
ssl.truststore.location=/etc/security/tls/kafka.client.truststore.jks
ssl.truststore.password=test1234
ssl.keystore.location=/etc/security/tls/kafka.client.keystore.jks
ssl.keystore.password=test1234
ssl.key.password=test1234
```

```java
Properties settings = new Properties();
settings.put(StreamsConfig.APPLICATION_ID_CONFIG, "secure-kafka-streams-app");
settings.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka.example.com:9093");
settings.put(CommonClientConfigs.SECURITY_PROTOCOL_CONFIG, "SSL");
settings.put(SslConfigs.SSL_TRUSTSTORE_LOCATION_CONFIG, "/etc/security/tls/kafka.client.truststore.jks");
settings.put(SslConfigs.SSL_TRUSTSTORE_PASSWORD_CONFIG, "test1234");
settings.put(SslConfigs.SSL_KEYSTORE_LOCATION_CONFIG, "/etc/security/tls/kafka.client.keystore.jks");
settings.put(SslConfigs.SSL_KEYSTORE_PASSWORD_CONFIG, "test1234");
settings.put(SslConfigs.SSL_KEY_PASSWORD_CONFIG, "test1234");
```

Misconfiguration fails fast at startup, e.g. a wrong keystore password: `KafkaException: Failed to construct kafka producer … Keystore was tampered with, or password was incorrect`.

**ACLs:** the app's principal must be able to create, read and write its **internal topics** and use its group. Because internal topics and the group share the `application.id` prefix, use **prefixed ACLs**, e.g. `--resource-pattern-type prefixed --topic your.application.id --operation All` (KIP-277, KIP-290). With `group.protocol=streams` additionally:

| API | Operation | Resource | Notes |
| --- | --- | --- | --- |
| `STREAMS_GROUP_HEARTBEAT` | Read | Group | The app's streams group. |
| `STREAMS_GROUP_HEARTBEAT` | Create | Cluster, or all changelog/repartition topics | Only if internal topics are auto-created. |
| `STREAMS_GROUP_HEARTBEAT` | Describe | Topic | All topics in the topology. |

To avoid granting topic creation, **pre-create internal topics** with the right partition count (equal to the input topic, or the max across inputs) and, for changelogs, compaction (`delete,compact` with suitable retention for windowed KTables) — otherwise startup fails or data may be lost. Security model: [Streams security model](../security/listeners-and-security-overview.md#kafka-streams-security-model).

## Streams rebalance protocol (KIP-1071)

The broker-driven protocol for Streams, following KIP-848 for consumers: assignments are computed **continuously on the broker**, and the app registers as a **streams group** (separate from consumer groups) with streams-specific metadata.

**Benefits:** a single authoritative coordinator (fewer split-brain risks), faster and more stable rebalances without a global sync barrier, and better observability (dedicated metrics, Admin APIs, CLI).

### Enabling

Enabled by default on **new clusters from Kafka 4.2**; brokers **and** clients must be 4.2+.

```bash
# existing clusters (after upgrading to 4.2)
bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --feature streams.version=1
# disable
bin/kafka-features.sh --bootstrap-server localhost:9092 downgrade --feature streams.version=0
```

```properties
# application
group.protocol=streams
```

### Supported

- Dedicated streams group lifecycle and metadata.
- **Sticky task assignor** (`sticky`, default); custom `TaskAssignor`s via broker `group.streams.assignors` (first is default), selectable per group with `streams.assignor.name`.
- Interactive queries.
- Admin API (`describeStreamsGroups`, `StreamsGroupDescribe` RPC) and `kafka-streams-groups.sh`.
- Topology description plugin (`group.streams.topology.description.plugin.class`).
- Offline migration (classic ↔ streams).
- Static membership with `group.instance.id` — requires clients and brokers on **4.4+** (older brokers reject it with `INVALID_REQUEST`, a fatal error).

### Not supported yet

- Significant **topology changes** (new source topics, different number of subtopologies) — create a new group.
- A high-availability assignor or rack-aware assignment in the built-in assignor (custom assignors can implement it).
- **Warmup tasks** (planned to be injected by the coordinator).
- **Regex** topic subscriptions.
- **Online** migration.
- A custom `KafkaClientSupplier` can't provide the main consumer.

### Configuration

Broker: `group.streams.session.timeout.ms` (+ `min`/`max`), `group.streams.heartbeat.interval.ms` (+ `min`/`max`), `group.streams.max.size`, `group.streams.num.standby.replicas`, `group.streams.max.standby.replicas`, `group.streams.initial.rebalance.delay.ms`, `group.streams.assignors`, `group.streams.topology.description.plugin.class`; `group.coordinator.rebalance.protocols` must include `streams` (deprecated config).

Group-level (dynamic, via `kafka-configs.sh` or Admin): `streams.session.timeout.ms` (45000), `streams.heartbeat.interval.ms` (5000), `streams.num.standby.replicas` (0), `streams.initial.rebalance.delay.ms` (3000), `streams.assignor.name`:

```bash
bin/kafka-configs.sh --bootstrap-server localhost:9092 \
  --alter --entity-type groups --entity-name wordcount \
  --add-config streams.num.standby.replicas=1
```

**Ignored client configs** with `group.protocol=streams`: `acceptable.recovery.lag`, `max.warmup.replicas`, `num.standby.replicas`, `probing.rebalance.interval.ms`, `rack.aware.assignment.tags`, `rack.aware.assignment.strategy`, `rack.aware.assignment.traffic_cost`, `rack.aware.assignment.non_overlap_cost`, `task.assignor.class`, `session.timeout.ms`, `heartbeat.interval.ms` — use broker/group configs instead.

### How it works

- Clients use `StreamsGroupHeartbeat` to join/leave and report owned tasks. A group ID's type (streams, share or consumer) is fixed by its first heartbeat.
- The first heartbeat carries **topology metadata** (subtopologies), persisted in `__consumer_offsets`.
- The coordinator validates: source topics exist, co-partitioning holds, internal topic partition counts are derivable, internal topics exist with the right config. Problems put the group in **`NOT_READY`**: heartbeats still succeed, responses report the problem, and members get **empty assignments**.
- Assignment options (e.g. standby count) are central on the broker and can change without redeploying; changes trigger immediate reassignment.
- Admin differences: `describeStreamsGroups` returns streams-specific data, there's an extra `NOT_READY` state, and no `removeMembersFromConsumerGroup` equivalent.

Metrics: `kafka.server:type=group-coordinator-metrics,name=group-count,protocol={consumer|classic|streams}`, `name=streams-group-count,state={empty|not_ready|assigning|reconciling|stable|dead}`, `name=streams-group-rebalance-rate` / `-count`.

### Migrating (offline only)

1. Stop all instances.
2. Wait for `session.timeout.ms` to expire (or force a group leave) so the group is empty.
3. Set `group.protocol=streams` (or back to `classic`).
4. Restart.

Only committed offsets are preserved; other group metadata is recreated; internal topics remain. **Don't migrate classic → streams on 4.2.0** (KAFKA-20254); use 4.2.1+. New streams groups aren't affected.

## kafka-streams-groups.sh

Manages streams groups (replaces `kafka-streams-application-reset.sh` for them). Connect with `--bootstrap-server`; pass security via `--command-config`. Mutating operations require stopped instances and an empty group; preview with `--dry-run`.

```bash
# list (optionally show/filter by state with --state)
kafka-streams-groups.sh --bootstrap-server localhost:9092 --list

# describe: state and epochs / members / input-topic offsets and lag / topology
kafka-streams-groups.sh --bootstrap-server localhost:9092 --describe --group my-streams-app --state --verbose
kafka-streams-groups.sh --bootstrap-server localhost:9092 --describe --group my-streams-app --members --verbose
kafka-streams-groups.sh --bootstrap-server localhost:9092 --describe --group my-streams-app --offsets
kafka-streams-groups.sh --bootstrap-server localhost:9092 --describe --group my-streams-app --topology

# reset input-topic offsets (preview, then apply)
kafka-streams-groups.sh --bootstrap-server localhost:9092 \
  --group my-streams-app \
  --reset-offsets --all-input-topics --to-datetime 2025-01-31T23:57:00.000 \
  --dry-run
kafka-streams-groups.sh --bootstrap-server localhost:9092 \
  --group my-streams-app \
  --reset-offsets --all-input-topics --to-datetime 2025-01-31T23:57:00.000 \
  --execute

# delete offsets to force re-consumption
kafka-streams-groups.sh --bootstrap-server localhost:9092 --group my-streams-app --delete-offsets --all-input-topics
kafka-streams-groups.sh --bootstrap-server localhost:9092 --group my-streams-app --delete-offsets --input-topic input-a --input-topic input-b

# delete group metadata (optionally all internal topics)
kafka-streams-groups.sh --bootstrap-server localhost:9092 --delete --group my-streams-app
kafka-streams-groups.sh --bootstrap-server localhost:9092 --delete --group my-streams-app --delete-all-internal-topics
```

- States shown: Empty, Not Ready, Assigning, Reconciling, Stable, Dead.
- `--members --verbose` shows epochs, current vs target assignments and whether a member still uses the classic protocol.
- `--topology` prints a `Topology#describe()`-style view recorded by the broker's plugin — needs brokers **4.4+** with `group.streams.topology.description.plugin.class`; otherwise `UnsupportedVersionException` or "No topology description is stored…" (non-zero exit).
- Reset specifiers (exactly one): `--to-earliest`, `--to-latest`, `--to-current`, `--to-offset`, `--by-duration`, `--to-datetime`, `--shift-by`, `--from-file`; scope `--all-input-topics` or `--input-topic`; with `--execute` you can add `--delete-internal-topic <t>` / `--delete-all-internal-topics` (only when you intend to rebuild state from inputs).
- Other flags: `--all-groups` (with `--delete`), `--timeout` (default 30000 ms), `--help`, `--version`.

## Related pages

- [Configuration](configuration.md)
- [Consumer groups and rebalance protocols](../clients/consumer-groups-and-rebalance.md)
- [Topology naming and description plugin](topology-naming-and-description.md)
- [Streams metrics](../monitoring/client-metrics.md#kafka-streams-metrics)
