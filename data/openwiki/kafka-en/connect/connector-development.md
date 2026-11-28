---
type: developer-guide
title: Developing Kafka Connect Connectors
description: How to write Kafka Connect source and sink connectors — the Connector/Task split, SourceTask poll() with source partitions and offsets, SinkTask put()/flush(), ErrantRecordReporter, resuming from stored offsets, exactly-once source support (KIP-618) and transaction boundaries, dynamic reconfiguration, ConfigDef validation, the Schema/Struct data API and ServiceLoader manifests.
tags: [connect, connector-development, source-connector, sink-connector, exactly-once, schemas, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-870b2d94fd961c993acc749f
    resource: repo://docs/kafka-connect/connector-development-guide.md
  - id: openwiki-source-0cfab4979b85f5c875d630fd
    resource: repo://docs/kafka-connect/user-guide.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Developing Kafka Connect Connectors

Most users run existing connectors (see [Running Connect](overview-and-running.md)). This page is for developers implementing new ones with the Connect API (`org.apache.kafka.connect.*`, artifact `connect-api`). Use the [Internal API Checker](../clients/apis-overview.md#internal-api-checker-kip-1265) to make sure your plugin only uses public Kafka APIs.

## Core concepts

### Connectors and tasks

- A **`Connector`** describes *what* to copy. **`SourceConnector`**s import from another system (e.g. a `JDBCSourceConnector` importing a database); **`SinkConnector`**s export (e.g. an `HDFSSinkConnector`).
- Connectors don't copy data themselves: they split the job into **`Task`**s that the framework distributes to workers — **`SourceTask`** and **`SinkTask`**.
- Each task copies its subset of data, modeled as **input/output streams of records with consistent schemas**. A file connector maps each file to a stream with byte offsets as offsets; a JDBC connector might map each table to a stream and use a timestamp column as the offset.

### Streams, records and offsets

Each stream is a sequence of key/value records with possibly complex structure (primitives, arrays, objects, nested structures). The runtime data format is serialization-independent — converters handle serialization. Records carry **stream IDs (source partitions)** and **offsets**, which the framework commits periodically so processing resumes from the last commit after a failure.

### Dynamic connectors

Connectors also watch the external system for changes requiring reconfiguration (e.g. new tables) and notify the framework, which updates the tasks.

## A simple source connector

You implement two interfaces, `Connector` and `Task`. Kafka's `file` package includes `FileStreamSourceConnector`/`FileStreamSourceTask` and a sink pair, intended for standalone mode.

### Make the plugin discoverable

Add a ServiceLoader manifest `META-INF/services/org.apache.kafka.connect.source.SourceConnector` containing the fully qualified class name:

```text
com.example.FileStreamSourceConnector
```

### The connector

```java
public class FileStreamSourceConnector extends SourceConnector {
    private Map<String, String> props;

    @Override
    public Class<? extends Task> taskClass() {
        return FileStreamSourceTask.class;
    }

    @Override
    public void start(Map<String, String> props) {
        this.props = props;
        AbstractConfig config = new AbstractConfig(CONFIG_DEF, props);
        String filename = config.getString(FILE_CONFIG);
        filename = (filename == null || filename.isEmpty()) ? "standard input" : config.getString(FILE_CONFIG);
        log.info("Starting file source connector reading from {}", filename);
    }

    @Override
    public void stop() {
        // Nothing to do since no background monitoring is required.
    }

    @Override
    public List<Map<String, String>> taskConfigs(int maxTasks) {
        ArrayList<Map<String, String>> configs = new ArrayList<>();
        // Only one input stream makes sense.
        configs.add(props);
        return configs;
    }
}
```

`taskConfigs(maxTasks)` is the core: decide how many tasks are needed (≤ `maxTasks`) and give each its share of the work. Task configs may differ from the connector config. `ConnectorUtils` provides helpers for common work-splitting patterns.

### The source task

```java
public class FileStreamSourceTask extends SourceTask {
    @Override
    public void start(Map<String, String> props) {
        filename = props.get(FileStreamSourceConnector.FILE_CONFIG);
        stream = openOrThrowError(filename);
        topic = props.get(FileStreamSourceConnector.TOPIC_CONFIG);
        batchSize = props.get(FileStreamSourceConnector.TASK_BATCH_SIZE_CONFIG);
    }

    @Override
    public synchronized void stop() {
        stream.close();
    }

    @Override
    public List<SourceRecord> poll() throws InterruptedException {
        try {
            ArrayList<SourceRecord> records = new ArrayList<>();
            while (streamValid(stream) && records.isEmpty()) {
                LineAndOffset line = readToNextLine(stream);
                if (line != null) {
                    Map<String, Object> sourcePartition = Collections.singletonMap("filename", filename);
                    Map<String, Object> sourceOffset = Collections.singletonMap("position", streamOffset);
                    records.add(new SourceRecord(sourcePartition, sourceOffset, topic, Schema.STRING_SCHEMA, line));
                    if (records.size() >= batchSize) {
                        return records;
                    }
                } else {
                    Thread.sleep(1);
                }
            }
            return records;
        } catch (IOException e) {
            // Underlying stream was killed, probably as a result of calling stop.
        }
        return null;
    }
}
```

Key points:

- `start()`/`stop()` should only allocate/free resources. `stop()` is `synchronized` because each `SourceTask` gets a **dedicated thread** that may block indefinitely; the worker stops it from another thread.
- `poll()` is called repeatedly and returns `List<SourceRecord>`. A `SourceRecord` carries a **source partition**, **source offset**, topic and value (+ schema); other constructors add an explicit Kafka partition, a key and headers. Blocking/sleeping in `poll()` is acceptable.
- Optional `commit()` and `commitRecord()` let a source acknowledge messages in the source system (bulk or per record) after they are written to Kafka. Connect records offsets automatically, so these are only needed for sources with an acknowledgement mechanism.

### Sink tasks

`SinkTask` uses a **push** interface:

```java
public abstract class SinkTask implements Task {
    public void initialize(SinkTaskContext context) {
        this.context = context;
    }

    public abstract void put(Collection<SinkRecord> records);

    public void flush(Map<TopicPartition, OffsetAndMetadata> currentOffsets) {
    }
}
```

- `put()` translates and writes `SinkRecord`s (topic, partition, offset, key, value, headers). It need not finish the write before returning — internal buffering for batch writes is encouraged.
- `flush()` is called during offset commit: push outstanding data and **block until acknowledged**. The offsets can be stored in the destination for exactly-once delivery (e.g. an HDFS connector atomically moving data and offsets).

### Reporting errant records

When error reporting is enabled (see [error handling](rest-api-and-operations.md#error-reporting-and-dead-letter-queues)), sink tasks can report bad records to the DLQ via `ErrantRecordReporter`:

```java
private ErrantRecordReporter reporter;

@Override
public void start(Map<String, String> props) {
    try {
        reporter = context.errantRecordReporter(); // may be null if DLQ not enabled
    } catch (NoSuchMethodException | NoClassDefFoundError e) {
        // Will occur in Connect runtimes earlier than 2.6
        reporter = null;
    }
}

@Override
public void put(Collection<SinkRecord> records) {
    for (SinkRecord record: records) {
        try {
            process(record);
        } catch(Exception e) {
            if (reporter != null) {
                reporter.report(record, e);
            } else {
                throw new ConnectException("Failed on record", e);
            }
        }
    }
}
```

### Resuming from previous offsets

The framework commits source offsets automatically, but only the task knows how to seek. Read stored offsets from the `SourceTaskContext` in `initialize()`/`start()`:

```java
stream = new FileInputStream(filename);
Map<String, Object> offset = context.offsetStorageReader().offset(Collections.singletonMap(FILENAME_FIELD, filename));
if (offset != null) {
    Long lastRecordedOffset = (Long) offset.get("position");
    if (lastRecordedOffset != null)
        seekToOffset(stream, lastRecordedOffset);
}
```

`OffsetStorageReader` also supports bulk reads for many partitions.

## Exactly-once source connectors (KIP-618)

Since Kafka **3.3.0**, Connect supports exactly-once source connectors. A connector must provide meaningful source offsets for every record and be able to resume at exactly the position of any offset without drops or duplicates. (Workers must have exactly-once enabled — see [Connect operations](rest-api-and-operations.md#exactly-once-support).)

### Transaction boundaries

By default the framework creates and commits **one Kafka transaction per batch returned by `poll()`**. If users set `transaction.boundary=connector` on the connector, tasks get a `TransactionContext` from `SourceTaskContext` and define boundaries themselves (otherwise `context.transactionContext()` returns `null`):

```java
// commit at least every ten records
if (shouldCommit) {
    this.recordsSent = 0;
    this.context.transactionContext().commitTransaction();
}

// commit exactly at every tenth record
if (++this.recordsSent % 10 == 0) {
    this.context.transactionContext().commitTransaction(record);
}
```

Useful when a file/object is split into multiple records that must be delivered atomically, or when records can't each have a unique offset.

### Preflight validation

When users set `exactly.once.support=required`, the framework calls `exactlyOnceSupport(props)`; implement it even if unsupported:

```java
@Override
public ExactlyOnceSupport exactlyOnceSupport(Map<String, String> props) {
    return ExactlyOnceSupport.UNSUPPORTED;   // or ExactlyOnceSupport.SUPPORTED
}

@Override
public ConnectorTransactionBoundaries canDefineTransactionBoundaries(Map<String, String> props) {
    return ConnectorTransactionBoundaries.SUPPORTED;
}
```

`canDefineTransactionBoundaries` is only needed for connectors that can define boundaries in some cases.

## Dynamic input/output streams

Connect jobs are meant to be bulk (e.g. a whole database), so the stream set can change over time.

```java
// in a SourceConnector
if (inputsChanged())
    this.context.requestTaskReconfiguration();
```

- The framework then requests new task configs and lets tasks commit progress before reconfiguring. Any monitoring thread must be created by the connector itself.
- Tasks must still handle errors when an input disappears (e.g. a dropped table) before the connector notices.
- Sink connectors mostly handle new streams (the framework handles topic changes, e.g. regex subscriptions); `SinkTask`s may need to create downstream resources and handle races between tasks creating the same resource.

## Configuration validation

Expose a `ConfigDef` through `config()` so Connect can validate configs before running the connector and give feedback/recommended values:

```java
static final ConfigDef CONFIG_DEF = new ConfigDef()
    .define(FILE_CONFIG, Type.STRING, null, Importance.HIGH, "Source filename. If not specified, the standard input will be used")
    .define(TOPIC_CONFIG, Type.STRING, ConfigDef.NO_DEFAULT_VALUE, new ConfigDef.NonEmptyString(), Importance.HIGH, "The topic to publish data to")
    .define(TASK_BATCH_SIZE_CONFIG, Type.INT, DEFAULT_TASK_BATCH_SIZE, Importance.LOW,
        "The maximum number of records the source task can read from the file each time it is polled");

public ConfigDef config() {
    return CONFIG_DEF;
}
```

`ConfigDef` supports name, type, default, docs, group/order, width, display name, custom `Validator`s, dependents and `Recommender`s. `Connector.validate()` has a default implementation (which doesn't use recommended values for validation); override it for custom validation. Users call it via `PUT /connector-plugins/{connector-type}/config/validate`.

## Working with schemas

Use the Connect `data` API — mainly `Schema` and `Struct`:

```java
Schema schema = SchemaBuilder.struct().name(NAME)
    .field("name", Schema.STRING_SCHEMA)
    .field("age", Schema.INT_SCHEMA)
    .field("admin", SchemaBuilder.bool().defaultValue(false).build())
    .build();

Struct struct = new Struct(schema)
    .put("name", "Barbara Liskov")
    .put("age", 75);
```

- Source connectors: create fixed schemas once and reuse them; handle dynamic schemas (e.g. `ALTER TABLE`) by detecting changes.
- Sink connectors: validate incoming schemas and throw an exception on mismatch.

## Packaging for plugin discovery

For the fast `plugin.discovery=service_load` mode, ship ServiceLoader manifests in `META-INF/services/` named after each plugin supertype you implement, listing implementation classes one per line (mark non-plugin classes `abstract`). Types expecting manifests:

- `org.apache.kafka.connect.sink.SinkConnector`
- `org.apache.kafka.connect.source.SourceConnector`
- `org.apache.kafka.connect.storage.Converter`
- `org.apache.kafka.connect.storage.HeaderConverter`
- `org.apache.kafka.connect.transforms.Transformation`
- `org.apache.kafka.connect.transforms.predicates.Predicate`
- `org.apache.kafka.common.config.provider.ConfigProvider`
- `org.apache.kafka.connect.rest.ConnectRestExtension`
- `org.apache.kafka.connect.connector.policy.ConnectorClientConfigOverridePolicy`

```text
# META-INF/services/org.apache.kafka.connect.sink.SinkConnector
# license header or comment
com.example.MySinkConnector
```

Verify with a pre-release artifact using the `hybrid_warn`/`hybrid_fail` checks described in [Running Connect](overview-and-running.md#plugin-discovery).

## Related pages

- [Kafka Connect overview and workers](overview-and-running.md)
- [Single message transforms and predicates](transformations-and-predicates.md)
- [REST API, error handling and exactly-once](rest-api-and-operations.md)
