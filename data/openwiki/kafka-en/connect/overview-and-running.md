---
type: operations-guide
title: "Kafka Connect: Overview and Running Workers"
description: What Kafka Connect is and how to run it — standalone vs. distributed workers, required worker configs and the shipped connect-*.properties files, internal config/offset/status topics, client config prefixes and per-connector overrides, common connector configs, plugin.path layout, plugin discovery modes and the connect-plugin-path.sh migration tool, plus key worker config defaults.
tags: [connect, workers, standalone, distributed, plugin-path, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-6ec7adf2898acf934e5f7708
    resource: repo://config/connect-file-sink.properties
  - id: openwiki-source-1e57f1f2b7affeb6cbec8dbd
    resource: repo://config/connect-file-source.properties
  - id: openwiki-source-5b79839cbe27f32c7c963251
    resource: repo://docs/generated/connect_config.html
  - id: openwiki-source-879c710378f4939b0b8f9110
    resource: repo://docs/getting-started/quickstart.md
  - id: openwiki-source-0cfab4979b85f5c875d630fd
    resource: repo://docs/kafka-connect/user-guide.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Kafka Connect: Overview and Running Workers

Kafka Connect is a tool for scalably and reliably streaming data between Kafka and other systems. You define **connectors** that move large collections of data into Kafka (e.g. whole databases, metrics from all servers) or out of Kafka (into secondary storage, query systems or batch systems).

Features:

- **Common framework** for connectors — standardized development, deployment and management.
- **Distributed and standalone modes** — from an organization-wide service down to development and small deployments.
- **REST interface** to submit and manage connectors (see [REST API and operations](rest-api-and-operations.md)).
- **Automatic offset management** — connectors provide a little information and Connect handles offset commits.
- **Distributed and scalable by default** — built on Kafka's group management protocol; add workers to scale.
- **Streaming/batch integration.**

## Standalone mode

All work happens in a single process: simple to set up, good when one worker makes sense (e.g. collecting log files), but **no fault tolerance**.

```bash
$ bin/connect-standalone.sh config/connect-standalone.properties [connector1.properties connector2.json …]
```

The first argument is the worker config; the rest are connector configs (Java properties, or JSON matching the body of `POST /connectors` or `PUT /connectors/{name}/config`). All connectors run in the same process on different threads; you can also omit them and create connectors via REST.

`config/connect-standalone.properties`:

```properties
bootstrap.servers=localhost:9092
key.converter=org.apache.kafka.connect.json.JsonConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
key.converter.schemas.enable=true
value.converter.schemas.enable=true
offset.storage.file.filename=/tmp/connect.offsets
offset.flush.interval.ms=10000
```

Standalone-specific: `offset.storage.file.filename` — file storing source connector offsets.

### Quickstart: file source → topic → file sink

```bash
$ echo "plugin.path=libs/connect-file-4.3.0.jar" >> config/connect-standalone.properties
$ echo -e "foo\nbar" > test.txt
$ bin/connect-standalone.sh config/connect-standalone.properties config/connect-file-source.properties config/connect-file-sink.properties
$ more test.sink.txt
foo
bar
$ bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic connect-test --from-beginning
{"schema":{"type":"string","optional":false},"payload":"foo"}
{"schema":{"type":"string","optional":false},"payload":"bar"}
```

`config/connect-file-source.properties`:

```properties
name=local-file-source
connector.class=FileStreamSource
tasks.max=1
file=test.txt
topic=connect-test
```

`config/connect-file-sink.properties`:

```properties
name=local-file-sink
connector.class=FileStreamSink
tasks.max=1
file=test.sink.txt
topics=connect-test
```

(`connect-console-source.properties` / `connect-console-sink.properties` use `org.apache.kafka.connect.file.FileStreamSourceConnector` / `FileStreamSinkConnector` without a `file`, i.e. stdin/stdout.) The FileStream connectors in `connect-file-4.3.0.jar` are **not** on the worker's `CLASSPATH` or `plugin.path` by default — add them first.

## Distributed mode

Automatic work balancing, dynamic scale up/down, and fault tolerance for tasks and for config/offset data:

```bash
$ bin/connect-distributed.sh config/connect-distributed.properties
```

`config/connect-distributed.properties`:

```properties
bootstrap.servers=localhost:9092
group.id=connect-cluster
key.converter=org.apache.kafka.connect.json.JsonConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
key.converter.schemas.enable=true
value.converter.schemas.enable=true
offset.storage.topic=connect-offsets
offset.storage.replication.factor=1
config.storage.topic=connect-configs
config.storage.replication.factor=1
status.storage.topic=connect-status
status.storage.replication.factor=1
offset.flush.interval.ms=10000
```

Offsets, configs and task statuses are stored in **Kafka topics**. Critical settings:

| Config | Meaning |
| --- | --- |
| `group.id` | Unique Connect cluster name; **must not conflict** with consumer group IDs. |
| `config.storage.topic` | Connector/task configs — **single partition**, replicated, compacted. |
| `offset.storage.topic` | Source offsets — **many partitions**, replicated, compacted. |
| `status.storage.topic` | Statuses — multiple partitions OK, replicated, compacted. |

Create these topics manually to control partitions and replication; otherwise they are auto-created (`internal.topics.automatic.creation.enable`, default `true`) with `offset.storage.partitions=25`, `status.storage.partitions=5` and replication factor `3` each. In distributed mode connector configs are **not** passed on the command line — use the REST API.

## Required worker configs (both modes)

- `bootstrap.servers` — Kafka servers to bootstrap.
- `key.converter` / `value.converter` — converters between Connect's data format and the bytes in Kafka (e.g. JSON, Avro); independent of connectors, so any connector works with any format.
- `plugin.path` (default `null`) — where plugins live (see below).

### Client config prefixes

Worker-level client settings apply to the producers/consumers Connect uses for its config, offset and status topics. For the producers of **source tasks** and consumers of **sink tasks**, repeat them with the `producer.` and `consumer.` prefixes. Only `bootstrap.servers` is inherited without a prefix — so on a secured cluster, security settings typically appear **three times** (management, sources, sinks):

```properties
security.protocol=SASL_SSL
producer.security.protocol=SASL_SSL
consumer.security.protocol=SASL_SSL
```

Per-connector overrides use `producer.override.` and `consumer.override.` inside the connector config, permitted by the worker's `connector.client.config.override.policy` (default `All`).

## Configuring connectors

Connector configs are key/value maps, sent as JSON over REST (or properties files in standalone mode). Common options:

| Config | Meaning |
| --- | --- |
| `name` | Unique connector name; re-registering the same name fails. |
| `connector.class` | Connector class — full name or alias (`org.apache.kafka.connect.file.FileStreamSinkConnector`, `FileStreamSink` or `FileStreamSinkConnector`). |
| `tasks.max` | Maximum tasks (default `1`); a connector may create fewer. |
| `key.converter` / `value.converter` | Optional per-connector override of worker converters. |
| `topics` / `topics.regex` | **Sink connectors must set one**: comma-separated topics or a Java regex. |
| `transforms` / `predicates` | [Single message transforms](transformations-and-predicates.md). |
| `errors.*` | [Error handling and DLQ](rest-api-and-operations.md#error-reporting-and-dead-letter-queues). |

Other connector defaults: `tasks.max.enforce=true`, `config.action.reload=restart`, `header.converter=null` (worker default `org.apache.kafka.connect.storage.SimpleHeaderConverter`), and for source connectors `exactly.once.support=requested`, `transaction.boundary=poll`.

## plugin.path

A comma-separated list of paths containing plugins (connectors, converters, transformations). Each path is a plugin archive (JAR/ZIP) or a directory; in a directory, **each direct child** (directory or archive) is loaded with its own class loader:

- a directory of JARs/ZIPs with a plugin and its dependencies,
- an uber-jar,
- or a directory with the package structure of classes.

Children are scanned recursively; symlinks are followed. For class-loading isolation put each plugin in its own direct child directory:

```properties
plugin.path=/usr/local/share/java,/usr/local/share/kafka/plugins,/opt/connectors
# /opt/connectors/my-plugin/        (deps may be nested, e.g. /opt/connectors/my-plugin/lib/dep.jar)
# /opt/connectors/another-plugin.jar
```

**Do not use config provider variables** in `plugin.path`: the scanner reads the raw path before config providers are initialized. Prefer absolute paths in production.

## Plugin discovery

`plugin.discovery` controls how workers find plugins and strongly affects startup time:

| Mode | Behavior |
| --- | --- |
| `only_scan` | Reflection only (behavior before 3.6). |
| `hybrid_warn` (**default since 3.6**) | Reflection + ServiceLoader; warns about plugins not discoverable by ServiceLoader. |
| `hybrid_fail` | Like `hybrid_warn`, but worker startup fails on incompatible plugins. |
| `service_load` | ServiceLoader only — fastest; incompatible plugins may be unusable. |

To verify compatibility (Connect ≥ 3.6): start with `hybrid_warn` and WARN logging for `org.apache.kafka.connect` (a log line mentions `plugin.discovery` and lists incompatible plugins), or start a test worker with `hybrid_fail`. Re-verify after installing or upgrading plugins (CI-friendly).

Fixing incompatible plugins, most to least preferable: upgrade to a compatible release; ask the vendor to add manifests ([developer instructions](connector-development.md#packaging-for-plugin-discovery)); or migrate artifacts yourself with `bin/connect-plugin-path.sh` (`bin\windows\connect-plugin-path.bat`):

```bash
bin/connect-plugin-path.sh list --worker-config config/connect-distributed.properties
bin/connect-plugin-path.sh sync-manifests --worker-config config/connect-distributed.properties --dry-run
bin/connect-plugin-path.sh sync-manifests --worker-config config/connect-distributed.properties
```

Locate plugins with repeatable `--worker-config`, `--plugin-path` or `--plugin-location`; classpath plugins are ignored. `sync-manifests` modifies JARs/resources (not suitable with code signing), needs writable paths and is idempotent — back up first and dry-run before the real run.

## Key worker config defaults

| Config | Default |
| --- | --- |
| `listeners` | `http://:8083` (REST API) |
| `admin.listeners` | `null` (use regular listeners) |
| `rest.advertised.host.name` / `rest.advertised.port` / `rest.advertised.listener` | `null` |
| `offset.flush.interval.ms` | `60000` (sample files use `10000`) |
| `offset.flush.timeout.ms` | `5000` |
| `session.timeout.ms` / `heartbeat.interval.ms` / `rebalance.timeout.ms` | `10000` / `3000` / `60000` |
| `scheduled.rebalance.max.delay.ms` | `300000` (wait for departed workers before reassigning) |
| `connect.protocol` | `sessioned` |
| `exactly.once.source.support` | `disabled` |
| `topic.creation.enable` | `true` |
| `task.shutdown.graceful.timeout.ms` | `5000` |
| `request.timeout.ms` | `40000` |
| `header.converter` | `org.apache.kafka.connect.storage.SimpleHeaderConverter` |
| `config.storage.replication.factor` / `offset.storage.replication.factor` / `status.storage.replication.factor` | `3` |
| `offset.storage.partitions` / `status.storage.partitions` | `25` / `5` |
| `connector.client.config.override.policy` | `All` |
| `rest.extension.classes` | `""` |
| `inter.worker.signature.algorithm` / `inter.worker.key.ttl.ms` | `HmacSHA256` / `3600000` |

Full reference: `docs/generated/connect_config.html` (worker), `source_connector_config.html`, `sink_connector_config.html`. MirrorMaker 2 runs on Connect — see [Geo-replication](../operations/geo-replication-mirrormaker.md).

## Related pages

- [Single message transforms and predicates](transformations-and-predicates.md)
- [REST API, error handling, exactly-once and security](rest-api-and-operations.md)
- [Developing connectors](connector-development.md)
- [Configuration providers](../configuration/config-providers-and-system-properties.md) for connector secrets
- [Connect monitoring](../monitoring/client-metrics.md)
